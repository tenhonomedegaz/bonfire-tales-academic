# -*- coding: utf-8 -*-
"""Remove fontes visiveis do conteudo final.

Fonte/source/page sao referencias de importacao. Nao devem aparecer em itens ou
criaturas no conteudo consumido pelo site/ficha.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction


FONTE_LINE_RE = re.compile(r"^\s*-\s*\*\*Fonte:\*\*.*(?:\r?\n)?", re.M)


def clean_markdown(text):
    if not text:
        return text
    text = FONTE_LINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_statblock(sb):
    if not isinstance(sb, dict):
        return sb, False
    changed = False
    out = dict(sb)
    for key in ("source", "source_en", "page"):
        if key in out:
            out.pop(key, None)
            changed = True
    return out, changed


class Command(BaseCommand):
    help = "Remove fonte/source/page de itens e criaturas."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        from home.models import TbBestiario, TbItemMundano

        updates = []
        for obj in TbItemMundano.objects.all():
            changes = {}
            md = clean_markdown(obj.descricao_markdown)
            if md != (obj.descricao_markdown or "").strip():
                changes["descricao_markdown"] = md
            if changes:
                updates.append((obj, changes))

        for obj in TbBestiario.objects.all():
            changes = {}
            md = clean_markdown(obj.descricao_markdown)
            if md != (obj.descricao_markdown or "").strip():
                changes["descricao_markdown"] = md
            sb, changed = clean_statblock(obj.statblock_json)
            if changed:
                changes["statblock_json"] = sb
            if changes:
                updates.append((obj, changes))

        if opts["apply"]:
            with transaction.atomic():
                for obj, changes in updates:
                    for field, value in changes.items():
                        setattr(obj, field, value)
                    obj.save(update_fields=list(changes.keys()))

        self.stdout.write(self.style.SUCCESS(
            "%s updates=%d" % ("APPLY" if opts["apply"] else "PREVIEW", len(updates))
        ))
