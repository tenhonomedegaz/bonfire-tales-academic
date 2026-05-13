@echo off
setlocal
cd /d "%~dp0"

set "DB_FILE=bonfas_classes.db"
set "DB_BACKUP=bonfas_classes.db.force_update_backup"

echo ===================================================
echo   ATUALIZACAO FORCADA DO SITE (Force Pull)
echo ===================================================
echo Este script apaga os arquivos de cache do Python
echo e forca o repositorio local a ficar exatamente
echo igual a versao da nuvem (branch dev).
echo O banco SQLite local sera preservado.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado!
    pause
    exit /b 1
)

echo [1/5] Limpando arquivos temporarios do Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /S /Q *.pyc >nul 2>&1

echo.
echo [2/5] Protegendo banco de dados local...
git rm --cached "%DB_FILE%" -f >nul 2>&1

if exist "%DB_FILE%" (
    copy /Y "%DB_FILE%" "%DB_BACKUP%" >nul
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar backup do banco. Update cancelado.
        pause
        exit /b 1
    )
    echo    Backup do banco criado: %DB_BACKUP%
) else (
    echo    Banco local nao encontrado. O update nao criara nem baixara um banco do Git.
)

echo.
echo [3/5] Baixando alteracoes da nuvem e forcando sincronizacao...
git fetch --all
if errorlevel 1 (
    echo [ERRO] Falha ao baixar alteracoes da nuvem.
    if exist "%DB_BACKUP%" copy /Y "%DB_BACKUP%" "%DB_FILE%" >nul
    pause
    exit /b 1
)

git reset --hard origin/dev
if errorlevel 1 (
    echo [ERRO] Falha no reset do repositorio.
    if exist "%DB_BACKUP%" copy /Y "%DB_BACKUP%" "%DB_FILE%" >nul
    pause
    exit /b 1
)

echo.
echo [4/5] Restaurando banco de dados local...
if exist "%DB_BACKUP%" (
    copy /Y "%DB_BACKUP%" "%DB_FILE%" >nul
    if errorlevel 1 (
        echo [ERRO] Update baixado, mas nao foi possivel restaurar o banco.
        echo        Backup preservado em %DB_BACKUP%.
        pause
        exit /b 1
    )
    echo    Banco de dados restaurado.
) else (
    echo    Nenhum backup local para restaurar.
)

echo.
echo [5/6] Aplicando migracoes do Django...
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 (
    echo [ERRO] O update terminou, mas as migracoes falharam.
    echo        O banco local foi preservado. Veja o erro acima.
    pause
    exit /b 1
)

echo.
echo [6/6] Restaurando dados do Mongo para o SQLite...
.venv\Scripts\python.exe manage.py sync_mongo_to_sqlite
if errorlevel 1 (
    echo [ERRO] O update terminou, mas a restauracao Mongo -> SQLite falhou.
    echo        O banco local foi preservado. Veja o erro acima.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Atualizacao concluida com sucesso!
echo Banco local preservado. Backup mantido em %DB_BACKUP%.
echo Se o servidor estiver rodando, ele ira recarregar.
echo ===================================================
pause
