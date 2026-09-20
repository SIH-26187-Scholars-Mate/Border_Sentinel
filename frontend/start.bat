@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Install Node.js LTS first.
  exit /b 1
)
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
  if errorlevel 1 exit /b 1
)
if not exist .env copy /Y .env.example .env >nul
call npm start
