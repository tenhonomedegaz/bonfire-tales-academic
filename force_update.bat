@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   ATUALIZACAO FORCADA DO SITE (Force Pull)
echo ===================================================
echo Este script apaga os arquivos de cache do Python
echo e forca o repositorio local a ficar exatamente
echo igual a versao da nuvem (branch dev).
echo O banco PostgreSQL nao fica dentro desta pasta e nao sera alterado pelo Git.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado!
    pause
    exit /b 1
)

echo [1/4] Limpando arquivos temporarios do Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /S /Q *.pyc >nul 2>&1

echo.
echo [2/4] Baixando alteracoes da nuvem e forcando sincronizacao...
git fetch --all
if errorlevel 1 (
    echo [ERRO] Falha ao baixar alteracoes da nuvem.
    pause
    exit /b 1
)

git reset --hard origin/dev
if errorlevel 1 (
    echo [ERRO] Falha no reset do repositorio.
    pause
    exit /b 1
)

echo.
echo [3/4] Aplicando migracoes do Django no PostgreSQL...
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 (
    echo [ERRO] O update terminou, mas as migracoes falharam.
    pause
    exit /b 1
)

echo.
echo [4/4] Coletando arquivos estaticos...
.venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 (
    echo [ERRO] O update terminou, mas o collectstatic falhou.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Atualizacao concluida com sucesso!
echo Se o servidor estiver rodando, ele ira recarregar.
echo ===================================================
pause
