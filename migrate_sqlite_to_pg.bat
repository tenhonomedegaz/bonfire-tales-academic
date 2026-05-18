@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================================
echo   Migração de Dados do Django (SQLite -^> PostgreSQL)
echo ========================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual ^(.venv^) nao encontrado. Execute este script na raiz do projeto BonfireSite.
    pause
    exit /b
)

echo [1/5] Sincronizando o SQLite com o MongoDB (caso o Mongo exista)...
.venv\Scripts\python.exe manage.py sync_mongo_to_sqlite
if %errorlevel% neq 0 (
    echo [AVISO] Nao foi possivel sincronizar com o Mongo (ele nao existe ou esta indisponivel). Usando dados atuais do SQLite.
) else (
    echo OK! SQLite atualizado com os dados do Mongo.
)
echo.

echo [2/5] Extraindo os dados do SQLite...
echo (Isso pode demorar alguns segundos)
.venv\Scripts\python.exe manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 4 > datadump.json
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao exportar os dados do SQLite.
    pause
    exit /b
)
echo OK! Dados exportados para datadump.json
echo.

echo [3/5] Atualizando o arquivo .env para apontar para o PostgreSQL...
:: Verifica se ja esta configurado, caso contrario, adiciona as credenciais
findstr /C:"DB_ENGINE=django.db.backends.postgresql" .env > nul
if %errorlevel% neq 0 (
    echo.>> .env
    echo DB_ENGINE=django.db.backends.postgresql>> .env
    echo DB_NAME=postgres>> .env
    echo DB_USER=postgres>> .env
    echo DB_PASSWORD=bonfire>> .env
    echo DB_HOST=localhost>> .env
    echo DB_PORT=5432>> .env
    echo OK! Variaveis de banco inseridas no .env.
) else (
    echo O arquivo .env ja parece estar apontando para o PostgreSQL.
)
echo.

echo [4/5] Criando as tabelas no PostgreSQL (migrate)...
.venv\Scripts\python.exe manage.py migrate
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao criar tabelas no PostgreSQL. O servico do banco esta rodando?
    pause
    exit /b
)
echo OK! Tabelas recriadas no PostgreSQL.
echo.

echo [5/5] Importando os dados (loaddata)...
.venv\Scripts\python.exe manage.py loaddata datadump.json
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao importar os dados para o PostgreSQL.
    pause
    exit /b
)
echo OK! Dados importados com sucesso!
echo.

echo ========================================================
echo   MIGRACAO CONCLUIDA COM SUCESSO!
echo   Todos os Jornais, Classes, Racas e Usuarios foram
echo   migrados do SQLite para o PostgreSQL.
echo   O arquivo bonfas_classes.db ainda existe como backup.
echo ========================================================
pause
