# -*- coding: utf-8 -*-
"""Valida TODAS as tags_json do banco contra a biblioteca (home/tag_library.json),
no espírito do Excel: aponta exatamente a fórmula errada.

    manage.py validate_tags                  # banco inteiro + lint da biblioteca
    manage.py validate_tags --lint           # só audita a biblioteca
    manage.py validate_tags --model talento  # só um catálogo
    manage.py validate_tags --errors-only    # só ERROS (#REF!/desbalanceado/catálogo)
    manage.py validate_tags --no-db          # pula checagem de referências (#REF!)
    manage.py validate_tags                  # tambem falha nomes mecanicos com hifen
    manage.py validate_tags --allow-legacy-hyphen  # auditoria temporaria de legado
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from home.tag_engine import Library, DataIndex, validate_tags_json, ERROR, WARN, INFO


def _iter_models(only=None):
    """Gera (chave, label, tags_json) para cada registro com a coluna tags_json."""
    specs = []

    def add(key, importer, in_default=True):
        # item-magico fica FORA da varredura default (metadados de loja —
        # tipo/item/raridade/slot/loja — não são DSL e geram ruído); continua
        # acessível sob demanda via `--model item-magico`.
        if only:
            if only != key:
                return
        elif not in_default:
            return
        specs.append((key, importer))

    def classe_hab():
        from home.models import TbClassehabilidade
        for h in TbClassehabilidade.objects.select_related("id_classe").all():
            cl = getattr(h, "id_classe", None)
            cn = getattr(cl, "nome", "?") if cl else "?"
            yield (f"{cn}/{h.nome}", h.tags_json)

    def talento():
        from home.models import TbTalento
        for t in TbTalento.objects.all():
            yield (t.nome, t.tags_json)

    def opcao():
        from home.models import TbOpcaojogo
        for o in TbOpcaojogo.objects.all():
            yield (f"{o.tipo}/{o.nome}", o.tags_json)

    def traco():
        from home.models import TbTracoracial
        for t in TbTracoracial.objects.all():
            yield (t.nome, t.tags_json)

    def classe_meta():
        from home.models import TbClasse
        for c in TbClasse.objects.all():
            yield (c.nome, getattr(c, "tags_json", None))

    def antecedente():
        from home.models import TbAntecedente
        for a in TbAntecedente.objects.all():
            yield (a.nome, a.tags_json)

    def magia():
        from home.models import TbMagia
        for m in TbMagia.objects.all():
            yield (m.nome, m.tags_json)

    def bestiario():
        from home.models import TbBestiario
        for b in TbBestiario.objects.all():
            yield (b.nome, b.tags_json)

    def item_mundano():
        from home.models import TbItemMundano
        for item in TbItemMundano.objects.all():
            yield (item.nome, item.tags_json)

    def item_magico():
        from home.models import TbItemMagico
        for item in TbItemMagico.objects.all():
            yield (item.nome, item.tags_json)

    add("classe-hab", classe_hab)
    add("talento", talento)
    add("opcao", opcao)
    add("traco", traco)
    add("antecedente", antecedente)
    add("classe", classe_meta)
    add("magia", magia)
    add("bestiario", bestiario)
    add("item-mundano", item_mundano)
    add("item-magico", item_magico, in_default=False)
    return specs


class Command(BaseCommand):
    help = "Valida as tags_json do banco contra home/tag_library.json (estilo Excel)."

    def add_arguments(self, parser):
        parser.add_argument("--lint", action="store_true", help="Só audita a biblioteca.")
        parser.add_argument("--model", default=None,
                            help="classe-hab | talento | opcao | traco | classe | antecedente | magia | bestiario | item-mundano | item-magico")
        parser.add_argument("--errors-only", action="store_true")
        parser.add_argument("--no-db", action="store_true", help="Não checa referências (#REF!).")
        parser.add_argument("--allow-legacy-hyphen", action="store_true",
                            help="Modo de auditoria legado: nao falha identificadores com hifen.")
        parser.add_argument("--strict-names", action="store_true",
                            help="Compatibilidade: strict_names agora e padrao.")
        parser.add_argument("--max", type=int, default=40, help="Máx. de itens listados por seção.")

    def handle(self, *args, **opt):
        lib = Library()

        # ── lint da biblioteca ──────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== LINT da biblioteca (tag_library.json) ==="))
        lint = lib.lint()
        for lvl, msg in lint:
            self._line(lvl, msg)
        if not lint:
            self.stdout.write("  (sem observações)")
        if opt["lint"]:
            return

        # ── índice do banco p/ #REF! ────────────────────────────────────
        data = None
        if not opt["no_db"]:
            self.stdout.write(self.style.MIGRATE_HEADING("\n=== Indexando banco (referências) ==="))
            data = DataIndex.build()
            self.stdout.write(
                f"  abilities={len(data.ability_names)} spells={len(data.spell_slugs)} "
                f"recursos={len(data.resources)} maestrias={len(data.masteries)} "
                f"opções={len(data.opcao_tipos)} classes={len(data.classe_slugs)} "
                f"bestiário={len(data.bestiary_slugs)}")

        # ── varre os modelos ────────────────────────────────────────────
        by_level = Counter()
        by_code = Counter()
        unknown = defaultdict(lambda: [0, []])      # head -> [count, exemplos]
        errors = []                                 # (label, Diagnostic)
        warns = []
        n_rows = n_tagged = n_tags = 0
        per_model = Counter()

        for key, importer in _iter_models(opt["model"]):
            for label, tags in importer():
                n_rows += 1
                if not tags:
                    continue
                n_tagged += 1
                n_tags += len(tags) if isinstance(tags, list) else 1
                full = f"{key}:{label}"
                for d in validate_tags_json(tags, lib, data, strict_names=not opt["allow_legacy_hyphen"]):
                    by_level[d.level] += 1
                    by_code[d.code] += 1
                    per_model[key] += 1
                    if d.code == "verbo-desconhecido":
                        slot = unknown[d.fragment]
                        slot[0] += 1
                        if len(slot[1]) < 3 and full not in slot[1]:
                            slot[1].append(full)
                    elif d.level == ERROR:
                        errors.append((full, d))
                    elif d.level == WARN:
                        warns.append((full, d))

        # ── relatório ───────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== VALIDAÇÃO DAS TAGS (banco) ==="))
        self.stdout.write(f"  registros={n_rows}  com tags={n_tagged}  linhas de tag={n_tags}")

        self.stdout.write(self.style.MIGRATE_HEADING("\n-- ERROS (#REF! / desbalanceado / catálogo) --"))
        if errors:
            for full, d in errors[: opt["max"]]:
                self._line(d.level, f"[{d.code}] {full}\n        -> {d.message}\n        ... {d.fragment}")
            if len(errors) > opt["max"]:
                self.stdout.write(f"  (+{len(errors) - opt['max']} erros omitidos)")
        else:
            self.stdout.write(self.style.SUCCESS("  nenhum erro — todas as referências e delimitadores OK"))

        if not opt["errors_only"]:
            self.stdout.write(self.style.MIGRATE_HEADING("\n-- VERBOS/ESCOPOS DESCONHECIDOS (frequência) --"))
            if unknown:
                for head, (count, ex) in sorted(unknown.items(), key=lambda kv: -kv[1][0]):
                    self.stdout.write(self._safe(f"  {head:<28} x{count:<4} ex: {', '.join(ex)}"))
            else:
                self.stdout.write(self.style.SUCCESS("  nenhum — todo verbo usado está na biblioteca"))

            self.stdout.write(self.style.MIGRATE_HEADING("\n-- OUTROS AVISOS (catálogo/padrão) --"))
            other = [(f, d) for f, d in warns if d.code != "verbo-desconhecido"]
            for full, d in other[: opt["max"]]:
                self._line(d.level, f"[{d.code}] {full} -> {d.message}  ({d.fragment})")
            if not other:
                self.stdout.write("  (nenhum)")
            elif len(other) > opt["max"]:
                self.stdout.write(f"  (+{len(other) - opt['max']} avisos omitidos)")

        self.stdout.write(self.style.MIGRATE_HEADING("\n-- RESUMO --"))
        self.stdout.write(f"  ERROR={by_level[ERROR]}  WARN={by_level[WARN]}  INFO={by_level[INFO]}")
        self.stdout.write("  por código: " + ", ".join(f"{c}={n}" for c, n in by_code.most_common()))

    def _line(self, level, msg):
        style = {"ERROR": self.style.ERROR, "WARN": self.style.WARNING,
                 "INFO": self.style.NOTICE}.get(level, self.style.NOTICE)
        self.stdout.write(self._safe(style(f"  [{level}] ") + msg))

    def _safe(self, msg):
        enc = getattr(getattr(self.stdout, "_out", None), "encoding", None) or "utf-8"
        return str(msg).encode(enc, "replace").decode(enc)
