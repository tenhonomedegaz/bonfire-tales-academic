@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================================
echo   MIGRACAO SQLITE -^> POSTGRESQL
echo ========================================================
echo.
echo Esta etapa ja foi concluida em sessoes anteriores.
echo O site agora exige PostgreSQL via POSTGRES_URL ou DB_ENGINE.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado.
    pause
    exit /b 1
)

.venv\Scripts\python.exe manage.py check
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] A configuracao atual nao esta pronta para PostgreSQL.
    pause
    exit /b 1
)

.venv\Scripts\python.exe manage.py migrate --noinput
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao aplicar migracoes no PostgreSQL.
    pause
    exit /b 1
)

echo.
echo PostgreSQL verificado e migracoes aplicadas.
pause
