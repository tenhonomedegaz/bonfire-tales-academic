@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ===================================================
echo   BANCO DEFINITIVO: PostgreSQL
echo ===================================================
echo.
echo A sincronizacao SQLite/Mongo foi desativada.
echo Este projeto agora usa PostgreSQL como fonte unica.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado!
    pause
    exit /b 1
)

echo Rodando migracoes pendentes no PostgreSQL...
.venv\Scripts\python.exe manage.py migrate --noinput
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao aplicar migracoes.
    pause
    exit /b 1
)

echo.
echo PostgreSQL atualizado.
pause
