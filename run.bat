@echo off
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Running main.py...
python main.py

echo.
echo Script finished. Press any key to exit.
pause >nul
