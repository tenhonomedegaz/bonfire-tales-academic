@echo off
chcp 65001 >nul 2>&1
title BonfireTales - Deploy de Conteudo
cd /d "%~dp0"

echo.
echo  ====================================================
echo    DEPLOY DE CONTEUDO [catalogo] para a producao
echo    Preserva usuarios, personagens e missoes.
echo  ====================================================
echo.

if not exist ".venv\Scripts\python.exe" goto :sem_venv

echo  [1/2] Aplicando migracoes [schema, aditivo]...
.venv\Scripts\python.exe manage.py migrate --noinput
if %ERRORLEVEL% NEQ 0 goto :erro_migrate
echo         Schema OK.
echo.

echo  [2/2] Sincronizando conteudo [backup + checagem de PK + load]...
.venv\Scripts\python.exe manage.py sync_conteudo
if %ERRORLEVEL% NEQ 0 goto :erro_sync

echo.
echo  ====================================================
echo    Conteudo sincronizado. Memoria preservada.
echo  ====================================================
pause
exit /b 0

:sem_venv
echo  [ERRO] Ambiente Python .venv nao encontrado.
pause
exit /b 1

:erro_migrate
echo  [ERRO] migrate falhou. Abortado.
pause
exit /b 1

:erro_sync
echo.
echo  [ERRO] sync_conteudo abortou. NADA foi carregado. Veja a mensagem acima.
pause
exit /b 1
