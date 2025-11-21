import keyboard
import psutil
import ctypes
import sys
import threading
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QComboBox, QDialog, QMessageBox,
    QSystemTrayIcon, QMenu, QKeySequenceEdit
)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt, QTimer, QEvent
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import os

# =====================
# Admin Privilege Check
# =====================
def check_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            from PyQt5.QtWidgets import QMessageBox, QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "ERROR", "This program must be run as Administrator")
            sys.exit(1)
    except:
        from PyQt5.QtWidgets import QMessageBox, QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "ERROR", "Unable to verify admin privileges")
        sys.exit(1)

check_admin()

# =====================
# Configuration
# =====================
if getattr(sys, 'frozen', False):
    program_dir = Path(sys.executable).resolve().parent
else:
    program_dir = Path(os.path.abspath(__file__)).resolve().parent
CONFIG_FILE = program_dir / ".app_pause_resume_config.json"

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"process_name": "", "hotkey": "F1"}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# =====================
# Process Suspend / Resume
# =====================
PROCESS_ALL_ACCESS = 0x1F0FFF

ntdll = ctypes.WinDLL("ntdll")
NtSuspendProcess = ntdll.NtSuspendProcess
NtResumeProcess = ntdll.NtResumeProcess
NtSuspendProcess.argtypes = [ctypes.c_void_p]
NtResumeProcess.argtypes = [ctypes.c_void_p]

NT_SUCCESS = lambda status: status >= 0

def get_handle_by_name(name):
    for p in psutil.process_iter(['name', 'pid']):
        if p.info['name'].lower() == name.lower():
            pid = p.info['pid']
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if handle:
                return handle, pid
    return None, None

def get_running_processes():
    processes = set()
    try:
        for p in psutil.process_iter(['name']):
            processes.add(p.info['name'])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return sorted(list(processes))

class ProcessController:
    def __init__(self):
        self.suspended = False
        self.current_handle = None
        self.current_pid = None
        self.current_process = ""
    
    def set_process(self, process_name):
        self.current_process = process_name
    
    def toggle(self):
        if not self.current_process:
            return False, "No process selected"
        
        handle, pid = get_handle_by_name(self.current_process)
        if handle is None:
            self.suspended = False
            self.current_handle = None
            self.current_pid = None
            return False, f"{self.current_process} not running"
        
        self.current_handle = handle
        self.current_pid = pid
        
        if not self.suspended:
            status = NtSuspendProcess(handle)
            if NT_SUCCESS(status):
                self.suspended = True
                return True, f"Suspended {self.current_process} (PID {pid})"
            else:
                return False, f"Failed to suspend {self.current_process}"
        else:
            status = NtResumeProcess(handle)
            if NT_SUCCESS(status):
                self.suspended = False
                return True, f"Resumed {self.current_process} (PID {pid})"
            else:
                return False, f"Failed to resume {self.current_process}"

