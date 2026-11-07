@echo off
set "PGROOT=C:\Users\helio\Desktop\Projetos Bonfas\pgsql"
set "PGDATA=%PGROOT%\data"

"%PGROOT%\bin\pg_ctl.exe" stop -D "%PGDATA%" -m fast -w
exit /b %ERRORLEVEL%
