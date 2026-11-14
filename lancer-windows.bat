@echo off
chcp 65001 >nul
title Auto Shorts
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python n'est pas installe. Installe-le depuis https://www.python.org/downloads/
  echo  IMPORTANT : coche la case "Add python.exe to PATH" pendant l'installation.
  echo.
  pause
  exit /b
)

if not exist .venv (
  echo  Premiere installation, ca peut prendre 5 a 10 minutes...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q -U "yt-dlp[default]"

if not exist .env copy .env.example .env >nul

where deno >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Conseil : installe Deno pour que le telechargement YouTube marche bien :
  echo     winget install DenoLand.Deno
  echo.
)

python -m app.main
pause
