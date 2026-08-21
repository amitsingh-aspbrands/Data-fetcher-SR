@echo off
REM This batch file is called by Windows Task Scheduler at 6 AM daily.
REM It runs the data fetcher script and logs any startup errors.

cd /d "D:\Data fetcher SR"
python main.py
