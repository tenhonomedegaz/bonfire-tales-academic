# -*- coding: utf-8 -*-
"""Núcleo reutilizável de sincronização de CONTEÚDO por chave natural.

Usado tanto pelo comando `manage.py sync_conteudo` quanto pelo console do admin
(upload de fixture do dev). Sincroniza o catálogo preservando a "memória" (usuários,
personagens, missões): tabelas referenciadas por FK de usuário casam por slug e
PRESERVAM o PK da produção; as demais são substituídas inteiras com remapeamento de FK.
Ver docs/deploy-sync-conteudo.md.
"""
from collections import defaultdict

from django.apps import apps
from django.core import serializers
from django.db import connection, models, transaction

# Referenciadas por FK de usuário → casa por slug, PRESERVA PK. (ordem: pais antes)
UPSERT_POR_SLUG = [
    "TbRaca", "TbEssencia", "TbAntecedente", "TbClasse", "TbOpcaojogo",
    "TbMagia", "TbTalento", "TbItemMagico", "TbLinhagem", "TbSubclasse",
]
# Não referenciadas por FK de usuário → substitui inteiras (delete + reinsert).
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
CONTENT_MODELS = UPSERT_POR_SLUG + SUBSTITUI


def _m(nome):
    return apps.get_app_config("home").get_model(nome)


def _fk_fields(model):
    return {f.attname: f.related_model for f in model._meta.get_fields()
            if isinstance(f, models.ForeignKey)}


def _label(model):
    return "home." + model.__name__.lower()


def contagem(nomes):
    return {nm: _m(nm).objects.count() for nm in nomes}


def sincronizar_conteudo(fixture_text):
    """Aplica o fixture de conteúdo (texto JSON serializado pelo Django) por chave
    natural. Retorna um relatório dict: {pass1, pass2, mem_antes, mem_depois, mem_ok}.
    Tudo numa transação — se algo falhar, faz rollback."""
    por_modelo = defaultdict(list)
    for d in serializers.deserialize("json", fixture_text):
        por_modelo[_label(d.object._meta.model)].append(d.object)

    remap = defaultdict(dict)

    def remapear_fks(obj):
        for attname, alvo in _fk_fields(obj._meta.model).items():
            val = getattr(obj, attname)
            if val is None:
                continue
            mp = remap.get(_label(alvo))
            if mp is not None and val in mp:
                setattr(obj, attname, mp[val])

    mem_antes = contagem(MEMORY_MODELS)
    rel = {"pass1": [], "pass2": []}

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
            rel["pass1"].append((nome, up, ins))

        # PASSO 2: substitui inteiras (delete + reinsert, remapeando FKs de pai)
        for nome in SUBSTITUI:
            M = _m(nome)
            M.objects.all().delete()
            novos = por_modelo.get(_label(M), [])
            for obj in novos:
                remapear_fks(obj)
                obj.save(force_insert=True)
            rel["pass2"].append((nome, len(novos)))

        # PASSO 3: realinha sequences (Postgres)
        if connection.vendor == "postgresql":
            from io import StringIO
            from django.core.management import call_command
            buf = StringIO()
            call_command("sqlsequencereset", "home", stdout=buf)
            sql = buf.getvalue().strip()
            if sql:
                with connection.cursor() as cur:
                    cur.execute(sql)

    mem_depois = contagem(MEMORY_MODELS)
    rel["mem_antes"] = mem_antes
    rel["mem_depois"] = mem_depois
    rel["mem_ok"] = mem_antes == mem_depois
    return rel


def relatorio_texto(rel):
    """Formata o relatório de sincronização como texto legível."""
    linhas = ["== Conteúdo referenciado (upsert por slug, preserva PK) =="]
    for nome, up, ins in rel["pass1"]:
        linhas.append("  %-20s %d atualizados, %d inseridos" % (nome, up, ins))
    linhas.append("== Demais tabelas (substituídas inteiras) ==")
    for nome, n in rel["pass2"]:
        linhas.append("  %-20s %d registros" % (nome, n))
    if rel["mem_ok"]:
        linhas.append("MEMÓRIA INTACTA: %d tabelas de usuário/missão com a mesma contagem." % len(rel["mem_antes"]))
    else:
        mudou = {k: (rel["mem_antes"][k], rel["mem_depois"][k])
                 for k in rel["mem_antes"] if rel["mem_antes"][k] != rel["mem_depois"][k]}
        linhas.append("ATENÇÃO: memória mudou! %s" % mudou)
    return "\n".join(linhas)
