@echo off
title BonfireTales - Restaurar Backup Producao
cd /d "%~dp0"

echo ====================================================
echo   RESTAURANDO BACKUP NO AMBIENTE DE PRODUCAO
echo   Backup: ref/backup_site_20260613_185509.json
echo ====================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts/restore_backup.py ref/backup_site_20260613_185509.json

echo.
echo Restauracao concluida!
pause
