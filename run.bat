@echo off
title AI Job Application Co-Pilot
cd /d "%~dp0"
echo ========================================================
echo        AI Job Application Co-Pilot is Starting...
echo ========================================================
echo.
call .venv\Scripts\activate.bat
echo Starting Streamlit Dashboard...
streamlit run app.py
pause
