import json
import math
import re
import unicodedata
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator, slugify

from .bot_mongo import (
    BotMongoUnavailable,
    collection_document_count,
    delete_document,
    find_documents,
    get_bot_database,
    get_document,
    list_collection_summaries,
    save_document,
)
from .models import (
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbEssencia,
    TbLinhagem,
    TbMapMarker,
    TbOpcaojogo,
    TbRaca,
    TbRecursoclasse,
    TbRegiao,
    TbSubclasse,
    TbTalento,
    TbTerritorio,
    TbTracoracial,
    TbItemMundano,
    TbItemMagico,
)
from .security import validate_json_no_sql_danger, validate_no_sql_danger


admin.site.site_header = "Bonfire Tales Admin"
admin.site.site_title = "Bonfire Tales Admin"
admin.site.index_title = "Painel de Conteudo"
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser


def markdown_editor_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Editor Markdown",
    }
    return render(request, "admin/markdown_editor.html", context)


def mongo_collections_view(request):
    mongo_error = ""
    collections = []
    database_name = ""

    try:
        collections = list_collection_summaries()
        database_name = collections[0].get("database", "") if collections else ""
    except BotMongoUnavailable as exc:
        mongo_error = str(exc)

    context = {
        **admin.site.each_context(request),
        "title": "Mongo do Bot",
        "collections": collections,
        "mongo_error": mongo_error,
        "database_name": database_name,
        "configured_database": getattr(settings, "BOT_MONGO_DATABASE", ""),
    }
    return render(request, "admin/mongo_collections.html", context)


def mongo_collection_detail_view(request, collection_name):
    search = request.GET.get("q", "").strip()
    per_page = request.GET.get("per_page") or request.GET.get("limit") or "50"
    page = request.GET.get("page", "1")
    try:
        per_page = min(max(int(per_page), 1), 200)
    except ValueError:
        per_page = 50
    try:
        page = max(int(page), 1)
    except ValueError:
        page = 1

    mongo_error = ""
    documents = []
    total_documents = 0
    try:
        total_documents = collection_document_count(collection_name, search=search)
        total_pages = max(math.ceil(total_documents / per_page), 1)
        page = min(page, total_pages)
        documents = find_documents(
            collection_name,
            search=search,
            limit=per_page,
            skip=(page - 1) * per_page,
        )
    except BotMongoUnavailable as exc:
        mongo_error = str(exc)
        total_pages = 1

    table_columns = _mongo_table_columns(documents)
    table_rows = [_mongo_table_row(document, table_columns) for document in documents]
    page_start = ((page - 1) * per_page + 1) if total_documents else 0
    page_end = min(page * per_page, total_documents)

    def page_url(target_page):
        params = {"page": target_page, "per_page": per_page}
        if search:
            params["q"] = search
        return f"?{urlencode(params)}"

    window_start = max(page - 2, 1)
    window_end = min(page + 2, total_pages)
    page_links = [
        {"number": number, "url": page_url(number), "is_current": number == page}
        for number in range(window_start, window_end + 1)
    ]

    context = {
        **admin.site.each_context(request),
        "title": f"Mongo: {collection_name}",
        "collection_name": collection_name,
        "table_columns": table_columns,
        "table_rows": table_rows,
        "search": search,
        "per_page": per_page,
        "limit": per_page,
        "page": page,
        "total_pages": total_pages,
        "total_documents": total_documents,
        "page_start": page_start,
        "page_end": page_end,
        "page_links": page_links,
        "first_page_url": page_url(1),
        "previous_page_url": page_url(page - 1) if page > 1 else "",
        "next_page_url": page_url(page + 1) if page < total_pages else "",
        "last_page_url": page_url(total_pages),
        "mongo_error": mongo_error,
        "spells_collection_name": SPELL_COLLECTION_NAME,
    }
    return render(request, "admin/mongo_collection_detail.html", context)


MONGO_EDITOR_SCHEMAS = {
    "spells": [
        ("Nome", "text"), ("Slug", "text"), ("Nivel", "number"), ("Escola", "text"),
        ("CastingTime", "text"), ("Ritual", "checkbox"), ("Duracao", "text"),
        ("Concentracao", "checkbox"), ("Alcance", "text"), ("Componentes", "json"),
        ("Classes", "json"), ("Subclasses", "json"), ("Descricao", "textarea"),
        ("EmNiveisSuperiores", "textarea"),
    ],
    "backgrounds": [
        ("Nome", "text"), ("Slug", "text"), ("Tipo", "text"), ("Tags", "json"),
        ("Resumo", "textarea"), ("Proficiencias", "json"), ("Idiomas", "json"),
        ("Equipamento", "textarea"), ("Descricao", "textarea"),
    ],
    "bestiary": [
        ("Nome", "text"), ("Slug", "text"), ("Tipo", "text"), ("Tamanho", "text"),
        ("CA", "number"), ("PV", "text"), ("Deslocamento", "text"), ("Dificuldade", "text"),
        ("Atributos", "json"), ("Salvaguardas", "json"), ("Pericias", "json"),
        ("Resistencias", "json"), ("Imunidades", "json"), ("Sentidos", "text"),
        ("Idiomas", "text"), ("XP", "number"), ("Descricao", "textarea"),
        ("Tracos", "json"), ("Acoes", "json"), ("Reacoes", "json"), ("AcoesLendarias", "json"),
    ],
    "organizations": [
        ("Nome", "text"), ("Slug", "text"), ("Tipo", "text"), ("Sede", "text"),
        ("Regioes", "json"), ("Territorios", "json"), ("Lideranca", "text"),
        ("Aliados", "json"), ("Inimigos", "json"), ("Tags", "json"), ("Descricao", "textarea"),
    ],
}


def _mongo_schema_for_collection(collection_name):
    configured = getattr(settings, "SITE_MONGO_COLLECTIONS", {})
    for key, configured_name in configured.items():
        if configured_name == collection_name and key in MONGO_EDITOR_SCHEMAS:
            return MONGO_EDITOR_SCHEMAS[key]
    return MONGO_EDITOR_SCHEMAS.get(collection_name, [])


def mongo_document_edit_view(request):
    collection_name = request.GET.get("collection") or request.POST.get("collection") or ""
    document_id = request.GET.get("id") or request.POST.get("document_id") or ""
    is_new = not document_id

    if not collection_name:
        messages.error(request, "Collection nao informada.")
        return redirect("admin:mongo_collections")

    original_doc = {}
    initial_json = "{\n  \n}"
    if document_id:
        original_doc = get_document(collection_name, document_id)
        if not original_doc:
            messages.error(request, "Documento nao encontrado.")
            return redirect("admin:mongo_collection_detail", collection_name=collection_name)
        initial_json = json.dumps(original_doc, ensure_ascii=False, indent=2, default=str)

    
    doc_fields = []
    skip_keys = {"_id", "_row_hash", "_sqlite_pk", "_sqlite_table", "_source"}
    for key, value in original_doc.items():
        if key in skip_keys:
            continue
        field_type = "text"
        display_value = value
        if isinstance(value, bool):
            field_type = "checkbox"
        elif isinstance(value, (int, float)):
            field_type = "number"
        elif isinstance(value, (dict, list)):
            field_type = "json"
            display_value = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        elif isinstance(value, str) and (len(value) > 120 or "\n" in value):
            field_type = "textarea"
        elif value is None:
            display_value = ""
        doc_fields.append({
            "key": key,
            "value": display_value,
            "field_type": field_type,
        })
    if not doc_fields:
        for key, field_type in _mongo_schema_for_collection(collection_name):
            default_value = "[]" if field_type == "json" else ""
            doc_fields.append({"key": key, "value": default_value, "field_type": field_type})

    if request.method == "POST":
        edit_mode = request.POST.get("edit_mode", "fields")

        if edit_mode == "json":
            
            form = MongoDocumentForm(request.POST)
            if form.is_valid():
                try:
                    payload = json.loads(form.cleaned_data["document_json"])
                    if not isinstance(payload, dict):
                        raise ValueError("O JSON precisa representar um objeto.")
                    saved_id = save_document(collection_name, payload)
                    messages.success(request, f"Documento {saved_id} salvo no Mongo.")
                    return redirect("admin:mongo_collection_detail", collection_name=collection_name)
                except Exception as exc:
                    form.add_error("document_json", str(exc))
        else:
            
            try:
                payload = {}
                if document_id:
                    payload["_id"] = original_doc.get("_id")

                field_keys = request.POST.getlist("field_key")
                field_values = request.POST.getlist("field_value")
                field_types = request.POST.getlist("field_type")

                for fk, fv, ft in zip(field_keys, field_values, field_types):
                    fk = fk.strip()
                    if not fk or fk in skip_keys:
                        continue
                    if ft == "checkbox":
                        payload[fk] = fk in request.POST.getlist("field_checked")
                    elif ft == "number":
                        try:
                            payload[fk] = int(fv) if "." not in fv else float(fv)
                        except ValueError:
                            payload[fk] = fv
                    elif ft == "json":
                        try:
                            payload[fk] = json.loads(fv)
                        except (json.JSONDecodeError, ValueError):
                            payload[fk] = fv
                    else:
                        payload[fk] = fv

                validate_json_no_sql_danger(json.dumps(payload, default=str), "documento")
                saved_id = save_document(collection_name, payload)
                messages.success(request, f"Documento {saved_id} salvo no Mongo.")
                return redirect("admin:mongo_collection_detail", collection_name=collection_name)
            except Exception as exc:
                messages.error(request, f"Erro ao salvar: {exc}")
            form = MongoDocumentForm(initial={
                "collection": collection_name,
                "document_id": document_id,
                "document_json": initial_json,
            })
    else:
        form = MongoDocumentForm(initial={
            "collection": collection_name,
            "document_id": document_id,
            "document_json": initial_json,
        })

    context = {
        **admin.site.each_context(request),
        "title": f"{'Novo' if is_new else 'Editar'} documento: {collection_name}",
        "collection_name": collection_name,
        "document_id": document_id,
        "form": form,
        "is_new": is_new,
        "doc_fields": doc_fields,
    }
    return render(request, "admin/mongo_document_form.html", context)


