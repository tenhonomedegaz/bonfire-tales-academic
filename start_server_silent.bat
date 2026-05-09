@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM Auto-minimizar a janela ao ser executado
if not defined MINIMIZED (
    set "MINIMIZED=1"
    start /min "" cmd /c "%~f0"
    exit /b
)

REM Script silencioso para iniciar o servidor Django automaticamente.
REM Usado pela Tarefa Agendada do Windows ou pelo bot do Discord.

if not exist ".env" exit /b 1
if not exist ".venv\Scripts\python.exe" exit /b 1

.venv\Scripts\python.exe manage.py collectstatic --noinput >nul 2>&1
.venv\Scripts\python.exe manage.py migrate --noinput >nul 2>&1

REM Extrai o token do Cloudflare do arquivo .env (se existir)
set "CLOUDFLARE_TUNNEL_TOKEN="
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if "%%A"=="CLOUDFLARE_TUNNEL_TOKEN" set "CLOUDFLARE_TUNNEL_TOKEN=%%B"
)

REM Inicia o Cloudflare Tunnel silenciosamente se o token estiver presente
if not "%CLOUDFLARE_TUNNEL_TOKEN%"=="" (
    if not exist "cloudflared.exe" (
        echo Baixando cloudflared.exe...
        curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe >nul 2>&1
    )
    if exist "cloudflared.exe" (
        start /B cloudflared.exe tunnel --no-autoupdate run --token %CLOUDFLARE_TUNNEL_TOKEN% >nul 2>&1
    )
)

REM Inicia o Waitress e redireciona a saída para o log, mantendo-o rodando
.venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8000 --threads=4 bonfire.wsgi:application > site_console.log 2>&1

