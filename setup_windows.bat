@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Border Sentinel backend + AI dependencies are installed in .venv.
echo.
echo Start the backend from this folder with:
echo   .venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
exit /b 0
:fail
echo Dependency installation failed. Check the messages above.
exit /b 1
