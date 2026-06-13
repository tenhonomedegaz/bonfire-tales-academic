#!/bin/bash
# Script to restore the backup_site_20260613_185509.json in production (Linux)

cd "$(dirname "$0")"

# Find python inside virtual env
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
else
    PYTHON_BIN="python3"
fi

echo "===================================================="
echo "  RESTAURANDO BACKUP NO AMBIENTE DE PRODUCAO"
echo "  Backup: ref/backup_site_20260613_185509.json"
echo "===================================================="
echo

$PYTHON_BIN scripts/restore_backup.py ref/backup_site_20260613_185509.json

echo
echo "Restauracao concluida!"
