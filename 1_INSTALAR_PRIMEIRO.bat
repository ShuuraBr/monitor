@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM PASSO 1: INSTALAR DEPENDÊNCIAS
REM Execute este arquivo PRIMEIRO
REM ═══════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║     NOC COMMANDER v12 - INSTALAÇÃO DE DEPENDÊNCIAS                     ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Procurar Python
echo 🔍 Procurando Python instalado...
echo.

set PYTHON_PATH=
set PYTHON_VERSION=

REM Tentar comando "python"
python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    set PYTHON_PATH=python
    echo ✅ Python encontrado: !PYTHON_VERSION!
    goto PYTHON_ENCONTRADO
)

REM Tentar comando "python3"
python3 --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('python3 --version 2^>^&1') do set PYTHON_VERSION=%%i
    set PYTHON_PATH=python3
    echo ✅ Python encontrado: !PYTHON_VERSION!
    goto PYTHON_ENCONTRADO
)

REM Procurar em caminhos comuns
echo ⏳ Procurando em caminhos comuns...

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
        for /f "delims=" %%i in ('"%%P" --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo ✅ Python encontrado em: %%P
        echo    Versão: !PYTHON_VERSION!
        goto PYTHON_ENCONTRADO
    )
)

REM Python não encontrado
echo.
echo ❌ ERRO: Python não foi encontrado!
echo.
echo SOLUÇÃO:
echo 1. Acesse: https://www.python.org/downloads/
echo 2. Baixe Python 3.10 ou superior
echo 3. Execute o instalador
echo 4. MARQUE a opção: "Add Python to PATH"
echo 5. Clique em "Install Now"
echo 6. Reinicie o computador
echo 7. Execute este arquivo novamente
echo.
pause
exit /b 1

:PYTHON_ENCONTRADO
echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo.

REM Instalar pip
echo 📦 Atualizando pip...
!PYTHON_PATH! -m pip install --upgrade pip --quiet
if !errorlevel! neq 0 (
    echo ⚠️  Aviso ao atualizar pip (continuando...)
)
echo ✅ pip atualizado
echo.

REM Instalar dependências
echo 📦 Instalando dependências...
echo.

set PACOTES=fastapi uvicorn psutil requests ping3 speedtest-cli GPUtil

for %%P in (%PACOTES%) do (
    echo   ⏳ Instalando %%P...
    !PYTHON_PATH! -m pip install %%P --quiet
    if !errorlevel! equ 0 (
        echo   ✅ %%P instalado
    ) else (
        echo   ⚠️  Erro ao instalar %%P (continuando...)
    )
)

echo.
echo ═══════════════════════════════════════════════════════════════════════════
echo.
echo ✅ INSTALAÇÃO CONCLUÍDA!
echo.
echo 🚀 Próximo passo:
echo    Clique duas vezes em: 2_EXECUTAR_NOC.bat
echo.
pause
