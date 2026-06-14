@echo off
cd /d "%~dp0"
python glossary/build_glossary.py
if errorlevel 1 pause
