@echo off
cd /d "%~dp0"
python -m pv_inspector --gui
if errorlevel 1 pause
