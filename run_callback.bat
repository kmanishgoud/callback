@echo off
REM Runs the weekly Callback report. Used by Windows Task Scheduler.
cd /d "%~dp0"
".venv\Scripts\python.exe" src\main.py
exit /b %ERRORLEVEL%