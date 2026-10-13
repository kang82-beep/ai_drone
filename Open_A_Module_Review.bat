@echo off
cd /d "%~dp0"
python run_module_review.py
if errorlevel 1 pause
