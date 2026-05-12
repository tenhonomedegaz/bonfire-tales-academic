@echo off
echo ===================================================
echo   SINCRONIZACAO DO BANCO DE DADOS (SQLite ^<--^> Mongo)
echo ===================================================
echo Este script garante que o seu banco local esteja
echo sincronizado e com backup no servidor remoto Mongo.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado!
    echo Execute o setup inicial primeiro.
    pause
    exit /b
)

if exist bonfas_classes.db (
    copy /Y bonfas_classes.db bonfas_classes.db.sync_backup >nul
    echo Backup local criado: bonfas_classes.db.sync_backup
)

.venv\Scripts\python.exe manage.py migrate --noinput
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao preparar banco para sincronizacao.
    pause
    exit /b 1
)

.venv\Scripts\python.exe manage.py sync_mongo_to_sqlite --bidirectional --confirm-merge
if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha na sincronizacao. O backup local foi preservado.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Sincronizacao concluida!
echo ===================================================
pause
