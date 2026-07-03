# -*- coding: utf-8 -*-
"""Exporta SÓ as tabelas de CONTEÚDO (catálogo do jogo) para um fixture JSON.

A ideia é levar o conteúdo do banco de TRABALHO (SQLite de dev) para a PRODUÇÃO
(PostgreSQL) com `loaddata`, que faz UPSERT por PK — preservando os IDs que os
dados de USUÁRIO/MISSÃO referenciam (TbPersonagemMagia.id_magia, .id_talento,
TbPersonagem.id_raca, etc.). Tabelas de usuário/runtime NÃO entram aqui e ficam
intactas na produção.

    manage.py dump_conteudo                      # catálogo principal -> conteudo.json
    manage.py dump_conteudo --output ref/backups/conteudo_AAAA-MM-DD.json
    manage.py dump_conteudo --mundo              # inclui Região/Território/Marcador
    manage.py dump_conteudo --bestiario-oficial  # inclui só Bestiário/Armadilha oficiais
    manage.py dump_conteudo --manifest m.json     # emite {modelo:{pk:chave-natural}} p/ checar alinhamento
"""
from django.core import serializers
from django.core.management.base import BaseCommand


# Catálogo do jogo — fonte de verdade = banco de trabalho. Ordem respeita FKs
# internas (pais antes dos filhos) para o loaddata não brigar.
CONTENT_MODELS = [
    "TbRaca", "TbLinhagem", "TbEssencia", "TbAntecedente",
    "TbClasse", "TbSubclasse", "TbClassehabilidade", "TbRecursoclasse",
    "TbOpcaojogo", "TbAcessoopcao",
    "TbMagia", "TbTalento", "TbTracoracial",
    "TbItemMagico", "TbItemMundano",
    "TbCondicao", "TbIdioma", "TbRegra", "TbRecompensaMestre",
    # Catálogo de cosméticos de perfil/ficha (F1). Inventário do usuário
    # (TbUsuarioCosmetico) é dado de USUÁRIO e NÃO entra aqui.
    "TbCosmetico",
    # Conquistas (F3): definição cadastrável pela staff → CONTEÚDO (sync por slug).
    # A concessão (TbUsuarioConquista) é dado de USUÁRIO e NÃO entra aqui.
    # Vem DEPOIS de TbCosmetico porque tem FK recompensa→TbCosmetico.
    "TbConquista",
    # Decisão do PO (2026-06-26): sincronizar Bestiário/Armadilhas inteiros (todos
    # oficiais, autor nulo) + conteúdo de mundo (fonte de verdade = dev).
    "TbBestiario", "TbArmadilha", "TbRegiao", "TbTerritorio", "TbMapMarker",
]
# (mantido p/ override futuro: rodar com --mundo NÃO duplica, pois já estão acima.)
WORLD_MODELS = []
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
                            help="Inclui TbRegiao/TbTerritorio/TbMapMarker.")
        parser.add_argument("--bestiario-oficial", action="store_true",
                            help="Inclui Bestiário/Armadilhas com autor nulo (oficiais).")
        parser.add_argument("--manifest", default=None,
                            help="Caminho p/ gravar {modelo:{pk:chave}} (checagem de alinhamento de PK).")

    def handle(self, *args, **opt):
        from django.apps import apps
        models = _resolve(CONTENT_MODELS)
        if opt["mundo"]:
            models += _resolve(WORLD_MODELS)

        objetos = []
        manifest = {}
        for m in models:
            qs = m.objects.all()
            objetos.extend(qs)
            if opt["manifest"]:
                key = NATURAL_KEY.get(m.__name__, "slug")
                if key and not hasattr(m, key):
                    key = "nome" if hasattr(m, "nome") else None
                manifest[m.__name__] = {
                    str(o.pk): (getattr(o, key) if key else None) for o in qs
                }

        # Bestiário/Armadilhas OFICIAIS (autor nulo) — opcional, sem clobber de comunidade.
        if opt["bestiario_oficial"]:
            for nm in ("TbBestiario", "TbArmadilha"):
                m = apps.get_app_config("home").get_model(nm)
                if "autor" in [f.name for f in m._meta.get_fields()]:
                    objetos.extend(m.objects.filter(autor__isnull=True))

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
