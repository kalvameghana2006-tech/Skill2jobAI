@echo off
REM One-command launcher (Windows):  run.bat
cd /d %~dp0
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist data\taxonomy.json ( python scripts\build_data.py )
streamlit run app.py
