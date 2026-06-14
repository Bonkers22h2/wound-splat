@echo off
echo ========================================
echo   Wound-Splat - Starting System
echo ========================================
echo.

REM Start Backend (FastAPI) in a new window
echo Starting Backend (FastAPI)...
start "Wound-Splat Backend" cmd /k "call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && cd /d "%~dp0backend" && call venv\Scripts\activate && uvicorn main:app --reload --port 8000"

REM Wait a few seconds before starting frontend
timeout /t 5 /nobreak >nul

REM Start Frontend (Next.js) in a new window
echo Starting Frontend (Next.js)...
start "Wound-Splat Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

REM Wait for frontend to compile
timeout /t 8 /nobreak >nul

REM Open browser
echo Opening browser...
start http://localhost:3000

echo.
echo ========================================
echo   Wound-Splat is starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Two terminal windows have opened for Backend and Frontend.
echo Close those windows to stop the servers.
echo This window can be closed.
pause
