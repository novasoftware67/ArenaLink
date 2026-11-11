@echo off
cd /d "%~dp0"
py -3 -m pip install pyinstaller
if errorlevel 1 goto :error
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name ArenaLink app.py
if errorlevel 1 goto :error
echo Application created: dist\ArenaLink.exe
pause
exit /b 0
:error
echo Build failed. Check the output above.
pause
exit /b 1
