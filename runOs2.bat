@echo off
title OS2 Messenger

echo Starting OS2 Messenger...
echo.

:: Start the registry server in a new window
start "OS2 Registry Server" cmd /k "cd /d "%~dp0OS2" && python server.py"

:: Brief pause to let the server start
timeout /t 2 /nobreak >nul

:: Start the web app in a new window
start "OS2 Web App" cmd /k "cd /d "%~dp0OS2" && python web_app.py"

:: Wait a moment then open the browser
timeout /t 3 /nobreak >nul
start http://localhost:5000

echo Both services are starting in separate windows.
echo Close those windows to shut down OS2.