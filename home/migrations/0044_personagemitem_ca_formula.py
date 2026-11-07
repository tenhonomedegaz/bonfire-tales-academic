# -*- coding: utf-8 -*-
"""Converte o snapshot de CA dos itens equipados (TbPersonagemItem.tags_json) do formato
antigo 'ca=<int>' [+ 'dex-ca-max:N'] para a formula canonica, e remove dex-ca-max:
  sem dex-ca-max     -> ca=<base>+dex_mod          (leve)
  dex-ca-max:N (>0)  -> ca=<base>+min(dex_mod,N)   (media)
  dex-ca-max:0       -> ca=<base>                  (pesada)
Necessario porque o motor passou a AVALIAR ca=<formula> (dex-ca-max deixou de existir)."""
import re
from django.db import migrations

_CA = re.compile(r"^\s*ca\s*=\s*([0-9]+)\s*$", re.I)
_DX = re.compile(r"^\s*dex-ca-max\s*:\s*([0-9]+)", re.I)


def to_formula(apps, schema_editor):
    PI = apps.get_model("home", "TbPersonagemItem")
    for it in PI.objects.all():
        tags = it.tags_json or []
        base = cap = None
        for t in tags:
            if not isinstance(t, str):
                continue
            m = _CA.match(t)
            if m:
                base = int(m.group(1))
            m = _DX.match(t)
            if m:
                cap = int(m.group(1))
        if base is None:
            continue  # sem CA de armadura (arma/escudo/consumivel)
        if cap is None:
            formula = "%d+dex_mod" % base
        elif cap == 0:
            formula = "%d" % base
        else:
            formula = "%d+min(dex_mod,%d)" % (base, cap)
        novo = [t for t in tags if isinstance(t, str) and not _CA.match(t) and not _DX.match(t)]
        novo.insert(0, "ca=%s" % formula)
        if novo != tags:
            it.tags_json = novo
            it.save(update_fields=["tags_json"])


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("home", "0043_remove_tbitemmundano_ca_remove_tbitemmundano_ca_base_and_more")]
    operations = [migrations.RunPython(to_formula, reverse)]
