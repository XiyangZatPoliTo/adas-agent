@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat
start "API" cmd /k uvicorn BFF_Bot.api.app:app
start "UI" cmd /k streamlit run ui/app.py