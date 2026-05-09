@echo off
echo ===================================================
echo   ATUALIZACAO FORCADA DO SITE (Force Pull)
echo ===================================================
echo Este script apaga os arquivos de cache do Python
echo e forca o repositorio local a ficar exatamente
echo igual a versao da nuvem (branch dev).
echo.
echo [1/3] Limpando arquivos temporarios do Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /S /Q *.pyc >nul 2>&1

echo [2/3] Baixando alteracoes da nuvem...
git fetch --all

echo [3/3] Forcando sincronizacao com a branch dev...
git reset --hard origin/dev

echo.
echo ===================================================
echo Atualizacao concluida com sucesso!
echo Se o servidor estiver rodando, ele ira recarregar.
echo ===================================================
pause
