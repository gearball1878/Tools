@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
set "VENV_PY="

if exist "..\.venv\Scripts\python.exe" set "VENV_PY=..\.venv\Scripts\python.exe"
if not defined VENV_PY if exist ".venv\Scripts\python.exe" set "VENV_PY=.venv\Scripts\python.exe"

if defined VENV_PY goto :install_requirements

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    python3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD goto :no_python

echo [ISD Suite] Gemeinsame Python-Umgebung wird unter ..\.venv angelegt...
%PYTHON_CMD% -m venv ..\.venv
if errorlevel 1 goto :error
set "VENV_PY=..\.venv\Scripts\python.exe"

:install_requirements
"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ISD Suite] Pip wird in der Python-Umgebung eingerichtet...
    "%VENV_PY%" -m ensurepip --upgrade
    if errorlevel 1 goto :requirements_error
)
echo [ISD Suite] Abhaengigkeiten aus requirements.txt werden geprueft...
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :requirements_error

echo [ISD Suite] Anwendung wird gestartet...
echo Der Browser oeffnet sich automatisch, sobald der Server bereit ist.
"%VENV_PY%" main.py
if errorlevel 1 goto :error
endlocal
exit /b 0

:no_python
echo.
echo [FEHLER] Es wurde keine verwendbare Python-Installation gefunden.
echo Bitte Python 3.11 oder neuer installieren und dabei
echo "Add python.exe to PATH" aktivieren.
echo Download: https://www.python.org/downloads/windows/
pause
endlocal
exit /b 1

:requirements_error
echo.
echo [FEHLER] Die Abhaengigkeiten aus requirements.txt konnten nicht installiert werden.
echo Bitte die pip-Fehlermeldung oben pruefen und den Start erneut versuchen.
echo Verwendete Python-Umgebung: "%VENV_PY%"
pause
endlocal
exit /b 1

:error
echo.
echo [FEHLER] Die Anwendung konnte nicht gestartet werden.
echo Bitte den oben angezeigten Fehler fuer die Diagnose kopieren.
pause
endlocal
exit /b 1
