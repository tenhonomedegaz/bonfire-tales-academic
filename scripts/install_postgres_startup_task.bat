@echo off
set "TASK_NAME=BonfirePostgreSQL"
set "SCRIPT=%~dp0start_postgres_local.bat"

schtasks /Create /TN "%TASK_NAME%" /TR "\"%SCRIPT%\"" /SC ONLOGON /F
if %ERRORLEVEL% NEQ 0 (
  echo Falha ao criar a tarefa de inicializacao.
  exit /b %ERRORLEVEL%
)

schtasks /Run /TN "%TASK_NAME%"
exit /b %ERRORLEVEL%
