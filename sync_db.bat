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

.venv\Scripts\python.exe manage.py sync_mongo_to_sqlite --bidirectional --confirm-merge

echo.
echo ===================================================
echo Sincronizacao concluida!
echo ===================================================
pause
