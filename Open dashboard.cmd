@echo off
rem Fetch the latest league pull, then open the dashboard.
cd /d "%~dp0"
git pull -q
start "" "dashboard.html"
