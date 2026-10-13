@echo off
cd /d "%~dp0"
set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if not exist "%BLENDER_EXE%" (
  echo Blender not found. Edit BLENDER_EXE in this file for your PC.
  pause
  exit /b 1
)
"%BLENDER_EXE%" "results\blender_site\Shinan_Module_Results.blend" --python "blender_module_results_ui.py"
