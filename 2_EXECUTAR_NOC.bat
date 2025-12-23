@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM PASSO 2: EXECUTAR NOC COMMANDER
REM Execute este arquivo DEPOIS de instalar as dependências
REM ═══════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║     NOC COMMANDER v12 - INICIANDO SERVIDOR                             ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Procurar Python
set PYTHON_PATH=

REM Tentar comando "python"
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_PATH=python
    goto PYTHON_ENCONTRADO
)

REM Tentar comando "python3"
python3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_PATH=python3
    goto PYTHON_ENCONTRADO
)

REM Procurar em caminhos comuns
for %%P in (
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Program Files\Python314\python.exe"
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist "%%P" (
        set PYTHON_PATH=%%P
        goto PYTHON_ENCONTRADO
    )
)

REM Python não encontrado
echo ❌ ERRO: Python não encontrado!
echo.
echo Execute primeiro: 1_INSTALAR_PRIMEIRO.bat
echo.
pause
exit /b 1

:PYTHON_ENCONTRADO

REM Verificar se arquivo existe
if not exist "noc_commander_v12_melhorado.py" (
    echo ❌ ERRO: Arquivo 'noc_commander_v12_melhorado.py' não encontrado!
    echo.
    echo Certifique-se de que o arquivo está nesta pasta.
    echo.
    pause
    exit /b 1
)

echo ✅ Python encontrado
echo ✅ Arquivo NOC encontrado
echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo.
echo 🚀 Iniciando NOC Commander...
echo.
echo ⏳ Aguarde a mensagem "Uvicorn running on http://0.0.0.0:8000"
echo.
echo 🌐 Quando estiver pronto, abra seu navegador em:
echo    http://localhost:8000
echo.
echo 📝 Para parar o servidor, pressione Ctrl+C
echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo.

!PYTHON_PATH! noc_commander_v12_melhorado.py

echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo Servidor finalizado.
echo.
pause
