@echo off
set "PGROOT=C:\Users\helio\Desktop\Projetos Bonfas\pgsql"
set "PGDATA=%PGROOT%\data"
set "PGLOG=%PGROOT%\pg.log"

"%PGROOT%\bin\pg_ctl.exe" status -D "%PGDATA%" >nul 2>&1
if %ERRORLEVEL% EQU 0 exit /b 0

"%PGROOT%\bin\pg_ctl.exe" start -D "%PGDATA%" -l "%PGLOG%" -w
exit /b %ERRORLEVEL%
