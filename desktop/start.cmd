@echo off
rem Starts the Smartdumbphone PC program. Needs Python 3 from python.org.
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 main.py
  exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw main.py
  exit /b 0
)
echo Python er ikke installeret.
echo Hent det fra https://www.python.org/downloads/ og start programmet igen.
pause
