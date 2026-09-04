@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 未找到虚拟环境，请先执行：python -m venv .venv
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py

