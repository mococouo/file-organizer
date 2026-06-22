@echo off
chcp 65001 >nul
title File Organizer

echo ========================================
echo         File Organizer
echo ========================================
echo.
echo Starting command-line mode...
echo.

python file_organizer.py

echo.
echo ========================================
echo Press any key to exit...
echo ========================================
pause >nul
