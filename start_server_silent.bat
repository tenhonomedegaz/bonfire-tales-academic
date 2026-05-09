@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM Script silencioso para iniciar o servidor Django automaticamente.
REM Usado pela Tarefa Agendada do Windows.

if not exist ".env" exit /b 1
if not exist ".venv\Scripts\python.exe" exit /b 1

.venv\Scripts\python.exe manage.py collectstatic --noinput >nul 2>&1
.venv\Scripts\python.exe manage.py migrate --noinput >nul 2>&1

REM Inicia o Waitress e redireciona a saída para o log, mantendo-o rodando
.venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8000 --threads=4 bonfire.wsgi:application > site_console.log 2>&1
