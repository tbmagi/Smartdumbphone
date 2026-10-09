@echo off
rem Starts the Smartdumbphone PC program. Needs Python 3 (see docs\pc-program.md, step 1).
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  rem A visible check first: a first-time Python download, or a missing tkinter, shows up here.
  py -3 -c "import tkinter" || goto broken
  start "" pyw -3 main.py
  exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  python -c "import tkinter" || goto broken
  start "" pythonw main.py
  exit /b 0
)
echo Python er ikke installeret.
echo Se docs\pc-program.md, trin 1.
pause
exit /b 1

:broken
echo Python virker ikke endnu. Se docs\pc-program.md, trin 1.
pause
exit /b 1
