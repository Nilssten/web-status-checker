@echo off
cd /d %~dp0
call venv\Scripts\activate  || echo (Skipping venv)
python WebCrawler.py
pause