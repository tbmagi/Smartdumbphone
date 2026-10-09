@echo off
rem Sends one command to the Smartdumbphone app on the phone over USB (adb).
rem Examples:
rem   sdp status
rem   sdp hide com.android.chrome
rem   sdp unhide com.android.chrome
rem   sdp lock
rem   sdp unlock
rem   sdp list
rem   sdp release JA
setlocal
rem The phone answers in UTF-8 (Danish letters); make the console show them correctly.
chcp 65001 >nul
set "ADB=adb"
where adb >nul 2>nul
if errorlevel 1 set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not "%ADB%"=="adb" if not exist "%ADB%" (
  echo Kan ikke finde adb. Se docs\opsaetning.md, afsnit 3.
  exit /b 1
)
if "%~1"=="" (
  echo Brug: sdp status ^| list ^| hide PAKKE ^| unhide PAKKE ^| lock ^| unlock ^| release JA
  exit /b 1
)
set "URI=content://io.github.tbmagi.smartdumbphone.control"
if "%~2"=="" (
  "%ADB%" shell content call --uri %URI% --method %~1
) else (
  "%ADB%" shell content call --uri %URI% --method %~1 --arg %~2
)
