@echo off
cd /d "%~dp0"
python export_web_data.py
if not exist web\viewer\Shinan3_Viewer.html python build_shinan3_portable.py --output web\viewer --console-data ../data/site.js
start "" "%~dp0web\index.html"
