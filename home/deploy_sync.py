# -*- coding: utf-8 -*-
"""Núcleo reutilizável de sincronização de CONTEÚDO por chave natural.

Usado tanto pelo comando `manage.py sync_conteudo` quanto pelo console do admin
(upload de fixture do dev). Sincroniza o catálogo preservando a "memória" (usuários,
personagens, missões): tabelas referenciadas por FK de usuário casam por slug e
PRESERVAM o PK da produção; as demais são substituídas inteiras com remapeamento de FK.
Ver docs/deploy-sync-conteudo.md.
"""
from collections import defaultdict
import hashlib
import json
import os

from django.apps import apps
from django.core import serializers
from django.db import connection, models, transaction
from django.db.models import Q
from django.db.models.functions import Lower, Trim

# Referenciadas por FK de usuário → casa por slug, PRESERVA PK. (ordem: pais antes)
UPSERT_POR_SLUG = [
    "TbRaca", "TbEssencia", "TbAntecedente", "TbClasse", "TbOpcaojogo",
    "TbMagia", "TbTalento", "TbItemMundano", "TbItemMagico", "TbLinhagem", "TbSubclasse",
    # Catálogo de cosméticos (F1): referenciado por TbUsuarioCosmetico (inventário
    # do usuário) → casa por slug e preserva PK pra não quebrar o inventário.
    "TbCosmetico",
    # Conquistas (F3): referenciada por TbUsuarioConquista (concessão do usuário)
    # → casa por slug e preserva PK. Depois de TbCosmetico (FK recompensa).
    "TbConquista",
]
# Não referenciadas por FK de usuário → substitui inteiras (delete + reinsert).
SUBSTITUI = [
    "TbClassehabilidade", "TbRecursoclasse", "TbAcessoopcao", "TbTracoracial",
    "TbCondicao", "TbIdioma", "TbRegra", "TbRecompensaMestre",
    "TbBestiario", "TbArmadilha",
]
OFFICIAL_REPLACE_MODELS = ["TbBestiario", "TbArmadilha"]

# Mundo/wiki são autorais e editados diretamente em produção. Eles nunca entram
# no merge mecânico, mesmo se um fixture antigo os trouxer por engano.
PRODUCTION_PRESERVED_MODELS = [
    "TbMapLayer", "TbRegiao", "TbTerritorio", "TbOrganizacao",
    "TbMapMarker", "TbMapDesenho",
]
MEMORY_MODELS = [
    "TbPersonagemCacador",
    "TbContentRevision", "TbRuleset", "TbRulesetContent",
    "TbOperacaoRecurso",
    "TbPersonagem", "TbPersonagemAtributoBonus", "TbPersonagemClasse",
    "TbPersonagemEscolha", "TbPersonagemItem", "TbPersonagemMagia",
    "TbPersonagemMagiaAssinatura",
    "TbPersonagemPericia", "TbPersonagemPersonalidade", "TbPersonagemProficiencia",
    "TbPersonagemTreinamento", "TbPersonagemEstado", "TbPersonagemRecurso",
    "TbPersonagemTalento",
    "TbPersonagemAventura", "TbEmprestimoPersonagem", "TbPersonagemRevisao",
    "TbTagLibraryRevision",
    "TbSolicitacaoTranscricao",
    "TbTransacao", "TbTransacaoMestre",
    "TbAventuraMestre", "TbAnuncioItemMagico", "TbCronica", "TbCronicaCurtida",
    "TbCronicaComentario", "TbCronicaDenuncia", "TbCronicaNotificacao", "TbJornal",
    "TbEventoConquista", "TbReiDaColina", "UserProfile",
    # Pedido e retorno financeiro do gateway: dado transacional da producao.
    # Nunca deve entrar em fixture de conteudo nem ser apagado por restauracao.
    "AsaasCheckoutOrder",
    # Textos institucionais/home são editados no admin de cada ambiente. O seed
    # da migration cria a base, mas deploy de catálogo não pisa em ajustes editoriais.
    "TbConteudoEstatico",
    # Inventário de cosméticos (F1): dado de USUÁRIO — nunca sincroniza, e protege
    # cosméticos referenciados contra deleção por tombstone (_memory_references).
    "TbUsuarioCosmetico",
    # Concessão de conquistas (F3): dado de USUÁRIO — nunca sincroniza, e protege
    # conquistas referenciadas contra deleção por tombstone.
    "TbUsuarioConquista",
    # Social do perfil (curtir/seguir): relação user↔user criada pelos jogadores em
    # produção. É memória pura — jamais entra em CONTENT_MODELS.
    "TbPerfilCurtida", "TbPerfilSeguidor",
    "SocialCreditWallet", "SocialCreditEntry", "SocialCreditPolicy",
    "SocialCreditReaderRecognition", "SocialCreditRedemption",
]
CONTENT_MODELS = UPSERT_POR_SLUG + SUBSTITUI
RESTORE_GUARDED_MODELS = CONTENT_MODELS + PRODUCTION_PRESERVED_MODELS
DELETIONS_PATH = os.path.join("home", "content_deletions.json")
RENAMES_PATH = os.path.join("home", "content_renames.json")


