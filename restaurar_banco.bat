@echo off
title BonfireTales - Restaurar Banco de Dados
cd /d "%~dp0"

echo ====================================================
echo      RESTAURADOR DE BANCO DE DADOS (POSTGRESQL)
echo ====================================================
echo.

set "BACKUP_FILE=%~1"

if "%BACKUP_FILE%"=="" (
    echo [Instrucao] Arraste e solte o arquivo de backup .json aqui
    echo             ou digite o caminho completo do arquivo.
    echo.
    set /p "BACKUP_FILE=Caminho do arquivo: "
)

REM Remover aspas extras que o usuario possa ter digitado ou que vieram do drag-and-drop
set "BACKUP_FILE=%BACKUP_FILE:"=%"

if "%BACKUP_FILE%"=="" (
    echo [ERRO] Nenhum arquivo foi especificado!
    goto FIM
)

if not exist "%BACKUP_FILE%" (
    echo [ERRO] O arquivo nao foi encontrado no caminho:
    echo        "%BACKUP_FILE%"
    goto FIM
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado nesta pasta!
    goto FIM
)

echo.
echo ====================================================
echo   AVISO: O BANCO DE DADOS LOCAL SERA TOTALMENTE
echo   LIMPO E SOBRESCRITO PELO CONTEUDO DO BACKUP!
echo ====================================================
echo.
set /p "CONFIRM=Deseja prosseguir com a restauracao? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo Operacao cancelada pelo usuario.
    goto FIM
)

echo.
echo Iniciando processo de restauracao...
.venv\Scripts\python.exe scripts/restore_backup.py "%BACKUP_FILE%"

:FIM
echo.
echo Pressione qualquer tecla para fechar esta janela.
pause >nul
