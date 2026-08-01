@echo off
REM One-command Windows launcher for the TNIC RCA dashboard.
REM Double-click this file, or run from cmd: start.demo.cmd
REM Requires Git Bash or WSL with bash on PATH.
setlocal
cd /d "%~dp0"

where bash >nul 2>&1
if %ERRORLEVEL%==0 (
  bash "%~dp0start.demo" %*
  exit /b %ERRORLEVEL%
)

where wsl >nul 2>&1
if %ERRORLEVEL%==0 (
  wsl -e bash ./start.demo %*
  exit /b %ERRORLEVEL%
)

echo ERROR: Need Git Bash or WSL to run start.demo
echo Install Git for Windows: https://git-scm.com/download/win
echo Or run from Git Bash:  ./start.demo
exit /b 1