# =====================
# Main GUI
# =====================
class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.config = load_config()
        self.current_hotkey = self.config.get("hotkey", "F1")
        self.init_ui()
        self.setup_hotkey()
    
    def init_ui(self):
        self.setWindowTitle("Application Pause/Resume")
        self.setGeometry(100, 100, 400, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        
        # Process Selection
        layout.addWidget(QLabel("Select or Enter Process Name:"))
        
        h_layout = QHBoxLayout()
        self.process_combo = QComboBox()
        self.process_combo.setEditable(True)
        self.refresh_processes()
        h_layout.addWidget(self.process_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_processes)
        h_layout.addWidget(refresh_btn)
        layout.addLayout(h_layout)
        
        if self.config.get("process_name"):
            self.process_combo.setCurrentText(self.config["process_name"])
        
        # Hotkey Setting
        layout.addWidget(QLabel("Hotkey:"))
        h_layout2 = QHBoxLayout()
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setText(self.current_hotkey)
        self.hotkey_edit.setReadOnly(True)
        h_layout2.addWidget(self.hotkey_edit)
        
        set_hotkey_btn = QPushButton("Set Hotkey")
        set_hotkey_btn.clicked.connect(self.open_hotkey_dialog)
        h_layout2.addWidget(set_hotkey_btn)
        layout.addLayout(h_layout2)
        
        # Control Buttons
        layout.addSpacing(20)
        
        start_btn = QPushButton("Start Monitoring")
        start_btn.clicked.connect(self.start_monitoring)
        layout.addWidget(start_btn)
        
        manual_toggle_btn = QPushButton("Manual Toggle (Pause/Resume)")
        manual_toggle_btn.clicked.connect(self.manual_toggle)
        layout.addWidget(manual_toggle_btn)
        
        # Status Label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        central_widget.setLayout(layout)
    
    def refresh_processes(self):
        current_text = self.process_combo.currentText()
        self.process_combo.clear()
        processes = get_running_processes()
        self.process_combo.addItems(processes)
        if current_text in processes:
            self.process_combo.setCurrentText(current_text)
    
    def open_hotkey_dialog(self):
        dialog = HotkeyDialog(self.current_hotkey, self)
        if dialog.exec_() == QDialog.Accepted:
            new_hotkey = dialog.get_hotkey()
            if new_hotkey:
                self.set_new_hotkey(new_hotkey)
    
    def set_new_hotkey(self, hotkey):
        try:
            keyboard.remove_hotkey(self.current_hotkey)
        except:
            pass
        
        try:
            keyboard.add_hotkey(hotkey, self.controller.toggle)
            self.current_hotkey = hotkey
            self.hotkey_edit.setText(hotkey)
            self.config["hotkey"] = hotkey
            save_config(self.config)
            self.status_label.setText(f"Hotkey changed to {hotkey}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to set hotkey: {str(e)}")
    
    def start_monitoring(self):
        process_name = self.process_combo.currentText().strip()
        if not process_name:
            QMessageBox.warning(self, "Error", "Please select or enter a process name")
            return
        
        self.controller.set_process(process_name)
        self.config["process_name"] = process_name
        save_config(self.config)
        self.status_label.setText(f"Monitoring: {process_name}")
    
    def manual_toggle(self):
        process_name = self.process_combo.currentText().strip()
        if not process_name:
            QMessageBox.warning(self, "Error", "Please select or enter a process name")
            return
        
        self.controller.set_process(process_name)
        success, message = self.controller.toggle()
        self.status_label.setText(message)
        if not success:
            QMessageBox.information(self, "Info", message)
    
    def setup_hotkey(self):
        try:
            keyboard.add_hotkey(self.current_hotkey, self.controller.toggle)
        except Exception as e:
            print(f"Failed to setup hotkey: {e}")
    
    def closeEvent(self, event):
        event.ignore()
        self.hide()

class HotkeyDialog(QDialog):
    def __init__(self, current_hotkey, parent=None):
        super().__init__(parent)
        self.hotkey = current_hotkey
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Set Hotkey")
        self.setGeometry(200, 200, 300, 150)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Press the key combination for the new hotkey:"))
        
        self.key_input = QLineEdit()
        self.key_input.setReadOnly(True)
        self.key_input.setText(self.hotkey)
        layout.addWidget(self.key_input)
        
        layout.addWidget(QLabel("(Press keys on your keyboard, then click OK)"))
        
        h_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        h_layout.addWidget(ok_btn)
        h_layout.addWidget(cancel_btn)
        layout.addLayout(h_layout)
        
        self.setLayout(layout)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        
        from PyQt5.QtGui import QKeySequence
        key_sequence = QKeySequence(event.key())
        key_name = key_sequence.toString()
        
        if not key_name or key_name == "Unknown":
            key_name = event.text() or str(event.key())
        
        self.key_input.setText(key_name)
        self.hotkey = key_name
    
    def get_hotkey(self):
        return self.hotkey

# =====================
# Tray Icon with pystray
# =====================
def create_tray_icon(main_window, controller, app):
    def on_quit(icon, item):
        try:
            icon.stop()
        except:
            pass
        # Use QApplication quit instead of sys.exit to properly shut down Qt
        app.quit()
    
    def on_show(icon, item):
        main_window.show()
        main_window.raise_()
        main_window.activateWindow()
    
    def on_toggle(icon, item):
        if main_window.controller.current_process:
            main_window.controller.toggle()
    
    # Create a simple icon image
    image = Image.new('RGB', (64, 64), color=(73, 109, 137))
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 16, 48, 48], fill=(255, 255, 255))
    draw.text((20, 24), "PS", fill=(0, 0, 0))
    
    menu = Menu(
        MenuItem("Show", on_show),
        MenuItem("Toggle Pause/Resume", on_toggle),
        MenuItem("Quit", on_quit)
    )
    
    icon = Icon("App Pause Resume", image, menu=menu)
    icon.run()

# =====================
# Main Execution
# =====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    controller = ProcessController()
    main_window = MainWindow(controller)
    
    # Start tray icon in separate thread
    tray_thread = threading.Thread(
        target=create_tray_icon,
        args=(main_window, controller, app),
        daemon=True
    )
    tray_thread.start()
    
    main_window.show()
    sys.exit(app.exec_())