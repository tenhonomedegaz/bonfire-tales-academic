# Hospedagem Provisória

Este setup roda o site fora do servidor de desenvolvimento do Django, usando Waitress no Windows.

## 1. Preparar variáveis

Copie `production.env.example` para `.env.production` e ajuste:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `POSTGRES_URL`

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

No PowerShell:

```powershell
.\scripts\run_production.ps1 -HostAddress 0.0.0.0 -Port 8000
```

O script instala dependências, aplica migrations, coleta arquivos estáticos e sobe o WSGI com Waitress.

## 3. Expor para outros staffs

Opção simples com Cloudflare Tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Use a URL gerada no `.env.production` e reinicie o servidor.

## Observações

- Não use `runserver` para os staffs.
- Faça backup do PostgreSQL antes de rodar alterações grandes.
- O site usa PostgreSQL como banco definitivo; a sincronização SQLite/Mongo foi desativada.
