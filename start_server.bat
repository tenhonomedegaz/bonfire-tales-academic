@echo off
chcp 65001 >nul 2>&1
title BonfireTales - Servidor
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║         BONFIRE TALES - SERVIDOR DO SITE         ║
echo  ║                bonfiretales.com.br               ║
echo  ╚══════════════════════════════════════════════════╝
echo.

REM === Verificacoes ===
if not exist ".env" (
    echo  [ERRO] Arquivo .env nao encontrado!
    echo  Entre em contato com o desenvolvedor.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo  [ERRO] Ambiente Python nao encontrado!
    echo  Entre em contato com o desenvolvedor.
    pause
    exit /b 1
)

REM === Verificar se o Cloudflare Tunnel ja esta rodando ===
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    echo  [1/4] Iniciando Cloudflare Tunnel...
    start /B "" cloudflared tunnel run bonfire-site >nul 2>&1
    timeout /t 3 /nobreak >nul
    echo         Tunnel iniciado.
) else (
    echo  [1/4] Cloudflare Tunnel ja esta rodando.
)
echo.

REM === Coletar arquivos estaticos ===
echo  [2/4] Preparando arquivos do site...
.venv\Scripts\python.exe manage.py collectstatic --noinput
if %ERRORLEVEL% NEQ 0 (
    echo  [ERRO] Falha ao preparar arquivos estaticos.
    pause
    exit /b 1
)
echo         Arquivos prontos.
echo.

REM === Migracoes ===
echo  [3/4] Verificando banco de dados...
.venv\Scripts\python.exe manage.py migrate --noinput
if %ERRORLEVEL% NEQ 0 (
    echo  [ERRO] Falha ao aplicar migracoes do banco.
    pause
    exit /b 1
)
echo         Banco de dados OK.
echo.

REM === Iniciar servidor ===
echo  [4/4] Iniciando servidor...
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║  Site no ar! Acesse: https://bonfiretales.com.br ║
echo  ║                                                  ║
echo  ║  Para PARAR o servidor: feche esta janela        ║
echo  ║  ou pressione Ctrl+C                             ║
echo  ╚══════════════════════════════════════════════════╝
echo.

.venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8000 --threads=4 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto --clear-untrusted-proxy-headers bonfire.wsgi:application

echo.
echo  Servidor parado.
pause
