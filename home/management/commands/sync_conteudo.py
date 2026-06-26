# -*- coding: utf-8 -*-
"""Carrega o CONTEÚDO (home/fixtures/conteudo.json) na PRODUÇÃO com segurança.

Roda na produção (após `git pull` + `migrate`) e atualiza só o catálogo, por UPSERT
de PK, SEM tocar nas tabelas de usuário/missão. Antes de carregar, confere se os PKs
do fixture (manifesto do dev) apontam para os MESMOS registros que já existem na
produção (chave natural slug/nome) — se houver divergência, ABORTA (não sobrescreve o
registro errado). Depois, conserta as sequences e confirma que a "memória"
(usuários/personagens/missões) ficou com a MESMA contagem.

    manage.py sync_conteudo            # checa, carrega, conserta sequences, verifica
    manage.py sync_conteudo --dry-run  # só a checagem de alinhamento (não carrega)
    manage.py sync_conteudo --allow-sqlite   # permite rodar em SQLite (teste local)
"""
import json
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from .dump_conteudo import CONTENT_MODELS, NATURAL_KEY, _resolve

FIXTURE = "conteudo"  # home/fixtures/conteudo.json (loaddata acha pelo nome)
MANIFEST_PATH = "home/fixtures/conteudo_manifest.json"

# "Memória" da produção — conferir que a contagem NÃO muda.
MEMORY_MODELS = [
    "TbPersonagem", "TbPersonagemAtributoBonus", "TbPersonagemClasse",
    "TbPersonagemEscolha", "TbPersonagemItem", "TbPersonagemMagia",
    "TbPersonagemPericia", "TbPersonagemPersonalidade", "TbPersonagemProficiencia",
    "TbPersonagemRecurso", "TbPersonagemTalento", "TbTransacao", "TbTransacaoMestre",
    "TbAventuraMestre", "TbAnuncioItemMagico", "TbCronica", "TbJornal",
    "TbReiDaColina", "UserProfile",
]


def _natural_key(model):
    nm = NATURAL_KEY.get(model.__name__, "slug")
    if nm and not hasattr(model, nm):
        nm = "nome" if hasattr(model, "nome") else None
    return nm


def _manifesto_atual():
    out = {}
    for m in _resolve(CONTENT_MODELS):
        key = _natural_key(m)
        if not key:
            continue
        out[m.__name__] = {str(o.pk): getattr(o, key) for o in m.objects.all()}
    return out


def _contagem(model_names):
    from django.apps import apps
    out = {}
    for nm in model_names:
        m = apps.get_app_config("home").get_model(nm)
        out[nm] = m.objects.count()
    return out


class Command(BaseCommand):
    help = "Carrega o conteúdo (fixture) na produção preservando usuários/missões."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Só checa alinhamento.")
        parser.add_argument("--allow-sqlite", action="store_true",
                            help="Permite rodar em SQLite (por padrão exige PostgreSQL).")
        parser.add_argument("--no-backup", action="store_true",
                            help="NÃO faz o backup da memória antes de carregar (não recomendado).")

    def handle(self, *args, **opt):
        if connection.vendor != "postgresql" and not opt["allow_sqlite"]:
            raise CommandError(
                "Banco atual é '%s' (esperado postgresql). Rode na PRODUÇÃO, ou use "
                "--allow-sqlite p/ testar localmente." % connection.vendor)

        # 1) Checagem de alinhamento de PK (fixture/dev × produção atual)
        if not os.path.exists(MANIFEST_PATH):
            raise CommandError("Manifesto não encontrado: %s" % MANIFEST_PATH)
        dev = json.load(open(MANIFEST_PATH, encoding="utf-8"))
        prod = _manifesto_atual()
        divergencias = []
        for modelo, devmap in dev.items():
            prodmap = prod.get(modelo, {})
            for pk, chave in devmap.items():
                if pk in prodmap and prodmap[pk] != chave:
                    divergencias.append((modelo, pk, chave, prodmap[pk]))
        if divergencias:
            self.stdout.write(self.style.ERROR(
                "ABORTADO: %d PK(s) apontam p/ registros DIFERENTES na produção "
                "(carregar sobrescreveria o errado):" % len(divergencias)))
            for modelo, pk, dv, pv in divergencias[:25]:
                self.stdout.write("  %s pk=%s  dev=%r  prod=%r" % (modelo, pk, dv, pv))
            raise CommandError("Alinhamento de PK divergente — sincronizar por chave natural à mão.")
        self.stdout.write(self.style.SUCCESS("Alinhamento de PK OK (nenhum PK aponta p/ registro diferente)."))

        if opt["dry_run"]:
            self.stdout.write("Dry-run: não carreguei nada.")
            return

        # 2) Snapshot da memória ANTES + backup (rede de segurança)
        mem_antes = _contagem(MEMORY_MODELS)
        if not opt["no_backup"]:
            from datetime import datetime
            os.makedirs("backups", exist_ok=True)
            destino = os.path.join("backups", "memoria_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
            with open(destino, "w", encoding="utf-8") as fh:
                call_command("dumpdata", *("home.%s" % m for m in MEMORY_MODELS),
                             indent=2, stdout=fh)
            self.stdout.write("Backup da memória -> %s" % destino)

        # 3) Carregar conteúdo (upsert por PK, em transação)
        with transaction.atomic():
            call_command("loaddata", FIXTURE, verbosity=1)

        # 4) Consertar sequences (Postgres)
        if connection.vendor == "postgresql":
            from io import StringIO
            buf = StringIO()
            call_command("sqlsequencereset", "home", stdout=buf)
            sql = buf.getvalue().strip()
            if sql:
                with connection.cursor() as cur:
                    cur.execute(sql)
            self.stdout.write("Sequences de PK realinhadas.")

        # 5) Verificar memória intacta
        mem_depois = _contagem(MEMORY_MODELS)
        mudou = {k: (mem_antes[k], mem_depois[k]) for k in mem_antes if mem_antes[k] != mem_depois[k]}
        if mudou:
            self.stdout.write(self.style.ERROR(
                "ATENÇÃO: contagem da MEMÓRIA mudou! %s — restaure do backup!" % mudou))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Memória intacta: %d tabelas de usuário/missão com a mesma contagem." % len(mem_antes)))

        # 6) Relatório do conteúdo
        cont = _contagem(CONTENT_MODELS)
        self.stdout.write(self.style.SUCCESS(
            "Conteúdo sincronizado: %d registros em %d tabelas." % (sum(cont.values()), len(cont))))
