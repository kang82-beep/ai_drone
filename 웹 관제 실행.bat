@echo off
cd /d "%~dp0"
if not exist web\data\site.js python run_flight.py --output results\shinan3_full_20261030
if not exist web\viewer\Shinan3_Viewer.html python build_shinan3_portable.py --output web\viewer --console-data ../data/site.js
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8765"
python serve_console.py
pause
