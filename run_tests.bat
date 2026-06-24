@echo off
cd /d "%~dp0"
python tests/test_fx_name_matrix.py || goto :fail
python tests/run_all_tests.py
if errorlevel 1 goto :fail
goto :done
:fail
echo Tests failed.
:done
pause
