# -*- coding: utf-8 -*-
"""Sincroniza o CONTEÚDO (home/fixtures/conteudo.json) na produção por CHAVE NATURAL.

Wrapper de linha de comando sobre `home.deploy_sync.sincronizar_conteudo` (o mesmo
núcleo usado pelo console do admin no upload de fixture). Ver docs/deploy-sync-conteudo.md.

    manage.py sync_conteudo            # executa (recomendado: deploy_conteudo.bat)
    manage.py sync_conteudo --dry-run  # só relata o plano
    manage.py sync_conteudo --allow-sqlite   # permite rodar em SQLite (teste local)
"""
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from home.deploy_sync import (UPSERT_POR_SLUG, SUBSTITUI, MEMORY_MODELS, _m,
                              _label, sincronizar_conteudo, relatorio_texto)

FIXTURE_PATH = "home/fixtures/conteudo.json"


class Command(BaseCommand):
    help = "Sincroniza o catálogo na produção por chave natural, preservando usuários/missões."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-sqlite", action="store_true")
        parser.add_argument("--no-backup", action="store_true")

    def handle(self, *args, **opt):
        if connection.vendor != "postgresql" and not opt["allow_sqlite"]:
            raise CommandError("Banco é '%s' (esperado postgresql). Rode na PRODUÇÃO ou use "
                               "--allow-sqlite." % connection.vendor)
        if not os.path.exists(FIXTURE_PATH):
            raise CommandError("Fixture não encontrado: %s" % FIXTURE_PATH)
        with open(FIXTURE_PATH, encoding="utf-8") as fh:
            texto = fh.read()

        if opt["dry_run"]:
            import json
            from collections import Counter
            cont = Counter(o["model"] for o in json.loads(texto))
            up = sum(cont.get(_label(_m(n)), 0) for n in UPSERT_POR_SLUG)
            rep = sum(cont.get(_label(_m(n)), 0) for n in SUBSTITUI)
            self.stdout.write(self.style.SUCCESS(
                "DRY-RUN: %d por slug (preserva PK) | %d substituídos. Nada alterado." % (up, rep)))
            return

        if not opt["no_backup"]:
            from datetime import datetime
            os.makedirs("backups", exist_ok=True)
            destino = os.path.join("backups", "memoria_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
            with open(destino, "w", encoding="utf-8") as fh:
                call_command("dumpdata", *("home.%s" % m for m in MEMORY_MODELS), indent=2, stdout=fh)
            self.stdout.write("Backup da memória -> %s" % destino)

        rel = sincronizar_conteudo(texto)
        self.stdout.write(relatorio_texto(rel))
        self.stdout.write(self.style.SUCCESS("Conteúdo sincronizado por chave natural.")
                          if rel["mem_ok"] else self.style.ERROR("Verifique a memória!"))
