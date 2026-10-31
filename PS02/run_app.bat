@echo off
cd /d "%~dp0"
echo ========================================================
echo Starting Financial Reconciliation Pipeline Dashboard...
echo Local URL: http://localhost:8501
echo ========================================================
streamlit run app.py
pause
