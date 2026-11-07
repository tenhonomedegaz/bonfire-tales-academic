# -*- coding: utf-8 -*-
"""Normaliza identificadores mecanicos das tags_json para snake_case."""
from django.core.management.base import BaseCommand

from home.tag_engine import normalize_tag_identifier_names


def _model_specs():
    from home.models import (
        TbAntecedente,
        TbBestiario,
        TbClasse,
        TbClassehabilidade,
        TbItemMagico,
        TbItemMundano,
        TbMagia,
        TbOpcaojogo,
        TbTalento,
        TbTracoracial,
    )
    return [
        ("classe", TbClasse, "id_classe"),
        ("classe-hab", TbClassehabilidade, "id_habilidade"),
        ("talento", TbTalento, "id_talento"),
        ("opcao", TbOpcaojogo, "id_opcao"),
        ("traco", TbTracoracial, "id_traco"),
        ("antecedente", TbAntecedente, "id_antecedente"),
        ("magia", TbMagia, "id_magia"),
        ("bestiario", TbBestiario, "id_criatura"),
        ("item-mundano", TbItemMundano, "id_item"),
        ("item-magico", TbItemMagico, "id_item"),
    ]


def _normalize_tags(tags):
    if not tags:
        return tags, 0
    if isinstance(tags, str):
        normalized = normalize_tag_identifier_names(tags)
        return normalized, int(normalized != tags)
    if not isinstance(tags, list):
        return tags, 0
    changed = 0
    out = []
    for item in tags:
        if isinstance(item, str):
            normalized = normalize_tag_identifier_names(item)
            changed += int(normalized != item)
            out.append(normalized)
        else:
            out.append(item)
    return out, changed


class Command(BaseCommand):
    help = "Troca hifen por underscore em nomes mecanicos de tags_json, preservando '-' matematico."

    def add_arguments(self, parser):
        parser.add_argument("--model", default=None,
                            help="classe | classe-hab | talento | opcao | traco | antecedente | magia | bestiario | item-mundano | item-magico")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--max-examples", type=int, default=12)

    def handle(self, *args, **opt):
        only = opt.get("model")
        dry = bool(opt.get("dry_run"))
        max_examples = int(opt.get("max_examples") or 0)
        rows = lines = 0
        examples = []
        for key, model, pk_name in _model_specs():
            if only and only != key:
                continue
            for obj in model.objects.all().only(pk_name, "nome", "tags_json"):
                new_tags, changed = _normalize_tags(getattr(obj, "tags_json", None))
                if not changed:
                    continue
                rows += 1
                lines += changed
                if len(examples) < max_examples:
                    label = getattr(obj, "nome", None) or str(getattr(obj, pk_name))
                    examples.append(f"{key}:{label} ({changed} linha(s))")
                if not dry:
                    obj.tags_json = new_tags
                    obj.save(update_fields=["tags_json"])
        mode = "DRY-RUN" if dry else "APLICADO"
        self.stdout.write(f"{mode}: registros alteraveis={rows} linhas normalizadas={lines}")
        for ex in examples:
            self.stdout.write(f"  - {ex}")
