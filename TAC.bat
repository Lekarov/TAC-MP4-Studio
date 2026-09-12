@echo off
cd /d "%~dp0"

set "REQ_FILE=requirements.txt"
set "HASH_FILE=.requirements.hash"

if not exist "%REQ_FILE%" goto :run

for /f "skip=1 tokens=1" %%h in ('certutil -hashfile "%REQ_FILE%" SHA256 2^>nul') do (
    if not defined NEW_HASH set "NEW_HASH=%%h"
)

set "OLD_HASH="
if exist "%HASH_FILE%" set /p OLD_HASH=<"%HASH_FILE%"

if "%NEW_HASH%"=="%OLD_HASH%" goto :run

echo Dependances modifiees, mise a jour...
pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo Echec de la mise a jour des dependances.
    pause
    exit /b 1
)
>"%HASH_FILE%" echo %NEW_HASH%

:run
python main.py
