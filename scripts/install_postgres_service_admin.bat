@echo off
set "SERVICE_NAME=BonfirePostgreSQL"
set "PGROOT=C:\Users\helio\Desktop\Projetos Bonfas\pgsql"
set "PGDATA=%PGROOT%\data"

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo Execute este arquivo como Administrador para instalar o servico do PostgreSQL.
  pause
  exit /b 1
)

"%PGROOT%\bin\pg_ctl.exe" register -N "%SERVICE_NAME%" -D "%PGDATA%" -S auto
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

sc start "%SERVICE_NAME%"
exit /b %ERRORLEVEL%
