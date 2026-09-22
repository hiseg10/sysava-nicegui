@echo off
chcp 65001 > nul

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "SCRIPT_PY=%PROJECT_DIR%main.py"

echo =======================================================
echo          SYSAVA NICE-GUI - INICIANDO
echo =======================================================

if exist "%PYTHON_EXE%" goto :executar

echo [AVISO] Ambiente virtual (.venv) nao encontrado. Criando agora...
python -m venv "%VENV_DIR%"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -m pip install -r "%PROJECT_DIR%requirements.txt"
)

if not exist "%PYTHON_EXE%" (
    echo [ERRO] Nao foi possivel criar o ambiente Python.
    pause
    exit /b 1
)

:executar
echo [OK] Ambiente virtual: %VENV_DIR%
echo [OK] Acesse: http://127.0.0.1:8080
echo.

"%PYTHON_EXE%" "%SCRIPT_PY%"

if errorlevel 1 (
    echo.
    echo [ERRO] A aplicacao encerrou com falha.
    pause
)
