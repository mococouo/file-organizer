@echo off
chcp 65001 >nul
title File Organizer

echo Starting File Organizer GUI...
echo.
python file_organizer_gui.py
echo.
echo The tool has closed. Press any key to exit...
pause >nul
