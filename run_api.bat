@echo off
title QTKD API Server :8080
echo Starting QTKD RAG API Server on http://localhost:8080 ...
echo.
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m api.main
pause
