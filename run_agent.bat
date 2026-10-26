@echo off
title Job Application Co-Pilot & Autonomous Agent
cd /d "%~dp0"
echo ===================================================
echo   Starting Job Application Co-Pilot & Autonomous Agent...
echo ===================================================
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
