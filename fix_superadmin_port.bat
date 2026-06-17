@echo off
setlocal
set PORT=8080
:RETRY
netstat -ano | findstr :%PORT% | findstr LISTENING >nul
if not errorlevel 1 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
        echo Killing PID %%a on port %PORT%
        taskkill /PID %%a /F
    )
    goto RETRY
)
echo Starting superadmin app on port %PORT%
start /B "" python superadmin_app.py
endlocal