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

.venv\Scripts\python.exe manage.py collectstatic --noinput >> site_console.log 2>&1
if %ERRORLEVEL% NEQ 0 exit /b 1

.venv\Scripts\python.exe manage.py migrate --noinput >> site_console.log 2>&1
if %ERRORLEVEL% NEQ 0 exit /b 1

REM Iniciar Cloudflare Tunnel se nao estiver rodando
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    start /B "" cloudflared tunnel run bonfire-site >nul 2>&1
)

REM Inicia o Waitress e redireciona a saída para o log, mantendo-o rodando
.venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8000 --threads=4 bonfire.wsgi:application > site_console.log 2>&1
