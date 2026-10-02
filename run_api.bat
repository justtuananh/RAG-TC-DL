@echo off
title QTKD API Server :8080
set OLLAMA_MODEL=qwen2.5:3b
echo Starting QTKD RAG API Server (model: %OLLAMA_MODEL%) on http://localhost:8080 ...
echo.
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m api.main
pause
