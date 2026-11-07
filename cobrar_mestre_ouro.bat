@echo off
REM ============================================================================
REM Cobranca mensal do Mestre Ouro (500 MM). Rodado diariamente pelo Agendador
REM de Tarefas do Windows (tarefa "Bonfire - Cobranca Mestre Ouro", 03:00).
REM Idempotente: so cobra quem tem pagamento vencido (mestre_ouro_proximo_pgto<=hoje).
REM Usa o banco PADRAO do projeto (settings/.env). Garanta que o banco esteja
REM acessivel no horario agendado. Em servidor Linux, use cron com o mesmo comando.
REM ============================================================================
cd /d "%~dp0"
".venv\Scripts\python.exe" -X utf8 manage.py cobrar_mestre_ouro >> "%~dp0mestre_ouro_cron.log" 2>&1
