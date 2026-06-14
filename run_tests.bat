@echo off
cd /d "%~dp0.."
python tests/run_all_tests.py
pause