def mongo_document_delete_view(request):
    if request.method != "POST":
        messages.error(request, "Exclusao precisa ser feita por POST.")
        return redirect("admin:mongo_collections")

    collection_name = request.POST.get("collection", "")
    document_id = request.POST.get("id", "")
    if not collection_name or not document_id:
        messages.error(request, "Collection ou documento nao informado.")
        return redirect("admin:mongo_collections")

    try:
        deleted = delete_document(collection_name, document_id)
        if deleted:
            messages.success(request, f"Documento {document_id} excluido.")
        else:
            messages.warning(request, f"Documento {document_id} nao foi encontrado.")
    except BotMongoUnavailable as exc:
        messages.error(request, f"Mongo indisponivel: {exc}")

    return redirect("admin:mongo_collection_detail", collection_name=collection_name)


SPELL_COLLECTION_KEY = "spells"
SPELL_COLLECTION_NAME = getattr(settings, "SITE_MONGO_COLLECTIONS", {}).get(
    SPELL_COLLECTION_KEY,
    getattr(settings, "BOT_MONGO_COLLECTIONS", {}).get(SPELL_COLLECTION_KEY, "spells"),
)

SPELL_HEADER_ALIASES = {
    "nome": "Nome",
    "nome_da_magia": "Nome",
    "magia": "Nome",
    "nivel": "Nivel",
    "nível": "Nivel",
    "lvl": "Nivel",
    "level": "Nivel",
    "casting_time": "CastingTime",
    "cating_time": "CastingTime",
    "tempo_de_conjuracao": "CastingTime",
    "tempo_de_conjuração": "CastingTime",
    "ritual": "Ritual",
    "ritual_booleana": "Ritual",
    "duracao": "Duracao",
    "duração": "Duracao",
    "escola": "Escola",
    "escola_de_magia": "Escola",
    "alcance": "Alcance",
    "range": "Alcance",
    "componentes": "Componentes",
    "components": "Componentes",
    "classes": "Classes",
    "classes_nome_do_bonfas": "Classes",
    "subclasses": "Subclasses",
    "subclasses_nome_do_bonfas": "Subclasses",
    "descricao": "Descricao",
    "descrição": "Descricao",
    "description": "Descricao",
    "em_niveis_superiores": "EmNiveisSuperiores",
    "em_níveis_superiores": "EmNiveisSuperiores",
    "higher_levels": "EmNiveisSuperiores",
    "higher_lvls": "EmNiveisSuperiores",
}


def _mongo_collection_by_name(collection_name):
    return get_bot_database()[collection_name]


def _next_numeric_id(collection, field_name):
    last = collection.find_one({field_name: {"$exists": True}}, sort=[(field_name, -1)])
    try:
        return int((last or {}).get(field_name) or 0) + 1
    except (TypeError, ValueError):
        return 1


def _split_list_value(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[,;/\n]+", str(value)) if part.strip()]


def _slug_list_value(value):
    slugs = []
    for item in _split_list_value(value):
        item_slug = slugify(item)
        if item_slug:
            slugs.append(item_slug)
    return slugs


def _bool_value(value):
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "sim", "s", "true", "yes", "y", "ritual"}


def _spell_level_value(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"c", "cantrip", "truque"}:
        return 0
    try:
        return int(float(normalized.replace(",", ".")))
    except (TypeError, ValueError):
        raise ValueError("nivel invalido")


def _normalize_casting_time(value):
    text = str(value or "").strip()
    normalized = _normalize_label(text)
    if normalized in {"bonus", "acao_bonus", "ação_bônus", "bonus_action"}:
        return "Ação bônus"
    if normalized in {"acao", "action"}:
        return "Ação"
    if normalized in {"reacao", "reaction"}:
        return "Reação"
    return text


def _duration_and_concentration(value):
    text = str(value or "").strip()
    concentration = bool(re.search(r"\bconcentra[cç][aã]o\b", text, re.I))
    clean = re.sub(r"^\s*concentra[cç][aã]o\s*,?\s*(?:até\s*)?", "", text, flags=re.I).strip()
    return clean or text, concentration


