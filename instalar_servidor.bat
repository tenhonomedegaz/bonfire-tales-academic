@echo off
chcp 65001 >nul 2>&1
title BonfireTales - Instalacao Inicial
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║    BONFIRE TALES - INSTALACAO DO SERVIDOR        ║
echo  ║    Execute este arquivo UMA VEZ como Admin       ║
echo  ╚══════════════════════════════════════════════════╝
echo.

REM Verificar se esta rodando como Administrador
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERRO] Este script precisa ser executado como Administrador!
    echo.
    echo  Clique com o botao DIREITO neste arquivo e
    echo  selecione "Executar como administrador".
    echo.
    pause
    exit /b 1
)

echo  [1/4] Verificando Python...
if exist ".venv\Scripts\python.exe" (
    echo         Python encontrado.
) else (
    echo  [ERRO] Ambiente Python nao encontrado!
    echo  Entre em contato com o desenvolvedor.
    pause
    exit /b 1
)
echo.

echo  [2/4] Instalando dependencias...
.venv\Scripts\pip.exe install -r requirements.txt --quiet
echo         Dependencias instaladas.
echo.

echo  [3/4] Preparando banco de dados...
.venv\Scripts\python.exe manage.py migrate --noinput
.venv\Scripts\python.exe manage.py collectstatic --noinput >nul 2>&1
echo         Banco de dados pronto.
echo.

echo  [4/5] Instalando Cloudflare Tunnel como servico do Windows...
cloudflared service install
if %ERRORLEVEL% EQU 0 (
    echo         Cloudflare Tunnel instalado como servico.
    echo         Ele vai iniciar automaticamente quando o PC ligar.
) else (
    echo         [AVISO] Nao foi possivel instalar o servico.
    echo         O tunnel vai precisar ser iniciado manualmente pelo start_server.bat
)
echo.

echo  [5/5] Configurando inicio automatico do servidor Django...
schtasks /create /tn "BonfireTales Servidor" /tr "\"%~dp0start_server_silent.bat\"" /sc onlogon /rl highest /f >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo         Servidor Django vai iniciar automaticamente no login.
) else (
    echo         [AVISO] Nao foi possivel agendar inicio automatico.
    echo         Use o atalho na Area de Trabalho para iniciar manualmente.
)
echo.

REM === Criar atalho na area de trabalho ===
echo  Criando atalho na Area de Trabalho...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine($ws.SpecialFolders('Desktop'), 'BonfireTales Servidor.lnk')); $s.TargetPath = '%~dp0start_server.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,13'; $s.Description = 'Iniciar o servidor do BonfireTales'; $s.Save()"
echo         Atalho criado!
echo.

echo  ╔══════════════════════════════════════════════════╗
echo  ║              INSTALACAO CONCLUIDA!               ║
echo  ║                                                  ║
echo  ║  Para iniciar o site, use o atalho               ║
echo  ║  "BonfireTales Servidor" na Area de Trabalho     ║
echo  ║                                                  ║
echo  ║  Ou clique duplo em: start_server.bat            ║
echo  ╚══════════════════════════════════════════════════╝
echo.
pause
