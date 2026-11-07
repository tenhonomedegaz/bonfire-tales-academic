"""Normaliza o conteudo de conjuracao para o contrato declarativo atual."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.models import TbClasse, TbClassehabilidade, TbRecursoclasse


CONTRACTS = {
    662: (
        "feiticeiro",
        "spellcasting{ability:cha, slots{progression:full}, list:feiticeiro, "
        "mode:known, spell_limit{resource:magias_conhecidas}, "
        "cantrip_limit{resource:truques}, pool:class_list, "
        "swap{event:level_up, max:all}, focus:arcano}",
    ),
    766: (
        "guerreiro",
        "spellcasting{ability:int, slots{progression:third}, list:mago, "
        "mode:known, spell_limit{resource:magias_conhecidas}, "
        "cantrip_limit{resource:truques}, pool:class_list, "
        "swap{event:level_up, max:1}, focus:arma_vinculada}",
    ),
    885: (
        "artifice",
        "spellcasting{ability:int, slots{progression:half}, list:artifice, "
        "mode:prepared, spell_limit{resource:magias_preparadas}, "
        "cantrip_limit{resource:truques}, pool:class_list, focus:ferramentas}",
    ),
    1019: (
        "cacador",
        "spellcasting{ability:int|wis, slots{progression:half}, list:cacador, "
        "mode:prepared, spell_limit{formula:spell_mod+rounddown(classlvl/2)}, "
        "pool:class_list, focus:foco_arcano|ferramentas_artesao}",
    ),
    1086: (
        "clerigo",
        "spellcasting{ability:wis, slots{progression:full}, list:clerigo, "
        "mode:prepared, spell_limit{resource:magias_preparadas}, "
        "cantrip_limit{resource:truques}, pool:class_list, focus:simbolo_sagrado}",
    ),
    1178: (
        "druida",
        "spellcasting{ability:wis, slots{progression:full}, list:druida, "
        "mode:prepared, spell_limit{formula:classlvl+wis_mod}, "
        "cantrip_limit{resource:truques}, pool:class_list, focus:foco_druidico}",
    ),
    1268: (
        "ladino",
        "spellcasting{ability:int, slots{progression:third}, list:mago, "
        "mode:prepared, spell_limit{resource:magias_preparadas}, "
        "cantrip_limit{resource:truques}, pool:class_list, focus:foco_arcano}",
    ),
    1332: (
        "mago",
        "spellcasting{ability:int, slots{progression:full}, list:mago, "
        "mode:prepared, spell_limit{formula:classlvl+int_mod}, "
        "cantrip_limit{resource:truques}, pool:spellbook, "
        "acquire{initial:6, level_up:2, transcribe{source:spell_scroll, "
        "cost_po:50*spell_level, time_hours:2*spell_level}}, focus:spellbook}",
    ),
    1428: (
        "mistico",
        "spellcasting{ability:cha, slots{progression:pact, "
        "resource:pontos_de_misticismo}, list:mistico, mode:known, "
        "spell_limit{resource:magias_conhecidas}, "
        "spell_level_limit{resource:ciclo_de_feiticos}, "
        "cantrip_limit{resource:truques_conhecidos}, pool:class_list, "
        "swap{event:level_up, max:1}, focus:foco_arcano}",
    ),
    1513: (
        "monge",
        "spellcasting{ability:wis, slots{progression:pact, resource:pontos_de_ki}, "
        "list:elemental, pool:class_list, focus:ki}",
    ),
    1626: (
        "paladino",
        "spellcasting{ability:cha, slots{progression:half}, list:paladino, "
        "mode:prepared, spell_limit{resource:magias_preparadas}, "
        "pool:class_list, focus:simbolo_sagrado}",
    ),
    1950: (
        "bardo",
        "spellcasting{ability:cha, slots{progression:full}, list:bardo, "
        "mode:known, spell_limit{resource:magias_conhecidas}, "
        "cantrip_limit{resource:truques}, pool:class_list, "
        "swap{event:level_up, max:all}, focus:instrumento_musical}",
    ),
}


RESOURCE_CHANGES = (
    ("artifice", None, "magias-conhecidas", "magias_preparadas", "Magias Preparadas"),
    ("bardo", None, "magias-conhecidas", "magias_conhecidas", "Magias Conhecidas"),
    ("clerigo", None, "magias-conhecidas", "magias_preparadas", "Magias Preparadas"),
    ("feiticeiro", None, "magias-conhecidas", "magias_conhecidas", "Magias Conhecidas"),
    ("guerreiro", "cavaleiro-arcano", "magias-preparadas", "magias_conhecidas", "Magias Conhecidas"),
    ("ladino", "trilha-do-trapaceiro-arcano", "magias-preparadas", "magias_preparadas", "Magias Preparadas"),
    ("mistico", None, "magias-conhecidas", "magias_conhecidas", "Magias Conhecidas"),
    ("mistico", None, "truques-conhecidos", "truques_conhecidos", "Truques Conhecidos"),
    ("paladino", None, "magias-conhecidas", "magias_preparadas", "Magias Preparadas"),
)


def _replace_declaration(tags, contract):
    result = []
    replaced = False
    for tag in tags or []:
        normalized = str(tag or "").strip().lower().replace(" ", "")
        if normalized == "swap:level_up":
            continue
        if normalized.startswith("spellcasting{") and (
                "slots" in normalized or "lista:" in normalized or "list:" in normalized):
            if not replaced:
                result.append(contract)
                replaced = True
            continue
        result.append(tag)
    if not replaced:
        result.insert(0, contract)
    return result


def _remove_declaration(tags):
    """Remove contratos de conjuracao duplicados do registro da classe.

    A habilidade de Conjuracao e a fonte mecanica. Manter uma segunda declaracao
    na classe faz a ordem dos registros decidir qual regra vence.
    """
    result = []
    for tag in tags or []:
        normalized = str(tag or "").strip().lower().replace(" ", "")
        if normalized == "swap:level_up":
            continue
        if normalized.startswith("spellcasting{") and (
                "slots" in normalized or "lista:" in normalized or "list:" in normalized):
            continue
        result.append(tag)
    return result


def _rewrite_descriptions():
    changes = 0

    def update(pk, replacements):
        nonlocal changes
        feature = TbClassehabilidade.objects.get(pk=pk)
        text = feature.descricao or ""
        new = text
        for old, replacement in replacements:
            new = new.replace(old, replacement)
        if new != text:
            feature.descricao = new
            feature.save(update_fields=["descricao"])
            changes += 1

    update(885, (
        ("##### Magias Conhecidas de 1º Círculo ou Superiores",
         "##### Magias Preparadas de 1º Círculo ou Superiores"),
        ("Você conhece uma lista de magias de **1º círculo ou superiores** que estão disponíveis para você conjurar com esta característica.",
         "Você prepara uma lista de magias de **1º círculo ou superiores** que ficam disponíveis para conjuração com esta característica."),
        ("Ao começar, escolha **duas magias de 1º círculo de Artífice**.",
         "Ao começar, prepare **duas magias de 1º círculo de Artífice**."),
        ("o número de magias em sua lista conhecida aumenta, conforme indicado na coluna de **Magias Conhecidas**",
         "o número de magias que você pode preparar aumenta, conforme indicado na coluna de **Magias Preparadas**"),
        ("na sua lista conhecida corresponda ao valor mostrado na tabela",
         "preparadas corresponda ao valor mostrado na tabela"),
        ("contra o número de magias que você pode conhecer",
         "contra o número de magias que você pode preparar"),
        ("##### Alterando suas Magias Conhecidas", "##### Alterando suas Magias Preparadas"),
        ("poderá alterar sua lista de magias conhecidas", "poderá redefinir sua lista de magias preparadas"),
    ))
    update(662, (
        ("#### Preparando Magias", "#### Magias Conhecidas"),
        ("Você prepara a lista de magias de Feiticeiro disponíveis para conjurar. Para isso, escolha",
         "Você conhece uma lista de magias de Feiticeiro disponíveis para conjurar. Escolha"),
        ("coluna **Magias Preparadas**", "coluna **Magias Conhecidas**"),
        ("sempre tem preparadas", "sempre conhece"),
        ("#### Alterando suas Magias Preparadas", "#### Alterando suas Magias Conhecidas"),
        ("das magias preparadas com esta característica", "das magias conhecidas com esta característica"),
    ))
    update(766, (
        ("#### Magias Preparadas", "#### Magias Conhecidas"),
        ("Você prepara uma lista de magias de Mago igual ao número mostrado na coluna \"Magias Preparadas\" da tabela. As magias preparadas",
         "Você conhece um número de magias de Mago igual ao valor mostrado na coluna \"Magias Conhecidas\" da tabela. As magias conhecidas"),
        ("Magias Preparadas |", "Magias Conhecidas |"),
    ))
    update(1626, (
        ("Para isso, escolha magias da **Lista de Magias de Paladino** em quantidade igual ao seu **modificador de Carisma + metade do seu nível de Paladino** (arredondado para baixo, mínimo de **uma magia**).",
         "Para isso, escolha da **Lista de Magias de Paladino** a quantidade indicada na coluna **Magias Preparadas** da tabela do Paladino."),
    ))
    update(1950, (
        ("pode substituir uma das magias que conhece", "pode substituir qualquer quantidade das magias que conhece"),
    ))
    update(1428, (
        ("\n  **Efeito:**\n", "\n"),
        ("[truques adicionais](tbClassehabilidade, o-celestial, truques-adicionais)",
         "truques adicionais"),
    ))
    return changes


class Command(BaseCommand):
    help = "Retaggeia conjuradores e alinha recursos/textos sem alterar o schema."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        changed_features = 0
        for pk, (class_slug, contract) in CONTRACTS.items():
            feature = TbClassehabilidade.objects.select_related("id_classe").filter(pk=pk).first()
            if feature is None or feature.id_classe.slug != class_slug:
                raise CommandError("Habilidade %s não corresponde à classe %s." % (pk, class_slug))
            tags = _replace_declaration(feature.tags_json, contract)
            if tags != (feature.tags_json or []):
                feature.tags_json = tags
                feature.save(update_fields=["tags_json"])
                changed_features += 1

        # O Paladino era o unico registro com o contrato repetido na classe e na
        # habilidade. A habilidade 1626 passa a ser a unica fonte da regra.
        changed_classes = 0
        paladin = TbClasse.objects.get(slug="paladino")
        tags = _remove_declaration(paladin.tags_json)
        if tags != (paladin.tags_json or []):
            paladin.tags_json = tags
            paladin.save(update_fields=["tags_json"])
            changed_classes += 1

        changed_resources = 0
        for class_slug, subclass_slug, old_slug, new_slug, name in RESOURCE_CHANGES:
            resources = TbRecursoclasse.objects.filter(id_classe__slug=class_slug, slug=old_slug)
            resources = resources.filter(
                id_subclasse__slug=subclass_slug) if subclass_slug else resources.filter(
                    id_subclasse__isnull=True)
            for resource in resources:
                resource.slug = new_slug
                resource.nome = name
                resource.save(update_fields=["slug", "nome"])
                changed_resources += 1

        changed_descriptions = _rewrite_descriptions()
        if options["check"]:
            transaction.set_rollback(True)
        suffix = " (simulação)" if options["check"] else ""
        self.stdout.write(self.style.SUCCESS(
            "Conjuração normalizada%s: %d habilidades, %d classes, %d recursos, "
            "%d descrições." % (
                suffix, changed_features, changed_classes, changed_resources,
                changed_descriptions)))