def _format_spell_range(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(feet|foot|ft|pes|pés|pe|pé)\b", lower)
    if match:
        feet = float(match.group(1).replace(",", "."))
        meters = feet * 1.5 / 5
        meters_text = str(int(meters)) if meters.is_integer() else f"{meters:.1f}".replace(".", ",")
        feet_text = str(int(feet)) if feet.is_integer() else f"{feet:.1f}".replace(".", ",")
        return f"{meters_text} metros [{feet_text} pés]"
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(m|metro|metros)\b", lower)
    if match:
        meters = float(match.group(1).replace(",", "."))
        feet = meters * 5 / 1.5
        meters_text = str(int(meters)) if meters.is_integer() else f"{meters:.1f}".replace(".", ",")
        feet_text = str(int(round(feet)))
        return f"{meters_text} metros [{feet_text} pés]"
    return raw


def _normalize_spell_components(value):
    parts = []
    text = str(value or "")
    for code in ("V", "S", "M"):
        if re.search(rf"\b{code}\b", text, re.I):
            parts.append(code)
    return parts or _split_list_value(value)


def _spell_material_text(value):
    text = str(value or "")
    match = re.search(r"\bM\s*\((.*?)\)", text, re.I | re.S)
    return match.group(1).strip() if match else ""


def _read_spell_rows_from_xlsx(uploaded):
    try:
        from openpyxl import load_workbook
    except ImportError:
        rows = _read_xlsx_rows_without_openpyxl(uploaded)
    else:
        workbook = load_workbook(uploaded, read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return []

    headers = []
    for header in rows[0]:
        normalized = _normalize_label(str(header or ""))
        headers.append(SPELL_HEADER_ALIASES.get(normalized, normalized))

    spells = []
    for index, row in enumerate(rows[1:], start=2):
        raw = {
            headers[i]: row[i]
            for i in range(min(len(headers), len(row)))
            if headers[i] and row[i] not in (None, "")
        }
        if not raw:
            continue
        name = str(raw.get("Nome") or "").strip()
        if not name:
            raise ValueError(f"Linha {index}: nome da magia e obrigatorio.")

        try:
            level = _spell_level_value(raw.get("Nivel"))
        except ValueError:
            raise ValueError(f"Linha {index}: nivel invalido.")

        casting_time = _normalize_casting_time(raw.get("CastingTime"))
        duration, concentration = _duration_and_concentration(raw.get("Duracao"))
        components_raw = str(raw.get("Componentes") or "").strip()

        spells.append({
            "Nome": name,
            "Slug": slugify(name),
            "Nivel": level,
            "EhTruque": level == 0,
            "CastingTime": casting_time,
            "AcaoBonus": _normalize_label(casting_time) == "acao_bonus",
            "Ritual": _bool_value(raw.get("Ritual")),
            "Duracao": duration,
            "Concentracao": concentration,
            "Escola": str(raw.get("Escola") or "").strip(),
            "Alcance": _format_spell_range(raw.get("Alcance")),
            "Componentes": _normalize_spell_components(raw.get("Componentes")),
            "ComponentesRaw": components_raw,
            "Material": _spell_material_text(raw.get("Componentes")) or None,
            "Classes": _slug_list_value(raw.get("Classes")),
            "Subclasses": _slug_list_value(raw.get("Subclasses")),
            "Descricao": str(raw.get("Descricao") or "").strip(),
            "EmNiveisSuperiores": str(raw.get("EmNiveisSuperiores") or "").strip() or None,
        })
    return spells


def _read_xlsx_rows_without_openpyxl(uploaded):
    import re as _re
    import zipfile
    from xml.etree import ElementTree

    uploaded.seek(0)
    with zipfile.ZipFile(uploaded) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall("x:si", ns):
                text = "".join(node.text or "" for node in item.findall(".//x:t", ns))
                shared_strings.append(text)

        sheet_name = "xl/worksheets/sheet1.xml"
        root = ElementTree.fromstring(archive.read(sheet_name))
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows = []
        for row in root.findall(".//x:row", ns):
            values_by_index = {}
            max_index = -1
            for cell in row.findall("x:c", ns):
                ref = cell.attrib.get("r", "")
                letters = _re.sub(r"\d", "", ref)
                index = 0
                for char in letters:
                    index = index * 26 + (ord(char.upper()) - ord("A") + 1)
                index -= 1
                max_index = max(max_index, index)

                value_node = cell.find("x:v", ns)
                inline_node = cell.find("x:is/x:t", ns)
                value = inline_node.text if inline_node is not None else (value_node.text if value_node is not None else "")
                if cell.attrib.get("t") == "s" and value != "":
                    value = shared_strings[int(value)]
                values_by_index[index] = value
            if max_index >= 0:
                rows.append(tuple(values_by_index.get(i, "") for i in range(max_index + 1)))
        return rows


def spell_excel_import_view(request):
    result = None
    mongo_error = ""
    if request.method == "POST":
        form = SpellExcelImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                spells = _read_spell_rows_from_xlsx(form.cleaned_data["arquivo"])
                collection = _mongo_collection_by_name(SPELL_COLLECTION_NAME)
                imported = 0
                updated = 0
                skipped = 0
                next_id = _next_numeric_id(collection, "Id_Magia")

                if not form.cleaned_data["apenas_validar"]:
                    for spell in spells:
                        existing = collection.find_one({"Slug": spell["Slug"]})
                        if existing and not form.cleaned_data["atualizar_existentes"]:
                            skipped += 1
                            continue
                        if existing:
                            spell["Id_Magia"] = existing.get("Id_Magia") or next_id
                            collection.replace_one({"_id": existing["_id"]}, {**existing, **spell})
                            updated += 1
                        else:
                            spell["Id_Magia"] = next_id
                            next_id += 1
                            collection.insert_one(spell)
                            imported += 1

                result = {
                    "read": len(spells),
                    "imported": imported,
                    "updated": updated,
                    "skipped": skipped,
                    "validated_only": form.cleaned_data["apenas_validar"],
                    "collection": SPELL_COLLECTION_NAME,
                }
            except BotMongoUnavailable as exc:
                mongo_error = str(exc)
            except Exception as exc:
                form.add_error("arquivo", str(exc))
    else:
        form = SpellExcelImportForm()

    return render(request, "admin/spell_import.html", {
        **admin.site.each_context(request),
        "title": "Importar magias por Excel",
        "form": form,
        "result": result,
        "mongo_error": mongo_error,
        "collection_name": SPELL_COLLECTION_NAME,
    })


def _mongo_table_columns(documents):
    priority = ["_id", "Nome", "name", "Slug", "slug", "Tipo", "type", "Descricao", "description"]
    excluded = {"_row_hash", "_sqlite_pk", "_sqlite_table", "_source", "password"}
    discovered = []
    for document in documents:
        for key in document.keys():
            if key in excluded or key in discovered:
                continue
            discovered.append(key)

    ordered = [key for key in priority if key in discovered]
    ordered.extend(key for key in discovered if key not in ordered)
    return ordered[:12]


def _mongo_cell_value(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    if value is True:
        return "Sim"
    if value is False:
        return "Nao"
    if value is None:
        return "-"
    return Truncator(str(value).replace("\n", " ")).chars(120)


def _mongo_table_row(document, columns):
    return {
        "id": document.get("_id", ""),
        "cells": [_mongo_cell_value(document.get(column)) for column in columns],
    }


class BonfireAdminMixin:
    save_on_top = True
    list_per_page = 40
    formfield_overrides = {
        models.TextField: {
            "widget": forms.Textarea(
                attrs={
                    "rows": 8,
                    "class": "bonfire-markdown",
                    "spellcheck": "true",
                }
            )
        },
    }

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class SafeAdminForm(base_form):
            def clean(self):
                cleaned_data = super().clean()
                for field_name, value in cleaned_data.items():
                    validate_no_sql_danger(value, field_name)
                return cleaned_data

        return SafeAdminForm

    @admin.display(description="Resumo")
    def short_description(self, obj):
        text = (
            getattr(obj, "descricao", None)
            or getattr(obj, "markdown", None)
            or getattr(obj, "lore_presentation", None)
            or getattr(obj, "tagline", None)
            or ""
        )
        return Truncator(text.replace("\n", " ")).chars(90)


class TalentoBulkImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo .txt",
        help_text="Use blocos com Nome, Etiqueta, Tag, Pre Requisito e Descricao.",
    )
    tipo = forms.ChoiceField(
        label="Tipo dos talentos",
        choices=TbTalento.TIPO_CHOICES,
        initial="origem",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar talentos existentes pelo slug",
        required=False,
        initial=True,
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class TalentoBulkConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class ClasseBulkImportForm(forms.Form):
    classe = forms.ModelChoiceField(
        label="Classe",
        queryset=TbClasse.objects.all().order_by("nome"),
        help_text="Classe que recebera os recursos e habilidades do arquivo.",
    )
    arquivo = forms.FileField(
        label="Arquivo .txt",
        help_text="Use secoes [RECURSOS] e [HABILIDADES], separando blocos com ---.",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar registros existentes",
        required=False,
        initial=True,
        help_text="Recursos: classe/subclasse/nivel/nome. Habilidades: classe/subclasse/nivel/nome.",
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class ClasseBulkConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    classe_id = forms.IntegerField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class TracoRacialBulkImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo .txt",
        help_text="Use blocos separados por ---. Cada bloco precisa de Nome, uma origem por slug e Descricao.",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar tracos existentes pela origem e nome",
        required=False,
        initial=True,
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class TracoRacialBulkConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class OpcaoJogoBulkImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo .txt",
        help_text="Use blocos separados por ---. Campos: Nome, Tipo, Tags, Pre Requisito, Classes, Subclasses, Nivel Recebimento e Descricao.",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar opcoes existentes pelo slug",
        required=False,
        initial=True,
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class OpcaoJogoBulkConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


class MongoDocumentForm(forms.Form):
    collection = forms.CharField(widget=forms.HiddenInput)
    document_id = forms.CharField(required=False, widget=forms.HiddenInput)
    document_json = forms.CharField(
        label="Documento JSON",
        widget=forms.Textarea(attrs={"rows": 24, "spellcheck": "false"}),
        help_text="Edite com cuidado. Campos de data de collections nativas do bot podem precisar continuar como Date no Mongo.",
    )

    def clean_document_json(self):
        value = self.cleaned_data["document_json"]
        validate_json_no_sql_danger(value, "documento")
        return value


class SpellExcelImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo Excel (.xlsx)",
        help_text="Primeira linha como cabecalho. Aceita: nome, nivel/lvl, casting time, ritual, duracao, escola, alcance, componentes, classes, subclasses, descricao, em niveis superiores.",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar magias existentes pelo nome",
        required=False,
        initial=True,
    )
    apenas_validar = forms.BooleanField(
        label="Apenas validar, sem gravar",
        required=False,
        initial=False,
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        if not uploaded.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx.")
        return uploaded


def _normalize_label(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", without_accents.lower()).strip("_")


def _decode_upload(uploaded_file):
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _unique_slug(base_slug, current_slug=None):
    slug = base_slug or "talento"
    candidate = slug
    counter = 2
    query = TbTalento.objects.all()
    if current_slug:
        query = query.exclude(slug=current_slug)

    while query.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _unique_option_slug(base_slug, current_slug=None):
    slug = base_slug or "opcao"
    candidate = slug
    counter = 2
    query = TbOpcaojogo.objects.all()
    if current_slug:
        query = query.exclude(slug=current_slug)

    while query.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _parse_talentos_txt(content, tipo):
    etiqueta_map = {
        _normalize_label(value): key
        for key, value in TbTalento.ETIQUETA_CHOICES
    }
    etiqueta_map.update({key: key for key, _ in TbTalento.ETIQUETA_CHOICES})

    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = source.split("\n")
    talentos = []
    errors = []
    index = 0

    def next_nonempty(start):
        cursor = start
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        return cursor

    def field_value(line, field_name):
        if ":" not in line:
            return None
        label, value = line.split(":", 1)
        return value.strip() if _normalize_label(label) == field_name else None

    def field_name(line):
        if ":" not in line:
            return None
        label = line.split(":", 1)[0]
        normalized = _normalize_label(label)
        aliases = {
            "etiqueta": "etiqueta",
            "tag": "tag",
            "pre_requisito": "pre_requisito",
            "aumento_de_atributo": "aumento_de_atributo",
            "descricao": "descricao",
        }
        return aliases.get(normalized)

    def starts_record(start):
        start = next_nonempty(start)
        if start >= len(lines) or not lines[start].strip() or ":" in lines[start]:
            return False
        cursor = start + 1
        found = set()
        while cursor < len(lines) and len(found) < 5:
            cursor = next_nonempty(cursor)
            if cursor >= len(lines):
                break
            current_field = field_name(lines[cursor])
            if not current_field:
                break
            found.add(current_field)
            if current_field == "descricao":
                break
            cursor += 1
        return "etiqueta" in found and "descricao" in found

    while index < len(lines):
        index = next_nonempty(index)
        if index >= len(lines):
            break

        if not starts_record(index):
            index += 1
            continue

        nome = lines[index].strip()
        cursor = next_nonempty(index + 1)
        fields = {
            "etiqueta": "",
            "tag": "",
            "pre_requisito": "",
            "aumento_de_atributo": "",
        }
        descricao_marker_index = None

        while cursor < len(lines):
            cursor = next_nonempty(cursor)
            current_field = field_name(lines[cursor]) if cursor < len(lines) else None
            if not current_field:
                break
            if current_field == "descricao":
                descricao_marker_index = cursor
                break
            fields[current_field] = lines[cursor].split(":", 1)[1].strip()
            cursor += 1

        if descricao_marker_index is None:
            errors.append(f"{nome}: campo Descricao nao encontrado.")
            index = cursor + 1
            continue

        etiqueta_text = fields["etiqueta"]
        tags = fields["tag"]
        pre_requisito = fields["pre_requisito"]
        atributos = _parse_attribute_increase(fields["aumento_de_atributo"])
        atributos_display = [
            label
            for field_name, label in (
                ("atrib_forca", "Forca"),
                ("atrib_destreza", "Destreza"),
                ("atrib_constituicao", "Constituicao"),
                ("atrib_inteligencia", "Inteligencia"),
                ("atrib_sabedoria", "Sabedoria"),
                ("atrib_carisma", "Carisma"),
            )
            if atributos[field_name]
        ]
        descricao_start = descricao_marker_index + 1
        descricao_end = descricao_start
        while descricao_end < len(lines) and not starts_record(descricao_end):
            descricao_end += 1

        descricao = "\n".join(lines[descricao_start:descricao_end]).strip()
        etiqueta = etiqueta_map.get(_normalize_label(etiqueta_text))

        if not etiqueta:
            errors.append(f"{nome}: etiqueta desconhecida '{etiqueta_text}'.")
            index = descricao_end
            continue

        talentos.append({
            "nome": nome,
            "slug": slugify(nome),
            "tipo": tipo,
            "etiqueta": etiqueta,
            "etiqueta_label": dict(TbTalento.ETIQUETA_CHOICES).get(etiqueta, etiqueta),
            "etiquetas_adicionais": tags or None,
            "pre_requisito": pre_requisito or None,
            "descricao": descricao,
            "atributos_display": ", ".join(atributos_display) or "Nenhum",
            **atributos,
        })
        index = descricao_end

    if not talentos and not errors:
        errors.append("Nenhum talento foi encontrado. Confira se o arquivo segue o formato esperado.")

    return talentos, errors


def _parse_attribute_increase(value):
    normalized = _normalize_label(value)
    attributes = {
        "atrib_forca": False,
        "atrib_destreza": False,
        "atrib_constituicao": False,
        "atrib_inteligencia": False,
        "atrib_sabedoria": False,
        "atrib_carisma": False,
    }

    if not normalized or normalized in {"nenhum", "nao", "n_a"}:
        return attributes

    if "atributo_a_sua_escolha" in normalized or "atributo_sua_escolha" in normalized:
        return {key: True for key in attributes}

    lookup = {
        "forca": "atrib_forca",
        "destreza": "atrib_destreza",
        "constituicao": "atrib_constituicao",
        "inteligencia": "atrib_inteligencia",
        "sabedoria": "atrib_sabedoria",
        "carisma": "atrib_carisma",
    }

    for token, field_name in lookup.items():
        if re.search(rf"(?:^|_){token}(?:_|$)", normalized):
            attributes[field_name] = True

    return attributes


def _split_import_sections(content):
    current = None
    sections = {"recursos": [], "habilidades": []}

    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        marker = _normalize_label(line.strip().strip("[]"))
        if marker in {
            "recursos",
            "recurso_classe",
            "recursos_de_classe",
            "recursos_subclasse",
            "recursos_de_subclasse",
            "recursos_subclasses",
        }:
            current = "recursos"
            continue
        if marker in {"habilidades", "habilidades_classe", "habilidades_de_classe"}:
            current = "habilidades"
            continue
        if current:
            sections[current].append(line)

    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _split_blocks(section_text):
    blocks = []
    current = []

    for line in (section_text or "").split("\n"):
        if line.strip() == "---":
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = []
            continue
        current.append(line)

    block = "\n".join(current).strip()
    if block:
        blocks.append(block)
    return blocks


def _parse_key_value_block(block):
    data = {}
    labels = {}
    current_key = None

    for line in block.split("\n"):
        if current_key == "descricao":
            data[current_key] = f"{data[current_key]}\n{line}".strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current_key = _normalize_label(key)
            labels[current_key] = key.strip()
            data[current_key] = value.strip()
            continue
        if current_key:
            data[current_key] = f"{data[current_key]}\n{line}".strip()

    data["__labels__"] = labels
    return data


def _parse_bool(value):
    return _normalize_label(value) in {"sim", "s", "true", "1", "yes", "y"}


def _split_slug_list(value):
    return [
        item.strip()
        for item in re.split(r"[,;\n]+", value or "")
        if item.strip()
    ]


def _get_subclasse_by_slug(classe, slug):
    slug = (slug or "").strip()
    if not slug:
        return None
    return TbSubclasse.objects.filter(id_classe=classe, slug=slug).first()


def _parse_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_tracos_raciais_txt(content):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if _normalize_label(source.split("\n", 1)[0] if source else "") in {"tracos", "tracos_raciais"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    tracos = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block)
        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        nivel = _parse_int(data.get("nivel") or data.get("nivel_requisito"), 0)
        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("requisito")
            or ""
        ).strip()
        talento_racial = _parse_bool(
            data.get("talento_racial")
            or data.get("talento")
            or data.get("opcional")
        )

        if not nome:
            errors.append(f"Bloco {index}: campo Nome ausente.")
            continue
        if not descricao:
            errors.append(f"Traco '{nome}': campo Descricao ausente.")
            continue
        if nivel is None or nivel < 0:
            errors.append(f"Traco '{nome}': campo Nivel invalido. Use 0 para tracos raciais base.")
            continue

        raca_slug = (data.get("raca") or data.get("raça") or "").strip()
        linhagem_slug = (data.get("linhagem") or "").strip()
        essencia_slug = (data.get("essencia") or data.get("essência") or "").strip()
        origins = [value for value in (raca_slug, linhagem_slug, essencia_slug) if value]
        if len(origins) != 1:
            errors.append(f"Traco '{nome}': informe exatamente uma origem: Raca, Linhagem ou Essencia.")
            continue

        raca = linhagem = essencia = None
        origem_tipo = origem_nome = ""
        if raca_slug:
            raca = TbRaca.objects.filter(slug=raca_slug).first()
            if not raca:
                errors.append(f"Traco '{nome}': raca '{raca_slug}' nao encontrada.")
                continue
            origem_tipo = "Raca"
            origem_nome = raca.nome
        elif linhagem_slug:
            linhagem = TbLinhagem.objects.filter(slug=linhagem_slug).select_related("id_raca").first()
            if not linhagem:
                errors.append(f"Traco '{nome}': linhagem '{linhagem_slug}' nao encontrada.")
                continue
            origem_tipo = "Linhagem"
            origem_nome = f"{linhagem.id_raca.nome} / {linhagem.nome}"
        elif essencia_slug:
            essencia = TbEssencia.objects.filter(slug=essencia_slug).first()
            if not essencia:
                errors.append(f"Traco '{nome}': essencia '{essencia_slug}' nao encontrada.")
                continue
            origem_tipo = "Essencia"
            origem_nome = essencia.nome

        tracos.append({
            "nome": nome,
            "descricao": descricao,
            "nivel_requisito": nivel,
            "talento_racial": talento_racial,
            "pre_requisito": pre_requisito or None,
            "id_raca": raca.id_raca if raca else None,
            "id_linhagem": linhagem.id_linhagem if linhagem else None,
            "id_essencia": essencia.id_essencia if essencia else None,
            "origem_tipo": origem_tipo,
            "origem_nome": origem_nome,
        })

    if not tracos and not errors:
        errors.append("Nenhum traco racial foi encontrado. Confira se os blocos estao separados por ---.")

    return tracos, errors


def _parse_opcoes_jogo_txt(content):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if _normalize_label(source.split("\n", 1)[0] if source else "").strip("_") in {"opcoes", "opcoes_jogo"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    opcoes = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block)
        nome = (data.get("nome") or "").strip()
        tipo = (data.get("tipo") or "").strip()
        descricao = (data.get("descricao") or "").strip()
        slug = (data.get("slug") or slugify(nome)).strip()
        tags = (
            data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
            or data.get("etiquetas_adicionais")
            or ""
        ).strip()
        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("pre_requisitos")
            or data.get("prerequisitos")
            or ""
        ).strip()
        nivel_recebimento = _parse_int(
            data.get("nivel_recebimento")
            or data.get("nivel")
            or data.get("nivel_de_recebimento"),
            1,
        )
        classe_slugs = _split_slug_list(data.get("classes") or data.get("classe") or "")
        subclasse_slugs = _split_slug_list(data.get("subclasses") or data.get("subclasse") or "")

        if not nome:
            errors.append(f"Bloco {index}: campo Nome e obrigatorio.")
        if not tipo:
            errors.append(f"{nome or f'Bloco {index}'}: campo Tipo e obrigatorio.")
        if not descricao:
            errors.append(f"{nome or f'Bloco {index}'}: campo Descricao e obrigatorio.")
        if nivel_recebimento is None:
            errors.append(f"{nome or f'Bloco {index}'}: Nivel Recebimento precisa ser um numero.")

        classes = []
        for classe_slug in classe_slugs:
            classe = TbClasse.objects.filter(slug=classe_slug).first()
            if classe:
                classes.append({"id": classe.id_classe, "slug": classe.slug, "nome": classe.nome})
            else:
                errors.append(f"{nome or f'Bloco {index}'}: classe nao encontrada pelo slug '{classe_slug}'.")

        subclasses = []
        for subclasse_slug in subclasse_slugs:
            subclasse = TbSubclasse.objects.select_related("id_classe").filter(slug=subclasse_slug).first()
            if subclasse:
                subclasses.append({
                    "id": subclasse.id_subclasse,
                    "slug": subclasse.slug,
                    "nome": subclasse.nome,
                    "classe": subclasse.id_classe.nome if subclasse.id_classe_id else "",
                })
            else:
                errors.append(f"{nome or f'Bloco {index}'}: subclasse nao encontrada pelo slug '{subclasse_slug}'.")

        if nome and tipo and descricao and nivel_recebimento is not None:
            opcoes.append({
                "nome": nome,
                "slug": slugify(slug) or slugify(nome),
                "tipo": tipo,
                "etiquetas_adicionais": tags or None,
                "pre_requisito": pre_requisito or None,
                "descricao": descricao,
                "nivel_recebimento": nivel_recebimento,
                "classes": classes,
                "subclasses": subclasses,
                "access_display": ", ".join(
                    [classe["nome"] for classe in classes]
                    + [f"{subclasse['nome']} ({subclasse['classe']})" for subclasse in subclasses]
                ) or "Sem acesso especifico",
            })

    if not opcoes and not errors:
        errors.append("Nenhuma opcao de jogo foi encontrada. Confira se os blocos estao separados por ---.")

    return opcoes, errors


def _parse_classe_import_txt(content, classe):
    sections = _split_import_sections(content)
    recursos = []
    habilidades = []
    errors = []

    reserved_resource_keys = {"nivel", "subclasse"}

    for index, block in enumerate(_split_blocks(sections["recursos"]), start=1):
        data = _parse_key_value_block(block)
        labels = data.get("__labels__", {})
        nivel = data.get("nivel")
        if not nivel or not nivel.isdigit():
            errors.append(f"Recurso bloco {index}: campo Nivel invalido ou ausente.")
            continue

        subclasse_slug = data.get("subclasse", "")
        subclasse = _get_subclasse_by_slug(classe, subclasse_slug)
        if subclasse_slug and not subclasse:
            errors.append(f"Recurso bloco {index}: subclasse '{subclasse_slug}' nao encontrada para {classe.nome}.")
            continue

        for key, value in data.items():
            if key in reserved_resource_keys:
                continue
            if key == "__labels__":
                continue
            nome = labels.get(key, key.replace("_", " ").strip().title())
            recursos.append({
                "nivel": int(nivel),
                "nome": nome,
                "slug": slugify(nome),
                "valor": value.strip() or None,
                "id_subclasse": subclasse.id_subclasse if subclasse else None,
                "subclasse_nome": subclasse.nome if subclasse else "",
            })

    for index, block in enumerate(_split_blocks(sections["habilidades"]), start=1):
        data = _parse_key_value_block(block)
        nome = data.get("nome", "").strip()
        nivel = data.get("nivel")
        descricao = data.get("descricao", "").strip()
        table_only = _parse_bool(data.get("table_only") or data.get("so_tabela") or data.get("apenas_tabela"))
        if not nome:
            errors.append(f"Habilidade bloco {index}: campo Nome ausente.")
            continue
        if not nivel or not nivel.isdigit():
            errors.append(f"Habilidade '{nome}': campo Nivel invalido ou ausente.")
            continue
        if not descricao and not table_only:
            errors.append(f"Habilidade '{nome}': campo Descricao ausente.")
            continue
        if not descricao and table_only:
            descricao = "Apenas tabela."

        subclasse_slug = data.get("subclasse", "")
        subclasse = _get_subclasse_by_slug(classe, subclasse_slug)
        if subclasse_slug and not subclasse:
            errors.append(f"Habilidade '{nome}': subclasse '{subclasse_slug}' nao encontrada para {classe.nome}.")
            continue

        habilidades.append({
            "nome": nome,
            "niveladquirido": int(nivel),
            "descricao": descricao,
            "table_only": table_only,
            "id_subclasse": subclasse.id_subclasse if subclasse else None,
            "subclasse_nome": subclasse.nome if subclasse else "",
        })

    if not recursos and not habilidades and not errors:
        errors.append("Nenhum recurso ou habilidade foi encontrado. Confira as secoes [RECURSOS] e [HABILIDADES].")

    return recursos, habilidades, errors


class TbClassehabilidadeInline(admin.TabularInline):
    model = TbClassehabilidade
    extra = 0
    fields = ("nome", "niveladquirido", "id_subclasse", "table_only", "descricao")
    autocomplete_fields = ("id_subclasse",)
    ordering = ("niveladquirido", "nome")
    show_change_link = True


class TbRecursoclasseInline(admin.TabularInline):
    model = TbRecursoclasse
    extra = 0
    fields = ("nivel", "nome", "slug", "valor", "id_subclasse")
    autocomplete_fields = ("id_subclasse",)
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nivel", "nome")
    show_change_link = True


class TbSubclasseInline(admin.TabularInline):
    model = TbSubclasse
    extra = 0
    fields = ("nome", "slug", "tagline")
    prepopulated_fields = {"slug": ("nome",)}
    show_change_link = True


@admin.register(TbClasse)
class TbClasseAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbclasse/change_list.html"
    list_display = ("nome", "slug", "short_tagline", "subclasses_count")
    search_fields = ("nome", "slug", "tagline", "atributo_principal", "resistencias", "pericias")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    inlines = (TbSubclasseInline, TbClassehabilidadeInline)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tagline")}),
        ("Ficha base", {"fields": (
            "atributo_principal",
            "dado_vida",
            "pv_nivel_1",
            "pv_por_nivel",
            "resistencias",
            "pericias",
            "armas",
            "ferramentas",
            "armaduras",
            "equipamento",
        )}),
        ("Multiclasse", {"fields": (
            "multiclass_requisitos",
            "multiclass_pericias",
            "multiclass_ferramentas",
            "multiclass_armaduras",
        )}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-arquivo/",
                self.admin_site.admin_view(self.importar_arquivo_view),
                name="home_tbclasse_importar_arquivo",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbclasse_importar_arquivo")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar recursos e habilidades de classe",
            "form": ClasseBulkImportForm(),
            "preview_recursos": [],
            "preview_habilidades": [],
            "errors": [],
            "payload": "",
            "classe_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbclasse/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = ClasseBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/home/tbclasse/import_form.html", context)

            classe = get_object_or_404(TbClasse, pk=confirm_form.cleaned_data["classe_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            recursos_criados = recursos_atualizados = habilidades_criadas = habilidades_atualizadas = 0

            with transaction.atomic():
                for item in payload.get("recursos", []):
                    query = TbRecursoclasse.objects.filter(
                        id_classe=classe,
                        id_subclasse_id=item["id_subclasse"],
                        nivel=item["nivel"],
                        nome=item["nome"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.slug = item["slug"]
                        existing.valor = item["valor"]
                        existing.save()
                        recursos_atualizados += 1
                        continue
                    if existing and not atualizar_existentes:
                        continue

                    TbRecursoclasse.objects.create(
                        id_classe=classe,
                        id_subclasse_id=item["id_subclasse"],
                        nome=item["nome"],
                        slug=item["slug"],
                        nivel=item["nivel"],
                        valor=item["valor"],
                    )
                    recursos_criados += 1

                for item in payload.get("habilidades", []):
                    query = TbClassehabilidade.objects.filter(
                        id_classe=classe,
                        id_subclasse_id=item["id_subclasse"],
                        niveladquirido=item["niveladquirido"],
                        nome=item["nome"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.descricao = item["descricao"]
                        existing.table_only = item["table_only"]
                        existing.save()
                        habilidades_atualizadas += 1
                        continue
                    if existing and not atualizar_existentes:
                        continue

                    TbClassehabilidade.objects.create(
                        id_classe=classe,
                        id_subclasse_id=item["id_subclasse"],
                        nome=item["nome"],
                        niveladquirido=item["niveladquirido"],
                        descricao=item["descricao"],
                        table_only=item["table_only"],
                    )
                    habilidades_criadas += 1

            messages.success(
                request,
                (
                    f"Importacao concluida: {recursos_criados} recursos criados, "
                    f"{recursos_atualizados} atualizados; {habilidades_criadas} habilidades criadas, "
                    f"{habilidades_atualizadas} atualizadas."
                ),
            )
            return redirect("admin:home_tbclasse_changelist")

        form = ClasseBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            classe = form.cleaned_data["classe"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            recursos, habilidades, errors = _parse_classe_import_txt(content, classe)
            context.update({
                "preview_recursos": recursos,
                "preview_habilidades": habilidades,
                "errors": errors,
                "payload": json.dumps({"recursos": recursos, "habilidades": habilidades}, ensure_ascii=False),
                "classe_id": classe.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbclasse/import_form.html", context)

    @admin.display(description="Tagline")
    def short_tagline(self, obj):
        return Truncator(obj.tagline or "").chars(70)

    @admin.display(description="Subclasses")
    def subclasses_count(self, obj):
        return obj.tbsubclasse_set.count()


@admin.register(TbSubclasse)
class TbSubclasseAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "classe_nome", "slug", "short_tagline")
    list_filter = ("id_classe",)
    search_fields = ("nome", "slug", "tagline", "id_classe__nome")
    autocomplete_fields = ("id_classe",)
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("id_classe__nome", "nome")

    @admin.display(description="Classe", ordering="id_classe__nome")
    def classe_nome(self, obj):
        return obj.id_classe.nome

    @admin.display(description="Tagline")
    def short_tagline(self, obj):
        return Truncator(obj.tagline or "").chars(70)


@admin.register(TbClassehabilidade)
class TbClassehabilidadeAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "classe_nome", "subclasse_nome", "niveladquirido", "table_only", "short_description")
    list_filter = ("id_classe", "id_subclasse", "niveladquirido", "table_only")
    search_fields = ("nome", "descricao", "id_classe__nome", "id_subclasse__nome")
    autocomplete_fields = ("id_classe", "id_subclasse")
    ordering = ("id_classe__nome", "niveladquirido", "nome")

    @admin.display(description="Classe", ordering="id_classe__nome")
    def classe_nome(self, obj):
        return obj.id_classe.nome

    @admin.display(description="Subclasse", ordering="id_subclasse__nome")
    def subclasse_nome(self, obj):
        return obj.id_subclasse.nome if obj.id_subclasse else "-"


@admin.register(TbRecursoclasse)
class TbRecursoclasseAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "classe_nome", "subclasse_nome", "nivel", "valor")
    list_filter = ("id_classe", "id_subclasse", "nivel")
    search_fields = ("nome", "slug", "valor", "id_classe__nome", "id_subclasse__nome")
    autocomplete_fields = ("id_classe", "id_subclasse")
    ordering = ("id_classe__nome", "nivel", "nome")

    @admin.display(description="Classe", ordering="id_classe__nome")
    def classe_nome(self, obj):
        return obj.id_classe.nome

    @admin.display(description="Subclasse", ordering="id_subclasse__nome")
    def subclasse_nome(self, obj):
        return obj.id_subclasse.nome if obj.id_subclasse else "-"


class TbLinhagemInline(admin.TabularInline):
    model = TbLinhagem
    extra = 0
    fields = ("nome", "slug", "descricao")
    prepopulated_fields = {"slug": ("nome",)}
    show_change_link = True


class TbTracoracialInline(admin.TabularInline):
    model = TbTracoracial
    fk_name = "id_raca"
    extra = 0
    fields = ("nome", "nivel_requisito", "talento_racial", "pre_requisito", "id_linhagem", "id_essencia", "descricao")
    autocomplete_fields = ("id_linhagem", "id_essencia")
    show_change_link = True


@admin.register(TbRaca)
class TbRacaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "permite_essencia_badge", "linhagens_count", "tracos_count")
    list_filter = ("permite_essencia",)
    search_fields = ("nome", "slug", "tagline", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tagline", "permite_essencia")}),
        ("Lore", {"classes": ("collapse",), "fields": ("lore_presentation", "lore_roleplay", "lore_society")}),
    )
    inlines = (TbLinhagemInline, TbTracoracialInline)

    @admin.display(description="Essencia", boolean=True)
    def permite_essencia_badge(self, obj):
        return obj.permite_essencia

    @admin.display(description="Linhagens")
    def linhagens_count(self, obj):
        return obj.linhagens.count()

    @admin.display(description="Tracos")
    def tracos_count(self, obj):
        return obj.tracos.count()


@admin.register(TbLinhagem)
class TbLinhagemAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "raca_nome", "slug", "short_description")
    list_filter = ("id_raca",)
    search_fields = ("nome", "slug", "descricao", "id_raca__nome")
    autocomplete_fields = ("id_raca",)
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("id_raca__nome", "nome")
    fieldsets = (
        (None, {"fields": ("id_raca", "nome", "slug", "descricao")}),
        ("Lore", {"classes": ("collapse",), "fields": ("lore_presentation", "lore_roleplay", "lore_society")}),
    )

    @admin.display(description="Raca", ordering="id_raca__nome")
    def raca_nome(self, obj):
        return obj.id_raca.nome


@admin.register(TbEssencia)
class TbEssenciaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "tracos_count")
    search_fields = ("nome", "slug", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)

    @admin.display(description="Tracos")
    def tracos_count(self, obj):
        return obj.tracos.count()


@admin.register(TbTracoracial)
class TbTracoracialAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbtracoracial/change_list.html"
    list_display = ("nome", "origem_badge", "nivel_requisito", "talento_racial", "pre_requisito_curto", "short_description")
    list_filter = ("talento_racial", "nivel_requisito", "id_raca", "id_linhagem", "id_essencia")
    search_fields = ("nome", "descricao", "pre_requisito", "id_raca__nome", "id_linhagem__nome", "id_essencia__nome")
    autocomplete_fields = ("id_raca", "id_linhagem", "id_essencia")
    ordering = ("nivel_requisito", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "nivel_requisito", "talento_racial", "pre_requisito")}),
        ("Origem", {"fields": ("id_raca", "id_linhagem", "id_essencia")}),
        ("Texto em Markdown", {"fields": ("descricao",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar/",
                self.admin_site.admin_view(self.importar_tracos_view),
                name="home_tbtracoracial_importar",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbtracoracial_importar")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_tracos_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar tracos raciais em massa",
            "form": TracoRacialBulkImportForm(),
            "preview": [],
            "errors": [],
            "payload": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbtracoracial/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = TracoRacialBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/home/tbtracoracial/import_form.html", context)

            tracos = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            created = 0
            updated = 0

            with transaction.atomic():
                for item in tracos:
                    query = TbTracoracial.objects.filter(
                        nome=item["nome"],
                        id_raca_id=item["id_raca"],
                        id_linhagem_id=item["id_linhagem"],
                        id_essencia_id=item["id_essencia"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.descricao = item["descricao"]
                        existing.nivel_requisito = item["nivel_requisito"]
                        existing.talento_racial = item["talento_racial"]
                        existing.pre_requisito = item["pre_requisito"]
                        existing.save()
                        updated += 1
                        continue
                    if existing and not atualizar_existentes:
                        continue

                    TbTracoracial.objects.create(
                        nome=item["nome"],
                        descricao=item["descricao"],
                        nivel_requisito=item["nivel_requisito"],
                        talento_racial=item["talento_racial"],
                        pre_requisito=item["pre_requisito"],
                        id_raca_id=item["id_raca"],
                        id_linhagem_id=item["id_linhagem"],
                        id_essencia_id=item["id_essencia"],
                    )
                    created += 1

            messages.success(request, f"Importacao concluida: {created} criados, {updated} atualizados.")
            return redirect("admin:home_tbtracoracial_changelist")

        form = TracoRacialBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_tracos_raciais_txt(content)
            context.update({
                "preview": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbtracoracial/import_form.html", context)

    @admin.display(description="Origem")
    def origem_badge(self, obj):
        if obj.id_raca:
            return format_html('<span class="admin-badge">Raca: {}</span>', obj.id_raca.nome)
        if obj.id_linhagem:
            return format_html('<span class="admin-badge">Linhagem: {}</span>', obj.id_linhagem.nome)
        if obj.id_essencia:
            return format_html('<span class="admin-badge">Essencia: {}</span>', obj.id_essencia.nome)
        return "-"

    @admin.display(description="Pre-requisito")
    def pre_requisito_curto(self, obj):
        return Truncator(obj.pre_requisito or "-").chars(55)


@admin.register(TbMapMarker)
class TbMapMarkerAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "pin_preview", "categoria", "territorio", "lat", "lng")
    search_fields = ("nome", "categoria", "territorio")
    list_filter = ("categoria", "territorio")
    ordering = ("territorio", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "categoria")}),
        ("Coordenadas", {"fields": ("lat", "lng")}),
        ("Localização", {"fields": ("territorio",)}),
    )

    @admin.display(description="Pin")
    def pin_preview(self, obj):
        from django.utils.safestring import mark_safe
        return mark_safe(
            '<span style="background:#f27007;width:12px;height:12px;border-radius:50%;display:inline-block;"></span>'
        )


@admin.register(TbTalento)
class TbTalentoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbtalento/change_list.html"
    list_display = ("nome", "tipo_badge", "etiquetas_badges", "pre_requisito_curto", "atributos_badges", "descricao_curta")
    list_filter = ("tipo", "etiqueta", "atrib_forca", "atrib_destreza", "atrib_constituicao", "atrib_inteligencia", "atrib_sabedoria", "atrib_carisma")
    search_fields = ("nome", "slug", "descricao", "etiqueta", "etiquetas_adicionais", "pre_requisito")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tipo", "etiqueta", "etiquetas_adicionais", "pre_requisito")}),
        ("Aumento de atributo", {"fields": ("atrib_forca", "atrib_destreza", "atrib_constituicao", "atrib_inteligencia", "atrib_sabedoria", "atrib_carisma")}),
        ("Texto em Markdown", {"fields": ("descricao",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar/",
                self.admin_site.admin_view(self.importar_talentos_view),
                name="home_tbtalento_importar",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbtalento_importar")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_talentos_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar talentos em massa",
            "form": TalentoBulkImportForm(),
            "preview": None,
            "errors": [],
            "payload": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbtalento/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = TalentoBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/home/tbtalento/import_form.html", context)

            talentos = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            created = 0
            updated = 0

            with transaction.atomic():
                for item in talentos:
                    existing = TbTalento.objects.filter(slug=item["slug"]).first()
                    if existing and atualizar_existentes:
                        existing.nome = item["nome"]
                        existing.tipo = item["tipo"]
                        existing.etiqueta = item["etiqueta"]
                        existing.etiquetas_adicionais = item["etiquetas_adicionais"]
                        existing.pre_requisito = item["pre_requisito"]
                        existing.descricao = item["descricao"]
                        existing.atrib_forca = item.get("atrib_forca", False)
                        existing.atrib_destreza = item.get("atrib_destreza", False)
                        existing.atrib_constituicao = item.get("atrib_constituicao", False)
                        existing.atrib_inteligencia = item.get("atrib_inteligencia", False)
                        existing.atrib_sabedoria = item.get("atrib_sabedoria", False)
                        existing.atrib_carisma = item.get("atrib_carisma", False)
                        existing.save()
                        updated += 1
                        continue

                    slug = _unique_slug(item["slug"])
                    TbTalento.objects.create(
                        nome=item["nome"],
                        slug=slug,
                        tipo=item["tipo"],
                        etiqueta=item["etiqueta"],
                        etiquetas_adicionais=item["etiquetas_adicionais"],
                        pre_requisito=item["pre_requisito"],
                        descricao=item["descricao"],
                        atrib_forca=item.get("atrib_forca", False),
                        atrib_destreza=item.get("atrib_destreza", False),
                        atrib_constituicao=item.get("atrib_constituicao", False),
                        atrib_inteligencia=item.get("atrib_inteligencia", False),
                        atrib_sabedoria=item.get("atrib_sabedoria", False),
                        atrib_carisma=item.get("atrib_carisma", False),
                    )
                    created += 1

            messages.success(request, f"Importacao concluida: {created} criados, {updated} atualizados.")
            return redirect("admin:home_tbtalento_changelist")

        form = TalentoBulkImportForm(request.POST, request.FILES)
        context["form"] = form

        if form.is_valid():
            content = _decode_upload(form.cleaned_data["arquivo"])
            talentos, errors = _parse_talentos_txt(content, form.cleaned_data["tipo"])
            context.update({
                "preview": talentos,
                "errors": errors,
                "payload": json.dumps(talentos, ensure_ascii=False),
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbtalento/import_form.html", context)

    @admin.display(description="Tipo", ordering="tipo")
    def tipo_badge(self, obj):
        return format_html('<span class="admin-badge admin-badge-hot">{}</span>', obj.get_tipo_display())

    @admin.display(description="Etiquetas")
    def etiquetas_badges(self, obj):
        labels = [obj.get_etiqueta_display()]
        if obj.etiquetas_adicionais:
            labels.extend([tag.strip() for tag in obj.etiquetas_adicionais.split(",") if tag.strip()])
        return format_html(" ".join('<span class="admin-badge">{}</span>' for _ in labels), *labels)

    @admin.display(description="Pre-requisito")
    def pre_requisito_curto(self, obj):
        return Truncator(obj.pre_requisito or "Nenhum").chars(55)

    @admin.display(description="Atributos")
    def atributos_badges(self, obj):
        attrs = []
        if obj.atrib_forca:
            attrs.append("FOR")
        if obj.atrib_destreza:
            attrs.append("DES")
        if obj.atrib_constituicao:
            attrs.append("CON")
        if obj.atrib_inteligencia:
            attrs.append("INT")
        if obj.atrib_sabedoria:
            attrs.append("SAB")
        if obj.atrib_carisma:
            attrs.append("CAR")
        if not attrs:
            return mark_safe('<span class="admin-muted">Nenhum</span>')
        return format_html(" ".join('<span class="admin-badge admin-badge-soft">{}</span>' for _ in attrs), *attrs)

    @admin.display(description="Descricao")
    def descricao_curta(self, obj):
        return Truncator((obj.descricao or "").replace("\n", " ")).chars(90)


@admin.register(TbOpcaojogo)
class TbOpcaojogoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbopcaojogo/change_list.html"
    list_display = ("nome", "tipo", "etiquetas_adicionais", "pre_requisito", "slug", "short_description")
    list_filter = ("tipo",)
    search_fields = ("nome", "slug", "tipo", "descricao", "pre_requisito", "etiquetas_adicionais")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("tipo", "nome")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar/",
                self.admin_site.admin_view(self.importar_opcoes_view),
                name="home_tbopcaojogo_importar",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbopcaojogo_importar")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_opcoes_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar opcoes de jogo em massa",
            "form": OpcaoJogoBulkImportForm(),
            "preview": None,
            "errors": [],
            "payload": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbopcaojogo/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = OpcaoJogoBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/home/tbopcaojogo/import_form.html", context)

            opcoes = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            created = 0
            updated = 0
            access_created = 0

            with transaction.atomic():
                for item in opcoes:
                    existing = TbOpcaojogo.objects.filter(slug=item["slug"]).first()
                    if existing and atualizar_existentes:
                        opcao = existing
                        opcao.nome = item["nome"]
                        opcao.tipo = item["tipo"]
                        opcao.etiquetas_adicionais = item["etiquetas_adicionais"]
                        opcao.pre_requisito = item["pre_requisito"]
                        opcao.descricao = item["descricao"]
                        opcao.save()
                        updated += 1
                    else:
                        opcao = TbOpcaojogo.objects.create(
                            nome=item["nome"],
                            slug=_unique_option_slug(item["slug"]),
                            tipo=item["tipo"],
                            etiquetas_adicionais=item["etiquetas_adicionais"],
                            pre_requisito=item["pre_requisito"],
                            descricao=item["descricao"],
                        )
                        created += 1

                    access_items = item.get("classes", []) + item.get("subclasses", [])
                    if access_items:
                        TbAcessoopcao.objects.filter(id_opcao=opcao).delete()
                        for classe in item.get("classes", []):
                            _, made = TbAcessoopcao.objects.get_or_create(
                                id_opcao=opcao,
                                id_classe_id=classe["id"],
                                id_subclasse=None,
                                defaults={"nivel_recebimento": item["nivel_recebimento"]},
                            )
                            if made:
                                access_created += 1
                        for subclasse in item.get("subclasses", []):
                            _, made = TbAcessoopcao.objects.get_or_create(
                                id_opcao=opcao,
                                id_classe=None,
                                id_subclasse_id=subclasse["id"],
                                defaults={"nivel_recebimento": item["nivel_recebimento"]},
                            )
                            if made:
                                access_created += 1

            messages.success(
                request,
                f"Importacao concluida: {created} opcoes criadas, {updated} atualizadas, {access_created} acessos criados.",
            )
            return redirect("admin:home_tbopcaojogo_changelist")

        form = OpcaoJogoBulkImportForm(request.POST, request.FILES)
        context["form"] = form

        if form.is_valid():
            content = _decode_upload(form.cleaned_data["arquivo"])
            opcoes, errors = _parse_opcoes_jogo_txt(content)
            context.update({
                "preview": opcoes,
                "errors": errors,
                "payload": json.dumps(opcoes, ensure_ascii=False),
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbopcaojogo/import_form.html", context)


@admin.register(TbAcessoopcao)
class TbAcessoopcaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("id_opcao", "id_classe", "id_subclasse")
    list_filter = ("id_opcao", "id_classe", "id_subclasse")
    autocomplete_fields = ("id_opcao", "id_classe", "id_subclasse")
    search_fields = ("id_opcao__nome", "id_classe__nome", "id_subclasse__nome")


@admin.register(TbRegiao)
class TbRegiaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "territorio", "categoria", "etiquetas_adicionais")
    list_filter = ("categoria", "territorio")
    search_fields = ("nome", "slug", "territorio", "etiquetas_adicionais")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("territorio", "nome")


@admin.register(TbTerritorio)
class TbTerritorioAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "color_preview", "short_description")
    search_fields = ("nome", "slug", "descricao_breve", "lore_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "imagem_url", "descricao_breve")}),
        ("Atributos", {"fields": (
            "riqueza_natural", "riqueza_monetaria", "poder_militar", 
            "desenvolvimento_tecnologico", "estabilidade_politica_interna", 
            "ameacas_externas", "diplomacia", "manipulacao_trama"
        )}),
        ("Mapa", {"fields": ("cor_hex", "coordenadas_poligono")}),
        ("Lore", {"fields": ("lore_markdown",)}),
    )

    @admin.display(description="Cor")
    def color_preview(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<span style="display:inline-block;width:24px;height:24px;'
            'border-radius:4px;border:1px solid #333;background-color:{};">'
            '</span> {}',
            obj.cor_hex or '#ffffff',
            obj.cor_hex or '#ffffff',
        )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'cor_hex':
            from django.forms import TextInput
            kwargs['widget'] = TextInput(attrs={'type': 'color', 'style': 'width:60px;height:36px;padding:2px;cursor:pointer;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(TbItemMundano)
class TbItemMundanoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "categoria", "subcategoria", "preco", "peso")
    list_filter = ("categoria", "subcategoria")
    search_fields = ("nome", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {
            "fields": ("nome", "slug", "categoria", "subcategoria", "preco", "peso", "imagem_url")
        }),
        ("Propriedades de Combate (Armas)", {
            "fields": ("dano", "propriedades", "maestria"),
            "classes": ("collapse",),
        }),
        ("Propriedades de Armadura", {
            "fields": ("ca", "forca_minima", "furtividade_desvantagem"),
            "classes": ("collapse",),
        }),
        ("Descrição", {
            "fields": ("descricao_markdown",)
        }),
    )


@admin.register(TbItemMagico)
class TbItemMagicoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "raridade", "tipo", "slot", "requer_sintonizacao")
    list_filter = ("raridade", "slot", "requer_sintonizacao")
    search_fields = ("nome", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {
            "fields": ("nome", "slug", "tipo", "raridade", "slot", "imagem_url")
        }),
        ("Sintonização", {
            "fields": ("requer_sintonizacao", "detalhes_sintonizacao"),
        }),
        ("Descrição", {
            "fields": ("descricao_markdown",)
        }),
    )


_original_admin_get_urls = admin.site.get_urls


def _bonfire_admin_get_urls():
    custom_urls = [
        path(
            "markdown-editor/",
            admin.site.admin_view(markdown_editor_view),
            name="markdown_editor",
        ),
        path(
            "mongo/",
            admin.site.admin_view(mongo_collections_view),
            name="mongo_collections",
        ),
        path(
            "mongo/spells/import-excel/",
            admin.site.admin_view(spell_excel_import_view),
            name="spell_excel_import",
        ),
        path(
            "mongo-document/",
            admin.site.admin_view(mongo_document_edit_view),
            name="mongo_document_edit",
        ),
        path(
            "mongo-document/delete/",
            admin.site.admin_view(mongo_document_delete_view),
            name="mongo_document_delete",
        ),
        path(
            "mongo/<path:collection_name>/",
            admin.site.admin_view(mongo_collection_detail_view),
            name="mongo_collection_detail",
        ),
    ]
    return custom_urls + _original_admin_get_urls()


admin.site.get_urls = _bonfire_admin_get_urls
