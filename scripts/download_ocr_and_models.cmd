@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\download_models.py

