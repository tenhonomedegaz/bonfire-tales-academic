# -*- coding: utf-8 -*-
"""Aplica a classificacao revisada de equipabilidade dos itens magicos."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Audita slots de itens magicos a partir de scratch/equipaveis_batch_*.json. "
        "Sem --apply apenas relata; confianca baixa nunca e aplicada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Persiste as alteracoes validadas. O padrao e dry-run.")
        parser.add_argument(
            "--log",
            default="scratch/equipaveis_aplicacao_log.json",
            help="Arquivo JSON do log antes/depois.")

    def handle(self, *args, **options):
        from home.models import TbItemMagico

        root = Path(settings.BASE_DIR)
        paths = sorted((root / "scratch").glob("equipaveis_batch_*.json"))
        if not paths:
            raise CommandError("Nenhum scratch/equipaveis_batch_*.json encontrado.")

        valid_slots = {value for value, _label in TbItemMagico.SLOT_CHOICES}
        decisions = {}
        for path in paths:
            try:
                rows = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError(f"Falha ao ler {path}: {exc}") from exc
            if not isinstance(rows, list):
                raise CommandError(f"{path} precisa conter uma lista JSON.")
            for row in rows:
                if not isinstance(row, dict) or not row.get("slug"):
                    raise CommandError(f"Registro invalido em {path}: {row!r}")
                slug = str(row["slug"]).strip()
                if slug in decisions:
                    raise CommandError(f"Slug duplicado nos lotes: {slug}")
                slot = str(row.get("slot_alvo") or "").strip()
                if slot not in valid_slots:
                    raise CommandError(f"Slot invalido para {slug}: {slot!r}")
                decisions[slug] = row

        items = {
            item.slug: item
            for item in TbItemMagico.objects.filter(slug__in=decisions)
        }
        missing = sorted(set(decisions) - set(items))
        if missing:
            raise CommandError(
                "Slugs inexistentes no banco: " + ", ".join(missing[:20]))

        changes = []
        holds = []
        unchanged = 0
        for slug, row in sorted(decisions.items()):
            item = items[slug]
            confidence = str(row.get("confianca") or "").strip().lower()
            if confidence not in {"alta", "media"}:
                holds.append({
                    "slug": slug,
                    "slot_atual": item.slot,
                    "slot_proposto": row["slot_alvo"],
                    "confianca": confidence or "nao_informada",
                    "motivo": row.get("motivo") or "",
                })
                continue
            target = row["slot_alvo"]
            if item.slot == target:
                unchanged += 1
                continue
            if item.slot != "empunhado":
                raise CommandError(
                    f"{slug} mudou fora da auditoria: slot atual={item.slot!r}, "
                    f"esperado='empunhado'.")
            changes.append({
                "tabela": TbItemMagico._meta.db_table,
                "pk": item.pk,
                "slug": slug,
                "campo": "slot",
                "antes": item.slot,
                "depois": target,
                "confianca": confidence,
                "motivo": row.get("motivo") or "",
            })

        mode = "APLICACAO" if options["apply"] else "DRY-RUN"
        self.stdout.write(
            f"{mode}: lotes={len(paths)} decisoes={len(decisions)} "
            f"alteracoes={len(changes)} sem_mudanca={unchanged} holds={len(holds)}")
        for hold in holds:
            self.stdout.write(
                f"  HOLD {hold['slug']}: {hold['slot_atual']} -> "
                f"{hold['slot_proposto']} ({hold['confianca']})")

        if not options["apply"]:
            return

        with transaction.atomic():
            for change in changes:
                item = items[change["slug"]]
                item.slot = change["depois"]
                item.save(update_fields=["slot"])

        log_path = root / options["log"]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "aplicado": True,
            "arquivos": [str(path.relative_to(root)) for path in paths],
            "alteracoes": changes,
            "holds": holds,
        }
        log_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"{len(changes)} alteracoes aplicadas; log: {log_path}"))
