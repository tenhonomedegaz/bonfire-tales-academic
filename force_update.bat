@echo off
echo ===================================================
echo   ATUALIZACAO FORCADA DO SITE (Force Pull)
echo ===================================================
echo Este script apaga os arquivos de cache do Python
echo e forca o repositorio local a ficar exatamente
echo igual a versao da nuvem (branch dev).
echo.
echo [1/5] Limpando arquivos temporarios do Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /S /Q *.pyc >nul 2>&1

echo [2/5] Sincronizando e fazendo backup do banco de dados (SQLite ^<--^> Mongo)...
.venv\Scripts\python.exe manage.py sync_mongo_to_sqlite --bidirectional --confirm-merge

echo.
echo [3/5] Protegendo banco de dados local...
git rm --cached bonfas_classes.db -f >nul 2>&1
if exist bonfas_classes.db (
    copy /Y bonfas_classes.db bonfas_classes.db.bak >nul
    echo    Backup do banco criado (bonfas_classes.db.bak)
)

echo.
echo [4/5] Baixando alteracoes da nuvem e forcando sincronizacao...
git fetch --all
git reset --hard origin/dev

echo.
echo [5/5] Restaurando banco de dados...
if exist bonfas_classes.db.bak (
    copy /Y bonfas_classes.db.bak bonfas_classes.db >nul
    del bonfas_classes.db.bak >nul 2>&1
    echo    Banco de dados restaurado!
)

echo.
echo ===================================================
echo Atualizacao concluida com sucesso!
echo Se o servidor estiver rodando, ele ira recarregar.
echo ===================================================
pause
