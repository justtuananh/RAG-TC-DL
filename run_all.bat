@echo off
title QTKD - Start All
set OLLAMA_MODEL=qwen2.5:3b
echo Starting QTKD RAG API Server + React Frontend (model: %OLLAMA_MODEL%)...
echo.
start "QTKD API :8080" cmd /k "set OLLAMA_MODEL=qwen2.5:3b && "%~dp0.venv\Scripts\python.exe" "%~dp0api_server.py""
timeout /t 2 /nobreak >nul
start "QTKD Frontend :5173" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo.
echo API:      http://localhost:8080
echo Frontend: http://localhost:5173
pause
