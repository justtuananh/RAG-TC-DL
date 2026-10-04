@echo off
title QTKD - Start All
echo Starting QTKD RAG API Server + React Frontend...
echo.
start "QTKD API :8080" cmd /k "cd /d "%~dp0" && "%~dp0.venv\Scripts\python.exe" -m api.main"
timeout /t 2 /nobreak >nul
start "QTKD Frontend :5173" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo.
echo API:      http://localhost:8080
echo Frontend: http://localhost:5173
pause
