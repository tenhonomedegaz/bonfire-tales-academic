@echo off
chcp 65001 >nul 2>&1
echo Encerrando servidor Django na porta 8000...

FOR /F "tokens=5" %%T IN ('netstat -a -n -o ^| findstr :8000') DO (
    echo Finalizando processo PID %%T...
    taskkill /F /PID %%T >nul 2>&1
)

echo Servidor encerrado.
exit /b 0
