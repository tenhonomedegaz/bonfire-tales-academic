# -*- coding: utf-8 -*-
"""Simula um evento de pagamento do Asaas para TESTAR a integração sem precisar dos
links de checkout reais (que só existem em produção).

Dois modos:

  --modo http   (padrão)  POSTa um payload de webhook no endpoint /webhooks/asaas/ do
                          site em execução. Exercita o CAMINHO REAL: auth do token,
                          filtro de evento, mapeamento e criação da transação. Útil pra
                          validar que o endpoint está de pé e configurado.

  --modo seed             Cria a linha em `transactions` DIRETO (sem HTTP), deixando você
                          definir e-mail/nome — assim o bot consegue casar o claim com a
                          conta do Discord e conceder os benefícios. Útil pra testar o
                          fluxo completo site→banco→bot.

Exemplos:
  manage.py simular_webhook_asaas --plano colaborador-conde-1m
  manage.py simular_webhook_asaas --modo seed --plano colaborador-duque-3m --email voce@email.com --valor 107.73
  manage.py simular_webhook_asaas --url https://bonfiretales.com.br/webhooks/asaas/

Plano = externalReference: colaborador-<conde|marques|duque>-<1m|3m|6m|12m>.
"""
import json
import urllib.request
import urllib.error
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Simula um webhook de pagamento do Asaas (modo http ou seed) para testar a integração."

    def add_arguments(self, parser):
        parser.add_argument("--modo", choices=["http", "seed"], default="http")
        parser.add_argument("--plano", default="colaborador-conde-1m",
                            help="externalReference: colaborador-<tier>-<periodo>")
        parser.add_argument("--evento", default="PAYMENT_CONFIRMED",
                            choices=["PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"])
        parser.add_argument("--valor", type=float, default=19.90)
        parser.add_argument("--email", default="teste-sandbox@bonfiretales.com.br",
                            help="(modo seed) e-mail do cliente — deve casar com a conta do Discord no claim")
        parser.add_argument("--nome", default="Teste Sandbox")
        parser.add_argument("--id", dest="pay_id", default=None,
                            help="id do pagamento (default: aleatório, para não colidir na idempotência)")
        parser.add_argument("--url", default="http://localhost:8000/webhooks/asaas/",
                            help="(modo http) URL do endpoint do webhook")

    def handle(self, *args, **opt):
        pay_id = opt["pay_id"] or ("sandbox_%s" % uuid.uuid4().hex[:16])
        plano = opt["plano"].strip()
        if not plano.startswith("colaborador-"):
            self.stdout.write(self.style.WARNING(
                "Aviso: plano '%s' não começa com 'colaborador-'; o bot pode não reconhecer." % plano))

        if opt["modo"] == "http":
            self._modo_http(pay_id, plano, opt)
        else:
            self._modo_seed(pay_id, plano, opt)

    # ───────────────────────── modo HTTP (endpoint real) ─────────────────────────
    def _modo_http(self, pay_id, plano, opt):
        if not settings.ASAAS_WEBHOOK_TOKEN:
            self.stdout.write(self.style.ERROR(
                "ASAAS_WEBHOOK_TOKEN está vazio no .env — o endpoint vai responder 401. "
                "Defina um token antes (o mesmo que você porá no painel do Asaas)."))
            return
        # payload no formato do Asaas; o endpoint usa este 'payment' inline como fallback
        # quando a API não resolve o id (id fake em sandbox) — então o teste é self-contained.
        body = {
            "event": opt["evento"],
            "payment": {
                "id": pay_id,
                "value": opt["valor"],
                "netValue": opt["valor"],
                "externalReference": plano,
                "paymentDate": timezone.now().strftime("%Y-%m-%d"),
                "subscription": None,
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            opt["url"], data=data, method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                     "asaas-access-token": settings.ASAAS_WEBHOOK_TOKEN})
        self.stdout.write("POST %s  (evento=%s, plano=%s, id=%s)" % (opt["url"], opt["evento"], plano, pay_id))
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                corpo = resp.read().decode("utf-8", "replace")
                self.stdout.write(self.style.SUCCESS("→ HTTP %s: %s" % (resp.status, corpo)))
        except urllib.error.HTTPError as e:
            self.stdout.write(self.style.ERROR("→ HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace"))))
            return
        except urllib.error.URLError as e:
            raise CommandError("Falha ao conectar em %s — o servidor está no ar? (%s)" % (opt["url"], e.reason))
        self.stdout.write(
            "Obs.: pelo endpoint, o e-mail do cliente só é preenchido se a API do Asaas resolver o "
            "customer (id real de sandbox). Para semear uma transação claimável com e-mail definido, "
            "use --modo seed.")
        self._mostrar_transacao(pay_id)

    # ───────────────────────── modo SEED (linha direta) ─────────────────────────
    def _modo_seed(self, pay_id, plano, opt):
        from home.models import BotTransaction
        from home.views import _asaas_map_transacao, _add_meses
        payment = {
            "id": pay_id, "value": opt["valor"], "netValue": opt["valor"],
            "externalReference": plano,
            "paymentDate": timezone.now().strftime("%Y-%m-%d"), "subscription": None,
        }
        campos = _asaas_map_transacao(payment, opt["evento"])
        campos["email"] = opt["email"].strip()
        campos["name"] = opt["nome"]
        pdate, meses = campos.pop("_paymentDate"), campos.pop("_meses")
        agora = timezone.now()
        if BotTransaction.objects.filter(transactionCode=pay_id).exists():
            raise CommandError("Já existe transação com id %s. Use --id outro ou deixe aleatório." % pay_id)
        BotTransaction.objects.create(
            id="asaas_%s" % uuid.uuid4().hex, paymentDate=pdate,
            expirationDate=_add_meses(pdate, meses), claimed=False,
            createdAt=agora, updatedAt=agora, **campos)
        self.stdout.write(self.style.SUCCESS(
            "Transação semeada (claimed=False) — o bot concede os benefícios no claim/resgate."))
        self._mostrar_transacao(pay_id)

    def _mostrar_transacao(self, pay_id):
        from home.models import BotTransaction
        t = BotTransaction.objects.filter(transactionCode=pay_id).first()
        if not t:
            self.stdout.write(self.style.WARNING("Nenhuma transação encontrada com transactionCode=%s." % pay_id))
            return
        self.stdout.write(
            "  transactions: plano=%s período=%s valor=%.2f email=%s claimed=%s expira=%s"
            % (t.subscriptionPlan, t.subscriptionPeriod, t.grossAmount,
               t.email or "(vazio)", t.claimed, t.expirationDate.strftime("%Y-%m-%d")))
