# -*- coding: utf-8 -*-
"""Exporta o catálogo mecânico para o merge por chave natural.

O arquivo gerado é consumido por ``sync_conteudo``/``merge_conteudo``. Não use
``loaddata``: PKs de dev e produção podem representar registros diferentes.

    manage.py dump_conteudo                      # catálogo principal -> conteudo.json
    manage.py dump_conteudo --output ref/backups/conteudo_AAAA-MM-DD.json
    manage.py dump_conteudo --mundo              # backup separado de mundo/wiki
    manage.py dump_conteudo --manifest m.json     # emite {modelo:{pk:chave-natural}} p/ checar alinhamento
"""
from django.core import serializers
from django.core.management.base import BaseCommand

from home.deploy_sync import (
    CONTENT_MODELS,
    OFFICIAL_REPLACE_MODELS,
    PRODUCTION_PRESERVED_MODELS,
)

# Mundo/wiki são produção-vence. ``--mundo`` existe apenas para backup/auditoria;
# essas tabelas são ignoradas pelo merge mecânico.
WORLD_MODELS = PRODUCTION_PRESERVED_MODELS
# Chave natural por modelo, p/ o manifesto de alinhamento de PK.
NATURAL_KEY = {
    "TbClassehabilidade": "nome", "TbRecursoclasse": "slug", "TbAcessoopcao": None,
}


def _resolve(model_names):
    from django.apps import apps
    out = []
    for nm in model_names:
        out.append(apps.get_app_config("home").get_model(nm))
    return out


class Command(BaseCommand):
    help = "Exporta as tabelas de CONTEÚDO (catálogo) para um fixture (sem dados de usuário)."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="conteudo.json")
        parser.add_argument("--mundo", action="store_true",
                            help="Inclui mundo/wiki para backup; o merge os ignora.")
        parser.add_argument("--bestiario-oficial", action="store_true",
                            help="Compatibilidade: bestiário/armadilhas já exportam só oficiais.")
        parser.add_argument("--manifest", default=None,
                            help="Caminho p/ gravar {modelo:{pk:chave}} (checagem de alinhamento de PK).")

    def handle(self, *args, **opt):
        models = _resolve(CONTENT_MODELS)
        if opt["mundo"]:
            models += _resolve(WORLD_MODELS)

        objetos = []
        manifest = {}
        for m in models:
            qs = m.objects.all()
            if m.__name__ in OFFICIAL_REPLACE_MODELS:
                qs = qs.filter(comunidade=False, autor__isnull=True)
            objetos.extend(qs)
            if opt["manifest"]:
                key = NATURAL_KEY.get(m.__name__, "slug")
                if key and not hasattr(m, key):
                    key = "nome" if hasattr(m, "nome") else None
                manifest[m.__name__] = {
                    str(o.pk): (getattr(o, key) if key else None) for o in qs
                }

        data = serializers.serialize("json", objetos, indent=2)
        with open(opt["output"], "w", encoding="utf-8") as fh:
            fh.write(data)
        self.stdout.write(self.style.SUCCESS(
            "Exportados %d registros de %d modelos -> %s" % (len(objetos), len(models), opt["output"])))

        if opt["manifest"]:
            import json
            with open(opt["manifest"], "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=1)
            self.stdout.write("Manifesto de PK->chave -> %s" % opt["manifest"])
