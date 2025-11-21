App Pause/Resume

A small Windows utility to suspend and resume a target process using a global hotkey or via the system tray.

<img width="454" height="359" alt="Screenshot 2025-11-21 175036" src="https://github.com/user-attachments/assets/c34b9351-bb40-4927-a2e7-8bae3659b5af" />

Requirements:
- Run as Administrator

Quick usage:
- Run with: `python windows_app_pause_resume.py` or use the bundled executable (`app_pause_resume.exe`) if built.
- Select or type a process name in the UI and click "Start Monitoring".
- Use the configured hotkey (default `F1`) or the tray menu to toggle pause/resume.
- Config is stored in `.app_pause_resume_config.json` in the program folder.

development:
- Virtual environment `uv venv`
- Install dependencies `uv pip install --requirements requirements.txt` 
- Run the app `uv run windows_app_pause_resume.py`

Building (PyInstaller):
- `uvx pyinstaller --onefile --noconsole --paths .venv/Lib/site-packages/ --name app_pause_resume .\windows_app_pause_resume.py`


Use with care
