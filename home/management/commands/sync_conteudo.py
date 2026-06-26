# -*- coding: utf-8 -*-
"""Sincroniza o CONTEÚDO (home/fixtures/conteudo.json) na produção por CHAVE NATURAL.

Por que NÃO por PK: os PKs do catálogo desalinharam entre dev e produção, então carregar
por PK (loaddata) sobrescreveria o registro errado (ex.: pôr "Frenesi" do Bárbaro em cima
da "Conjuração" de um conjurador). Aqui a sincronização é por slug/nome:

- Tabelas que os USUÁRIOS referenciam por FK (Raça, Essência, Linhagem, Antecedente,
  Classe, Subclasse, Opção, Magia, Talento, ItemMágico): match por **slug** → ATUALIZA o
  registro existente da produção (PRESERVA o PK da prod, então a FK do personagem continua
  válida) e INSERE os novos. Nunca apaga (não orfana FK).
- Demais tabelas (habilidades de classe, recursos, acesso-opção, traços raciais, condições,
  idiomas, regras, recompensas, itens mundanos, bestiário, armadilhas, mundo): ninguém as
  referencia por PK → SUBSTITUI inteiras (delete + reinsert), remapeando as FKs de pai
  (id_classe, id_raca, …) do PK do dev para o PK da produção.

A "memória" (personagens, missões, mercado, usuários) NÃO é tocada; é conferida antes/depois.

    manage.py sync_conteudo            # executa (recomendado: deploy_conteudo.bat)
    manage.py sync_conteudo --dry-run  # só relata o que faria (update/insert/replace)
    manage.py sync_conteudo --allow-sqlite   # permite rodar em SQLite (teste local)
"""
import os
from collections import defaultdict

from django.apps import apps
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction

FIXTURE_PATH = "home/fixtures/conteudo.json"

# Tabelas referenciadas por FK de usuário → match por slug, PRESERVA PK. (ordem: pais antes)
UPSERT_POR_SLUG = [
    "TbRaca", "TbEssencia", "TbAntecedente", "TbClasse", "TbOpcaojogo",
    "TbMagia", "TbTalento", "TbItemMagico", "TbLinhagem", "TbSubclasse",
]
# Tabelas não referenciadas por FK de usuário → substitui inteiras (delete + reinsert).
SUBSTITUI = [
    "TbClassehabilidade", "TbRecursoclasse", "TbAcessoopcao", "TbTracoracial",
    "TbCondicao", "TbIdioma", "TbRegra", "TbRecompensaMestre", "TbItemMundano",
    "TbRegiao", "TbTerritorio", "TbMapMarker", "TbBestiario", "TbArmadilha",
]
MEMORY_MODELS = [
    "TbPersonagem", "TbPersonagemAtributoBonus", "TbPersonagemClasse",
    "TbPersonagemEscolha", "TbPersonagemItem", "TbPersonagemMagia",
    "TbPersonagemPericia", "TbPersonagemPersonalidade", "TbPersonagemProficiencia",
    "TbPersonagemRecurso", "TbPersonagemTalento", "TbTransacao", "TbTransacaoMestre",
    "TbAventuraMestre", "TbAnuncioItemMagico", "TbCronica", "TbJornal",
    "TbReiDaColina", "UserProfile",
]


def _m(nome):
    return apps.get_app_config("home").get_model(nome)


def _fk_fields(model):
    """{attname (ex.: id_classe_id): ModeloAlvo} das FKs do modelo."""
    return {f.attname: f.related_model for f in model._meta.get_fields()
            if isinstance(f, models.ForeignKey)}


def _label(model):
    return "home." + model.__name__.lower()


