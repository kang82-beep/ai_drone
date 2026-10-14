@echo off
cd /d "%~dp0"
python export_web_data.py
start "" "%~dp0web\index.html"
