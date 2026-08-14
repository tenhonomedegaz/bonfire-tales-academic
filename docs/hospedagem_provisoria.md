# Hospedagem Provisória

Este setup roda o site fora do servidor de desenvolvimento do Django, usando Waitress no Windows.

## 1. Preparar variáveis

Copie `production.env.example` para `.env.production` e ajuste:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `POSTGRES_URL`
- `SITE_ORIGIN` (na produção: `https://bonfiretales.com.br`)
- `ADSENSE_ENABLED` (`1` para habilitar publicidade nas páginas elegíveis)
- `ADSENSE_PUBLISHER_ID` (por padrão, `ca-pub-1634793837919535`)

Os anúncios automáticos funcionam somente com o publisher configurado. Caso a equipe
crie unidades manuais no AdSense, informe também `ADSENSE_SIDEBAR_SLOT` e
`ADSENSE_HORIZONTAL_SLOT`. Telas privadas, ferramentas e páginas sem conteúdo
editorial não carregam inventário de anúncios.

Para túnel provisório via Cloudflare, coloque o domínio `trycloudflare.com` gerado em `DJANGO_ALLOWED_HOSTS` e a URL completa com `https://` em `DJANGO_CSRF_TRUSTED_ORIGINS`.

Em túnel provisório, mantenha:

```env
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SESSION_COOKIE_SECURE=0
DJANGO_CSRF_COOKIE_SECURE=0
DJANGO_SECURE_HSTS_SECONDS=0
```

Quando houver domínio/HTTPS fixo, esses valores podem ser endurecidos para `1` e HSTS pode ser configurado com cuidado.

## 2. Rodar o servidor

Execute:

```
start_server.bat
```

O script verifica `.env`/`.venv`, garante o Cloudflare Tunnel (`cloudflared tunnel run bonfire-site`) rodando, coleta arquivos estáticos, aplica migrations e sobe o WSGI com Waitress em `0.0.0.0:8000`.

## 3. Expor para outros staffs

Opção simples com Cloudflare Tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Use a URL gerada no `.env.production` e reinicie o servidor.

## Observações

- Não use `runserver` para os staffs.
- Faça backup do PostgreSQL antes de rodar alterações grandes.
- O site usa PostgreSQL como banco definitivo; a sincronização SQLite legado foi desativada.
