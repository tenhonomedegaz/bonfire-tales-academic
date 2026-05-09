# BonfireTales - Guia do Servidor

## Como funciona

O site **bonfiretales.com.br** roda neste computador. Quando o computador
está ligado e o servidor está rodando, o site fica acessível pela internet.

---

## Primeiro uso (UMA VEZ)

1. Clique com o botão **DIREITO** no arquivo `instalar_servidor.bat`
2. Selecione **"Executar como administrador"**
3. Aguarde a instalação terminar
4. Pronto! Um atalho foi criado na Área de Trabalho

---

## Uso diário

### Se o servidor iniciar automaticamente:
- Não precisa fazer nada! O servidor inicia sozinho quando você liga o PC
- Para verificar se está funcionando, acesse https://bonfiretales.com.br

### Se precisar iniciar manualmente:
- Clique duplo no atalho **"BonfireTales Servidor"** na Área de Trabalho
- Ou clique duplo no arquivo `start_server.bat` na pasta do projeto

### Para parar o servidor:
- Feche a janela preta (terminal) do servidor
- Ou pressione `Ctrl+C` na janela do terminal

---

## Arquivos importantes

| Arquivo | O que faz |
|---------|-----------|
| `start_server.bat` | Inicia o servidor (clique duplo) |
| `instalar_servidor.bat` | Instalação inicial (executar como admin, UMA VEZ) |
| `.env` | Configurações do site (NÃO MEXA!) |
| `bonfas_classes.db` | Banco de dados do site (NÃO APAGUE!) |

---

## Problemas comuns

### "O site não abre"
1. Verifique se o computador está ligado e conectado à internet
2. Verifique se a janela do servidor está aberta
3. Se não estiver, clique duplo no `start_server.bat`

### "Aparece erro na tela preta"
1. Feche a janela
2. Tente abrir novamente
3. Se o erro persistir, tire um print e envie para o desenvolvedor

### "Preciso desligar o computador"
- O site ficará fora do ar enquanto o computador estiver desligado
- Quando ligar novamente, o servidor deve iniciar automaticamente

---

## Contato para suporte técnico

Se algo não funcionar, entre em contato com o desenvolvedor e envie:
- Um print da tela de erro (se houver)
- O que você estava tentando fazer