def _m(nome):
    return apps.get_app_config("home").get_model(nome)


def _fk_fields(model):
    return {f.attname: f.related_model for f in model._meta.get_fields()
            if isinstance(f, models.ForeignKey)}


def _label(model):
    return "home." + model.__name__.lower()


def contagem(nomes):
    return {nm: _m(nm).objects.count() for nm in nomes}


def estado_modelos(nomes):
    """Retorna contagem e assinatura determinística de cada tabela."""
    estado = {}
    for nome in nomes:
        M = _m(nome)
        queryset = M.objects.all().order_by(M._meta.pk.name)
        payload = serializers.serialize("json", queryset).encode("utf-8")
        estado[nome] = {
            "count": queryset.count(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    return estado


def estado_conteudo_comunitario():
    """Assina só bestiário/armadilhas criados na produção pela comunidade."""
    estado = {}
    for nome in OFFICIAL_REPLACE_MODELS:
        M = _m(nome)
        queryset = M.objects.filter(
            Q(comunidade=True) | Q(autor__isnull=False)
        ).order_by(M._meta.pk.name)
        payload = serializers.serialize("json", queryset).encode("utf-8")
        estado[nome] = {
            "count": queryset.count(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    return estado


def _load_content_deletions():
    if not os.path.exists(DELETIONS_PATH):
        return {}
    with open(DELETIONS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {}
    return {str(model): [str(slug) for slug in slugs if slug]
            for model, slugs in data.items() if isinstance(slugs, list)}


def _load_content_renames():
    """Carrega renomeacoes de chaves naturais que devem preservar o PK da prod."""
    if not os.path.exists(RENAMES_PATH):
        return {}
    with open(RENAMES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("content_renames.json deve conter um objeto por modelo.")

    renames = {}
    for model_name, mapping in data.items():
        if model_name not in UPSERT_POR_SLUG:
            raise ValueError(
                "Renomeacao de slug so e permitida em modelos de upsert: %s"
                % model_name
            )
        if not isinstance(mapping, dict):
            raise ValueError(
                "Renomeacoes de %s devem ser um objeto {slug_antigo: slug_novo}."
                % model_name
            )
        normalized = {}
        targets = set()
        for old_slug, new_slug in mapping.items():
            old_slug = str(old_slug).strip()
            new_slug = str(new_slug).strip()
            if not old_slug or not new_slug or old_slug == new_slug:
                raise ValueError(
                    "Renomeacao de slug invalida em %s: %r -> %r"
                    % (model_name, old_slug, new_slug)
                )
            if new_slug in targets:
                raise ValueError(
                    "Mais de um slug antigo aponta para %s.%s"
                    % (model_name, new_slug)
                )
            normalized[old_slug] = new_slug
            targets.add(new_slug)
        renames[model_name] = normalized
    return renames


def _memory_references(obj):
    refs = []
    target_model = obj._meta.model
    for model_name in MEMORY_MODELS:
        M = _m(model_name)
        for field in M._meta.fields:
            if not isinstance(field, models.ForeignKey) or field.related_model != target_model:
                continue
            count = M.objects.filter(**{field.attname: obj.pk}).count()
            if count:
                refs.append((model_name, field.name, count))
    return refs


def inspect_content_deletions():
    """Read-only status of explicit tombstones against the connected database."""
    rows = []
    for model_name, slugs in _load_content_deletions().items():
        for slug in slugs:
            if model_name not in UPSERT_POR_SLUG:
                rows.append((model_name, slug, 'invalid_model', []))
                continue
            obj = _m(model_name).objects.filter(slug=slug).first()
            if obj is None:
                rows.append((model_name, slug, 'absent', []))
                continue
            refs = _memory_references(obj)
            rows.append((model_name, slug, 'blocked' if refs else 'would_delete', refs))
    return rows


def _preserve_battle_familiar_identity(spells, content_renames):
    """Resolve somente Battle Familiar por EN, preservando PK e slug do banco.

    Executado dentro da transação, antes de qualquer upsert: nenhuma outra linha
    da fixture pode disputar a identidade/slug. Slugs vivos também são tokens de
    itens adquiridos e não devem mudar quando apenas a tradução é atualizada.
    """
    incoming = [spell for spell in spells
                if (spell.nome_ingles or '').strip().casefold() == 'battle familiar']
    if not incoming:
        return
    if len(incoming) != 1:
        raise ValueError('Battle Familiar: identidade EN duplicada no fixture.')
    target = incoming[0]
    M = _m('TbMagia')
    matches = list(M.objects.select_for_update().annotate(
        battle_identity=Lower(Trim('nome_ingles')),
    ).filter(battle_identity='battle familiar'))
    if len(matches) > 1:
        raise ValueError('Battle Familiar: identidade EN duplicada no banco.')
    existing = matches[0] if matches else None
    renames = dict(content_renames.get('TbMagia', {}))
    protected_slugs = {target.slug}
    protected_slugs.update(old for old, new in renames.items() if new == target.slug)
    if existing:
        protected_slugs.add(existing.slug)
        if existing.slug in renames and renames[existing.slug] != target.slug:
            raise ValueError('Battle Familiar: rename existente aponta para outro destino.')
    if target.slug in renames and renames[target.slug] != target.slug:
        raise ValueError('Battle Familiar: slug de destino também é origem de outro rename.')
    for candidate in M.objects.select_for_update().filter(slug__in=protected_slugs):
        if existing is None or candidate.pk != existing.pk:
            raise ValueError('Battle Familiar: colisão de slug com outra identidade.')
    if any(spell is not target and spell.slug in protected_slugs for spell in spells):
        raise ValueError('Battle Familiar: outro registro do fixture disputa o slug.')
    if existing:
        target.slug = existing.slug


def sincronizar_conteudo(fixture_text, *, allow_content_deletions=False):
    """Aplica o fixture de conteúdo (texto JSON serializado pelo Django) por chave
    natural. Retorna um relatório dict: {pass1, pass2, mem_antes, mem_depois, mem_ok}.
    Tudo numa transação — se algo falhar, faz rollback."""
    por_modelo = defaultdict(list)
    for d in serializers.deserialize("json", fixture_text):
        por_modelo[_label(d.object._meta.model)].append(d.object)

    if not allow_content_deletions:
        planned = ["%s.%s" % (name, slug) for name, slug, status, _refs
                   in inspect_content_deletions() if status == 'would_delete']
        if planned:
            raise ValueError('Deleção explícita de conteúdo exige autorização operacional: %s'
                             % ', '.join(planned))

    remap = defaultdict(dict)

    def remapear_fks(obj):
        for attname, alvo in _fk_fields(obj._meta.model).items():
            val = getattr(obj, attname)
            if val is None:
                continue
            mp = remap.get(_label(alvo))
            if mp is not None and val in mp:
                setattr(obj, attname, mp[val])

    content_renames = _load_content_renames()
    rel = {
        "pass1": [], "pass2": [], "pass2_skipped": [],
        "renames": [], "deletions": [],
    }

    with transaction.atomic():
        _preserve_battle_familiar_identity(
            por_modelo.get('home.tbmagia', []), content_renames)
        mem_estado_antes = estado_modelos(MEMORY_MODELS)
        prod_estado_antes = estado_modelos(PRODUCTION_PRESERVED_MODELS)
        comunidade_estado_antes = estado_conteudo_comunitario()

        # PASSO 1: upsert por slug (preserva PK da produção)
        for nome in UPSERT_POR_SLUG:
            M = _m(nome)
            campos = [f.attname for f in M._meta.fields if not f.primary_key]
            legacy_by_target = defaultdict(list)
            for old_slug, new_slug in content_renames.get(nome, {}).items():
                legacy_by_target[new_slug].append(old_slug)
            up = ins = 0
            for obj in por_modelo.get(_label(M), []):
                dev_pk = obj.pk
                remapear_fks(obj)
                prod = M.objects.filter(slug=obj.slug).first()
                legacy_slugs = legacy_by_target.get(obj.slug, [])
                legacy_matches = list(M.objects.filter(slug__in=legacy_slugs))
                if prod and legacy_matches:
                    raise ValueError(
                        "%s possui simultaneamente o slug canonico %s e legado(s) %s; "
                        "merge abortado para evitar duplicidade."
                        % (nome, obj.slug, ", ".join(
                            sorted(item.slug for item in legacy_matches)))
                    )
                if len(legacy_matches) > 1:
                    raise ValueError(
                        "%s possui mais de um registro legado para %s: %s"
                        % (nome, obj.slug, ", ".join(
                            sorted(item.slug for item in legacy_matches)))
                    )
                if not prod and legacy_matches:
                    prod = legacy_matches[0]
                if prod:
                    old_slug = prod.slug
                    for c in campos:
                        setattr(prod, c, getattr(obj, c))
                    prod.save()
                    remap[_label(M)][dev_pk] = prod.pk
                    if old_slug != obj.slug:
                        rel["renames"].append(
                            (nome, old_slug, obj.slug, prod.pk)
                        )
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
            novos = por_modelo.get(_label(M), [])
            if _label(M) not in por_modelo:
                rel["pass2_skipped"].append((nome, "modelo ausente no fixture; tabela preservada"))
                continue
            if nome in OFFICIAL_REPLACE_MODELS:
                invalidos = [
                    obj for obj in novos
                    if obj.comunidade or obj.autor_id is not None
                ]
                if invalidos:
                    raise ValueError(
                        "%s contém %d registro(s) comunitário(s); o merge aceita "
                        "apenas conteúdo oficial desse modelo." % (nome, len(invalidos))
                    )
                slugs = [obj.slug for obj in novos]
                M.objects.filter(
                    comunidade=False, autor__isnull=True,
                ).exclude(slug__in=slugs).delete()

                campos = [
                    field.attname for field in M._meta.fields
                    if not field.primary_key
                ]
                for obj in novos:
                    remapear_fks(obj)
                    existente = M.objects.filter(slug=obj.slug).first()
                    if existente:
                        if existente.comunidade or existente.autor_id is not None:
                            raise ValueError(
                                "%s oficial colide com slug comunitário da produção: %s"
                                % (nome, obj.slug)
                            )
                        for campo in campos:
                            setattr(existente, campo, getattr(obj, campo))
                        existente.save()
                    else:
                        # O PK da dev pode colidir com um registro comunitário.
                        obj.pk = None
                        obj.save(force_insert=True)
            else:
                M.objects.all().delete()
                for obj in novos:
                    remapear_fks(obj)
                    obj.save(force_insert=True)
            rel["pass2"].append((nome, len(novos)))

        # PASSO 2.5: deleções explícitas de conteúdo removido da dev.
        for nome, slugs in _load_content_deletions().items():
            if nome not in UPSERT_POR_SLUG:
                rel["deletions"].append((nome, 0, len(slugs), "modelo nao permitido para tombstone"))
                continue
            M = _m(nome)
            deleted = blocked = 0
            details = []
            for slug in slugs:
                obj = M.objects.filter(slug=slug).first()
                if not obj:
                    continue
                refs = _memory_references(obj)
                if refs:
                    blocked += 1
                    details.append("%s referenciado por %s" % (
                        slug,
                        ", ".join("%s.%s=%d" % ref for ref in refs),
                    ))
                    continue
                if not allow_content_deletions:
                    raise ValueError('Deleção explícita de conteúdo exige autorização operacional: %s.%s'
                                     % (nome, slug))
                obj.delete()
                deleted += 1
            rel["deletions"].append((nome, deleted, blocked, "; ".join(details)))

        # PASSO 3: realinha sequences (Postgres)
        if connection.vendor == "postgresql":
            from io import StringIO
            from django.core.management import call_command
            buf = StringIO()
            call_command("sqlsequencereset", "home", stdout=buf)
            # O backend PostgreSQL envolve o script em BEGIN/COMMIT. Aqui ja
            # estamos dentro de transaction.atomic(); executar esses comandos
            # encerraria a transacao externa e invalidaria o savepoint usado
            # pela simulacao do restore.
            sql = "\n".join(
                line for line in buf.getvalue().splitlines()
                if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
            ).strip()
            if sql:
                with connection.cursor() as cur:
                    cur.execute(sql)

        mem_estado_depois = estado_modelos(MEMORY_MODELS)
        prod_estado_depois = estado_modelos(PRODUCTION_PRESERVED_MODELS)
        comunidade_estado_depois = estado_conteudo_comunitario()
        if mem_estado_antes != mem_estado_depois:
            raise RuntimeError(
                "Merge abortado: dados de usuário/personagem foram alterados."
            )
        if prod_estado_antes != prod_estado_depois:
            raise RuntimeError(
                "Merge abortado: dados de mapa/wiki da produção foram alterados."
            )
        if comunidade_estado_antes != comunidade_estado_depois:
            raise RuntimeError(
                "Merge abortado: bestiário/armadilhas da comunidade foram alterados."
            )

    rel["mem_antes"] = {
        nome: data["count"] for nome, data in mem_estado_antes.items()
    }
    rel["mem_depois"] = {
        nome: data["count"] for nome, data in mem_estado_depois.items()
    }
    rel["mem_estado_antes"] = mem_estado_antes
    rel["mem_estado_depois"] = mem_estado_depois
    rel["mem_ok"] = mem_estado_antes == mem_estado_depois
    rel["prod_preservada_antes"] = prod_estado_antes
    rel["prod_preservada_depois"] = prod_estado_depois
    rel["prod_preservada_ok"] = prod_estado_antes == prod_estado_depois
    rel["comunidade_antes"] = comunidade_estado_antes
    rel["comunidade_depois"] = comunidade_estado_depois
    rel["comunidade_ok"] = comunidade_estado_antes == comunidade_estado_depois
    return rel


def relatorio_texto(rel):
    """Formata o relatório de sincronização como texto legível."""
    linhas = ["== Conteúdo referenciado (upsert por slug, preserva PK) =="]
    for nome, up, ins in rel["pass1"]:
        linhas.append("  %-20s %d atualizados, %d inseridos" % (nome, up, ins))
    if rel.get("renames"):
        linhas.append("== Slugs renomeados (PK preservado) ==")
        for nome, old_slug, new_slug, pk in rel["renames"]:
            linhas.append(
                "  %-20s %s -> %s (pk=%s)"
                % (nome, old_slug, new_slug, pk)
            )
    linhas.append("== Demais tabelas (substituídas inteiras) ==")
    for nome, n in rel["pass2"]:
        linhas.append("  %-20s %d registros" % (nome, n))
    if rel.get("pass2_skipped"):
        linhas.append("== Tabelas preservadas por ausência no fixture ==")
        for nome, motivo in rel["pass2_skipped"]:
            linhas.append("  %-20s %s" % (nome, motivo))
    if rel.get("deletions"):
        linhas.append("== Deleções explícitas de conteúdo ==")
        for nome, deleted, blocked, details in rel["deletions"]:
            linhas.append("  %-20s %d removidos, %d bloqueados" % (nome, deleted, blocked))
            if details:
                linhas.append("    %s" % details)
    if rel["mem_ok"]:
        linhas.append("MEMÓRIA INTACTA: %d tabelas com contagem e conteúdo idênticos." % len(rel["mem_antes"]))
    else:
        mudou = {k: (rel["mem_antes"][k], rel["mem_depois"][k])
                 for k in rel["mem_antes"] if rel["mem_antes"][k] != rel["mem_depois"][k]}
        linhas.append("ATENÇÃO: memória mudou! %s" % mudou)
    if rel.get("prod_preservada_ok"):
        linhas.append("MAPA/WIKI INTACTOS: %d tabelas preservadas por assinatura." % len(rel["prod_preservada_antes"]))
    if rel.get("comunidade_ok"):
        linhas.append("CONTEÚDO COMUNITÁRIO INTACTO: bestiário e armadilhas preservados.")
    return "\n".join(linhas)