def _contagem(nomes):
    return {nm: _m(nm).objects.count() for nm in nomes}


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

        # Carrega o fixture (conteúdo do dev) agrupado por modelo.
        por_modelo = defaultdict(list)
        with open(FIXTURE_PATH, encoding="utf-8") as fh:
            for d in serializers.deserialize("json", fh.read()):
                por_modelo[_label(d.object._meta.model)].append(d.object)

        remap = defaultdict(dict)   # remap['home.tbclasse'][dev_pk] = prod_pk

        def remapear_fks(obj):
            for attname, alvo in _fk_fields(obj._meta.model).items():
                dev_val = getattr(obj, attname)
                if dev_val is None:
                    continue
                mp = remap.get(_label(alvo))
                if mp is None:        # alvo fora do escopo (ex.: autor->User) → mantém
                    continue
                if dev_val in mp:
                    setattr(obj, attname, mp[dev_val])

        plano = {"upsert_update": 0, "upsert_insert": 0, "replace": 0}

        if opt["dry_run"]:
            for nome in UPSERT_POR_SLUG:
                M = _m(nome)
                existentes = set(M.objects.values_list("slug", flat=True))
                for obj in por_modelo.get(_label(M), []):
                    plano["upsert_update" if obj.slug in existentes else "upsert_insert"] += 1
            for nome in SUBSTITUI:
                plano["replace"] += len(por_modelo.get(_label(_m(nome)), []))
            self.stdout.write(self.style.SUCCESS(
                "DRY-RUN: por slug → %d atualizar + %d inserir | substituir inteiras → %d "
                "registros. Nada foi alterado." % (
                    plano["upsert_update"], plano["upsert_insert"], plano["replace"])))
            return

        mem_antes = _contagem(MEMORY_MODELS)
        if not opt["no_backup"]:
            from datetime import datetime
            os.makedirs("backups", exist_ok=True)
            destino = os.path.join("backups", "memoria_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
            with open(destino, "w", encoding="utf-8") as fh:
                call_command("dumpdata", *("home.%s" % m for m in MEMORY_MODELS), indent=2, stdout=fh)
            self.stdout.write("Backup da memória -> %s" % destino)

        with transaction.atomic():
            # PASSO 1: upsert por slug (preserva PK da produção)
            for nome in UPSERT_POR_SLUG:
                M = _m(nome)
                campos = [f.attname for f in M._meta.fields if not f.primary_key]
                up = ins = 0
                for obj in por_modelo.get(_label(M), []):
                    dev_pk = obj.pk
                    remapear_fks(obj)
                    prod = M.objects.filter(slug=obj.slug).first()
                    if prod:
                        for c in campos:
                            setattr(prod, c, getattr(obj, c))
                        prod.save()
                        remap[_label(M)][dev_pk] = prod.pk
                        up += 1
                    else:
                        obj.pk = None
                        obj.save()
                        remap[_label(M)][dev_pk] = obj.pk
                        ins += 1
                self.stdout.write("  %-20s slug: %d atualizados, %d inseridos" % (nome, up, ins))

            # PASSO 2: substitui inteiras (delete + reinsert, remapeando FKs de pai)
            for nome in SUBSTITUI:
                M = _m(nome)
                M.objects.all().delete()
                novos = por_modelo.get(_label(M), [])
                for obj in novos:
                    remapear_fks(obj)
                    obj.save(force_insert=True)   # mantém o PK do dev (ninguém referencia)
                self.stdout.write("  %-20s substituída: %d registros" % (nome, len(novos)))

            # PASSO 3: realinha sequences (Postgres)
            if connection.vendor == "postgresql":
                from io import StringIO
                buf = StringIO()
                call_command("sqlsequencereset", "home", stdout=buf)
                sql = buf.getvalue().strip()
                if sql:
                    with connection.cursor() as cur:
                        cur.execute(sql)
                self.stdout.write("Sequences realinhadas.")

        # Verificação: memória intacta
        mem_depois = _contagem(MEMORY_MODELS)
        mudou = {k: (mem_antes[k], mem_depois[k]) for k in mem_antes if mem_antes[k] != mem_depois[k]}
        if mudou:
            self.stdout.write(self.style.ERROR("ATENÇÃO: memória mudou! %s — restaure do backup!" % mudou))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Memória intacta: %d tabelas de usuário/missão com a mesma contagem." % len(mem_antes)))
        self.stdout.write(self.style.SUCCESS("Conteúdo sincronizado por chave natural."))
