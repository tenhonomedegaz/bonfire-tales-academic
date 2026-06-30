# -*- coding: utf-8 -*-
"""Importa (idempotente, por slug) os JSONs REVISADOS de scratch/import_livros/ para o
catalogo (TbItemMundano, TbItemMagico, TbBestiario, TbRegra).

Etapa revisavel: por padrao roda em PREVIEW (nao grava). Use --apply para gravar.
Cada arquivo e uma lista de objetos; o `slug` e a chave (upsert). Campos de manifesto
(`action`, `duplicate_of`, `nome_en`, e os campos de staging de VTT) que NAO existem no
modelo sao ignorados na gravacao. `action: skip_duplicate` pula a entrada.

    manage.py importar_livros                  # preview de tudo
    manage.py importar_livros --tipo regra     # so as regras
    manage.py importar_livros --apply           # grava (idempotente por slug)
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

# arquivo -> (Model, campos permitidos no modelo)
PLANO = {
    "mundano": ("itens_mundanos.json", "TbItemMundano", [
        "nome", "slug", "categoria", "subcategoria", "fonte", "peso", "preco",
        "dano", "propriedades", "maestria", "ca", "tipo_equip", "ca_base",
        "ca_limite_des", "forca_minima", "furtividade_desvantagem",
        "descricao_markdown", "imagem_url", "tags_json"]),
    "magico": ("itens_magicos.json", "TbItemMagico", [
        "nome", "slug", "raridade", "requer_sintonizacao", "detalhes_sintonizacao",
        "slot", "loja", "preco", "tipo", "descricao_markdown", "imagem_url", "tags_json"]),
    "criatura": ("criaturas.json", "TbBestiario", [
        "nome", "slug", "tipo", "tamanho", "nd", "alinhamento", "source", "ca", "pv",
        "statblock_json", "tags_json", "descricao_markdown", "imagem_url", "comunidade"]),
    # TbRegra so tem o subconjunto de glossario; os campos de VTT (rule_kind,
    # default_enabled, toggleable, implementation_notes) ficam no JSON para o futuro VTT.
    "regra": ("regras_vtt.json", "TbRegra", ["slug", "nome", "nome_en", "categoria", "definicao"]),
}


class Command(BaseCommand):
    help = "Importa por slug os JSONs revisados de scratch/import_livros/ (preview; --apply grava)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="scratch/import_livros")
        parser.add_argument("--tipo", choices=list(PLANO) + ["todos"], default="todos")
        parser.add_argument("--apply", action="store_true", help="Grava no banco (sem isso, so mostra o plano).")

    def handle(self, *args, **opt):
        from django.apps import apps
        tipos = list(PLANO) if opt["tipo"] == "todos" else [opt["tipo"]]
        total = {"create": 0, "update": 0, "skip": 0, "erro": 0}

        for tipo in tipos:
            arquivo, model_name, campos = PLANO[tipo]
            caminho = os.path.join(opt["dir"], arquivo)
            if not os.path.exists(caminho):
                self.stdout.write(self.style.WARNING("  (pulado) %s nao encontrado" % caminho))
                continue
            Model = apps.get_app_config("home").get_model(model_name)
            with open(caminho, encoding="utf-8") as fh:
                try:
                    entradas = json.load(fh)
                except json.JSONDecodeError as e:
                    raise CommandError("JSON invalido em %s: %s" % (caminho, e))

            self.stdout.write(self.style.HTTP_INFO("== %s -> %s (%d entradas) ==" % (arquivo, model_name, len(entradas))))
            for ent in entradas:
                slug = (ent.get("slug") or slugify(ent.get("nome_en") or ent.get("nome") or "")).strip()
                if not slug:
                    self.stdout.write(self.style.ERROR("  ! sem slug: %s" % ent.get("nome")))
                    total["erro"] += 1
                    continue
                if ent.get("action") == "skip_duplicate":
                    self.stdout.write("  ~ skip_duplicate: %s (duplicata de %s)" % (slug, ent.get("duplicate_of")))
                    total["skip"] += 1
                    continue
                dados = {c: ent[c] for c in campos if c in ent and c != "slug"}
                try:
                    obj = Model.objects.filter(slug=slug).first()
                    acao = "update" if obj else "create"
                    if opt["apply"]:
                        with transaction.atomic():
                            if obj:
                                for k, v in dados.items():
                                    setattr(obj, k, v)
                                obj.save()
                            else:
                                Model.objects.create(slug=slug, **dados)
                    self.stdout.write(("  %s %s" % ("+" if acao == "create" else "~", slug)))
                    total[acao] += 1
                except Exception as e:  # nao derruba o lote por causa de 1 entrada
                    self.stdout.write(self.style.ERROR("  ! erro em %s: %s" % (slug, e)))
                    total["erro"] += 1

        modo = "GRAVADO" if opt["apply"] else "PREVIEW (nada gravado; use --apply)"
        self.stdout.write(self.style.SUCCESS(
            "\n%s — create=%d update=%d skip=%d erro=%d"
            % (modo, total["create"], total["update"], total["skip"], total["erro"])))
