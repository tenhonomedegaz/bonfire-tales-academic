import json
import math
import re
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db import models, transaction

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator, slugify

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
    TbMagia,
)
from .security import validate_json_no_sql_danger, validate_no_sql_danger


admin.site.site_header = "Bonfire Tales Admin"
admin.site.site_title = "Bonfire Tales Admin"
admin.site.index_title = "Painel de Conteudo"
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser


def download_backup_view(request):
    from django.apps import apps
    from django.core import serializers
    from django.http import HttpResponse
    import json
    from datetime import datetime

    if not (request.user.is_active and request.user.is_superuser):
        return HttpResponse("Proibido", status=403)

    home_models = apps.get_app_config('home').get_models()
    model_order_names = [
        'tbraca', 'tblinhagem', 'tbessencia', 'tbtracoracial',
        'tbclasse', 'tbsubclasse', 'tbclassehabilidade', 'tbrecursoclasse',
        'tbopcaojogo', 'tbacessoopcao', 'tbtalento',
        'tbregiao', 'tbterritorio', 'tbmapmarker',
        'tbcronica', 'tbjornal', 'tbitemmundano', 'tbitemmagico', 'tbmagia'
    ]
    sorted_models = []
    model_dict = {m._meta.model_name: m for m in home_models}
    for name in model_order_names:
        if name in model_dict:
            sorted_models.append(model_dict.pop(name))
    sorted_models.extend(model_dict.values())

    records = []
    for model in sorted_models:
        try:
            qs = model.objects.all().order_by('pk')
            if qs.exists():
                serialized = serializers.serialize('python', qs)
                records.extend(serialized)
        except Exception:
            continue

    response_data = json.dumps(records, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
    filename = f"backup_site_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response = HttpResponse(response_data, content_type="application/json; charset=utf-8")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def markdown_editor_view(request):
    context = {
        **admin.site.each_context(request),
        "title": "Editor Markdown",
    }
    return render(request, "admin/markdown_editor.html", context)


def _admin_console_paths():
    site_dir = Path(settings.BASE_DIR).resolve()
    bot_dir = Path(getattr(settings, "BOT_PROJECT_DIR", site_dir.parent / "bonfire-bot-main")).resolve()
    if not bot_dir.exists():
        for alt_name in ("BonfireBot-main", "BonfireBot", "bonfirebot-main"):
            alt_dir = site_dir.parent / alt_name
            if alt_dir.exists():
                bot_dir = alt_dir
                break
    return {
        "site": {
            "label": "Site Django",
            "path": site_dir,
            "env_path": site_dir / ".env",
            "log_path": site_dir / "site_console.log",
        },
        "bot": {
            "label": "Bot Discord",
            "path": bot_dir,
            "env_path": bot_dir / ".env",
            "log_path": _latest_bot_log_path(bot_dir),
        },
    }


def _latest_bot_log_path(bot_dir):
    log_dir = bot_dir / "log"
    if not log_dir.exists():
        return None
    # Try multiple patterns: pm2-style, dated, and plain
    patterns = ["*log-combined.log", "*.log", "*combined*.log"]
    for pattern in patterns:
        try:
            log_files = [f for f in log_dir.glob(pattern) if f.is_file() and f.stat().st_size > 0]
        except OSError:
            continue
        if log_files:
            return max(log_files, key=lambda item: item.stat().st_mtime)
    # Fallback: any .log file at all, even empty
    try:
        log_files = list(log_dir.glob("*.log"))
    except OSError:
        return None
    if log_files:
        return max(log_files, key=lambda item: item.stat().st_mtime)
    return None


def _tail_file(path, lines=150, missing_message="Arquivo nao encontrado."):
    if not path:
        return f"{missing_message}\n(caminho nao definido)"
    path = Path(path)
    if not path.exists():
        return f"{missing_message}\n(verificado: {path})"
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            content = handle.readlines()
    except PermissionError:
        return f"Sem permissao para ler: {path}"
    except OSError as exc:
        return f"Erro ao ler arquivo: {exc}\n(caminho: {path})"
    return "".join(content[-lines:]) if content else "Log vazio."


def _console_history_path():
    return Path(settings.BASE_DIR) / "admin_console_history.jsonl"


def _append_console_history(entry):
    entry = {
        **entry,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with _console_history_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_console_history(limit=40):
    path = _console_history_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(entries))


def _run_admin_console_command(target, command):
    paths = _admin_console_paths()
    target_info = paths.get(target)
    if not target_info:
        raise ValueError("Pasta alvo invalida.")
    if not target_info["path"].exists():
        raise FileNotFoundError(f"Pasta nao encontrada: {target_info['path']}")

    completed = subprocess.run(
        command,
        cwd=target_info["path"],
        shell=True,
        text=True,
        capture_output=True,
        timeout=120,
        encoding="utf-8",
        errors="replace",
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    return completed.returncode, output or "Comando executado sem saida."


def _read_env_content(path):
    path = Path(path)
    if not path.exists():
        return f"# Arquivo .env nao encontrado em: {path}"
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"# Sem permissao para ler: {path}"
    except OSError as exc:
        return f"# Erro ao ler: {exc}"


def _write_env_content(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    path.write_text(content.replace("\r\n", "\n"), encoding="utf-8")


def server_logs_view(request):
    from django.contrib.auth.hashers import check_password

    console_paths = _admin_console_paths()
    is_authenticated = bool(request.session.get("admin_console_authenticated"))
    command_result = None
    selected_target = request.POST.get("target") or request.GET.get("target") or "site"

    context = {
        **admin.site.each_context(request),
        "title": "Console do Servidor",
        "is_authenticated": is_authenticated,
        "targets": console_paths,
        "selected_target": selected_target if selected_target in console_paths else "site",
        "command_text": "",
        "command_result": None,
    }

    if request.method == "POST":
        action = request.POST.get("action", "refresh")
        if action == "authenticate":
            password = request.POST.get("server_password", "")
            expected_hash = getattr(settings, 'SERVER_LOGS_PASSWORD_HASH', '')
            if check_password(password, expected_hash):
                request.session["admin_console_authenticated"] = True
                context["is_authenticated"] = True
                messages.success(request, "Acesso ao console liberado.")
            else:
                messages.error(request, "Senha incorreta.")
        elif not context["is_authenticated"]:
            messages.error(request, "Autentique o console antes de continuar.")
        elif action == "run_command":
            command_text = request.POST.get("command", "").strip()
            context["command_text"] = command_text
            if not command_text:
                messages.error(request, "Informe um comando para executar.")
            else:
                try:
                    return_code, output = _run_admin_console_command(context["selected_target"], command_text)
                    command_result = {
                        "target": context["selected_target"],
                        "target_label": console_paths[context["selected_target"]]["label"],
                        "command": command_text,
                        "return_code": return_code,
                        "output": output[-12000:],
                    }
                    _append_console_history(command_result)
                    if return_code == 0:
                        messages.success(request, "Comando executado.")
                    else:
                        messages.warning(request, f"Comando terminou com codigo {return_code}.")
                except Exception as exc:
                    command_result = {
                        "target": context["selected_target"],
                        "target_label": console_paths.get(context["selected_target"], {}).get("label", context["selected_target"]),
                        "command": command_text,
                        "return_code": "erro",
                        "output": str(exc),
                    }
                    _append_console_history(command_result)
                    messages.error(request, f"Falha ao executar comando: {exc}")
        elif action == "save_env":
            env_target = request.POST.get("env_target", "site")
            env_content = request.POST.get("env_content", "")
            if env_target not in console_paths:
                messages.error(request, "Env alvo invalido.")
            else:
                try:
                    _write_env_content(console_paths[env_target]["env_path"], env_content)
                    messages.success(request, f".env do {console_paths[env_target]['label']} salvo com backup automatico.")
                except OSError as exc:
                    messages.error(request, f"Falha ao salvar .env: {exc}")

    if context["is_authenticated"]:
        bot_path_info = console_paths["bot"]
        context["site_log"] = _tail_file(
            console_paths["site"]["log_path"],
            missing_message="Arquivo site_console.log nao encontrado.",
        )
        context["bot_log"] = _tail_file(
            bot_path_info["log_path"],
            missing_message=f"Log do bot nao encontrado. Pasta do bot: {bot_path_info['path']} (existe: {bot_path_info['path'].exists()})",
        )
        context["history"] = _read_console_history()
        context["command_result"] = command_result
        context["site_env_content"] = _read_env_content(console_paths["site"]["env_path"])
        context["bot_env_content"] = _read_env_content(bot_path_info["env_path"])

    return render(request, "admin/server_logs.html", context)


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
        queryset=TbClasse.objects.none(),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['classe'].queryset = TbClasse.objects.all().order_by("nome")

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class RacaBulkImportForm(forms.Form):
    raca = forms.ModelChoiceField(
        label="Raça",
        queryset=TbRaca.objects.none(),
        help_text="Raça que receberá os traços e talentos do arquivo.",
    )
    arquivo = forms.FileField(
        label="Arquivo .txt",
        help_text="Use blocos separados por ---.",
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar registros existentes",
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['raca'].queryset = TbRaca.objects.all().order_by("nome")

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        position = uploaded.tell()
        content = _decode_upload(uploaded)
        uploaded.seek(position)
        validate_no_sql_danger(content, "arquivo")
        return uploaded


class RacaBulkConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    raca_id = forms.IntegerField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


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


class MagiaExcelImportForm(forms.Form):
    arquivo = forms.FileField(
        label="Arquivo .xlsx",
        help_text='Use a planilha com a aba "Versão Final pra Import".',
    )
    atualizar_existentes = forms.BooleanField(
        label="Atualizar magias existentes pelo slug",
        required=False,
        initial=True,
    )

    def clean_arquivo(self):
        uploaded = self.cleaned_data["arquivo"]
        if not uploaded.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx.")
        return uploaded


class MagiaExcelConfirmForm(forms.Form):
    payload = forms.CharField(widget=forms.HiddenInput)
    atualizar_existentes = forms.BooleanField(required=False, widget=forms.HiddenInput)


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


def _unique_spell_slug(base_slug, current_slug=None):
    slug = base_slug or "magia"
    candidate = slug
    counter = 2
    query = TbMagia.objects.all()
    if current_slug:
        query = query.exclude(slug=current_slug)

    while query.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _split_csv_text(value):
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", str(value)) if part.strip()]


def _parse_spell_level(value):
    text = str(value or "").strip().lower()
    if not text:
        return 0
    if text in {"c", "cantrip", "truque", "truques"}:
        return 0
    match = re.search(r"\d+", text)
    if not match:
        raise ValueError(f"Nivel invalido: {value}")
    level = int(match.group(0))
    if level < 0 or level > 9:
        raise ValueError(f"Nivel fora do intervalo 0-9: {value}")
    return level


def _parse_excel_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "sim", "s", "yes", "y", "verdadeiro"}


def _normalize_duration(value):
    text = str(value or "").strip()
    if not text:
        return "", False
    normalized = _normalize_label(text)
    if "concentracao" not in normalized:
        return text, False
    cleaned = re.sub(r"(?i)\bconcentra[cç][aã]o\b\s*,?\s*(at[eé]\s*)?", "", text).strip(" ,;-")
    return cleaned or text, True


def _parse_magias_xlsx(uploaded_file):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise forms.ValidationError("A dependencia openpyxl nao esta instalada.") from exc

    try:
        workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    except Exception as exc:
        raise forms.ValidationError(f"Nao foi possivel ler o Excel: {exc}") from exc

    sheet_name = "Versão Final pra Import"
    if sheet_name not in workbook.sheetnames:
        raise forms.ValidationError(f'A aba "{sheet_name}" nao foi encontrada.')

    worksheet = workbook[sheet_name]
    rows = worksheet.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers:
        raise forms.ValidationError("A planilha esta vazia.")

    aliases = {
        "nome": "nome",
        "lvl": "nivel",
        "nivel": "nivel",
        "cating_time": "casting_time",
        "casting_time": "casting_time",
        "ritual_booleana": "ritual",
        "ritual": "ritual",
        "duracao": "duracao",
        "escola": "escola",
        "alcance": "alcance",
        "componentes": "componentes",
        "classes_nome_do_bonfas": "classes",
        "classes": "classes",
        "subclasses_nome_do_bonfas": "subclasses",
        "subclasses": "subclasses",
        "descricao": "descricao",
        "higher_lvls": "em_niveis_superiores",
        "em_niveis_superiores": "em_niveis_superiores",
    }
    header_map = {
        index: aliases.get(_normalize_label(header))
        for index, header in enumerate(headers)
        if header is not None
    }
    required = {"nome", "nivel", "casting_time", "ritual", "duracao", "escola", "alcance", "componentes", "descricao"}
    missing = sorted(required - set(header for header in header_map.values() if header))
    if missing:
        raise forms.ValidationError("Colunas obrigatorias ausentes: " + ", ".join(missing))

    spells = []
    errors = []
    for row_number, row in enumerate(rows, start=2):
        record = {}
        for index, value in enumerate(row):
            field = header_map.get(index)
            if field:
                record[field] = value

        nome = str(record.get("nome") or "").strip()
        if not nome:
            continue

        try:
            nivel = _parse_spell_level(record.get("nivel"))
        except ValueError as exc:
            errors.append(f"Linha {row_number}: {exc}")
            continue

        duracao, concentracao = _normalize_duration(record.get("duracao"))
        item = {
            "nome": nome,
            "slug": slugify(nome),
            "nivel": nivel,
            "nivel_display": "Truque" if nivel == 0 else str(nivel),
            "casting_time": str(record.get("casting_time") or "").strip(),
            "ritual": _parse_excel_bool(record.get("ritual")),
            "duracao": duracao,
            "concentracao": concentracao,
            "escola": str(record.get("escola") or "").strip(),
            "alcance": str(record.get("alcance") or "").strip(),
            "componentes": str(record.get("componentes") or "").strip(),
            "classes": str(record.get("classes") or "").strip(),
            "subclasses": str(record.get("subclasses") or "").strip(),
            "descricao": str(record.get("descricao") or "").strip(),
            "em_niveis_superiores": str(record.get("em_niveis_superiores") or "").strip(),
        }
        item["tags_json"] = [
            tag for tag in (
                item["nivel_display"],
                item["escola"],
                *_split_csv_text(item["classes"]),
                *_split_csv_text(item["subclasses"]),
            )
            if tag
        ]
        try:
            validate_no_sql_danger(item, f"linha {row_number}")
        except forms.ValidationError as exc:
            errors.append(f"Linha {row_number}: {exc}")
            continue
        spells.append(item)

    return spells, errors


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
            "tags_json": _parse_tags_json(tags),
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


def _parse_key_value_block(block, known_keys=None):
    data = {}
    labels = {}
    current_key = None

    for line in block.split("\n"):
        if current_key == "descricao":
            data[current_key] = f"{data[current_key]}\n{line}".strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            norm_key = _normalize_label(key)
            if known_keys is None or norm_key in known_keys:
                current_key = norm_key
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


def _parse_tags_json(value):
    value = (value or "").strip()
    if not value:
        return []
    if value.startswith("[") or value.startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return parsed if isinstance(parsed, (list, dict)) else [parsed]
    return [
        item.strip()
        for item in re.split(r"[,;\n]+", value)
        if item.strip()
    ]


def _format_tags_preview(tags_json):
    if not tags_json:
        return "-"
    if isinstance(tags_json, list):
        return ", ".join(str(tag) for tag in tags_json[:6])
    return Truncator(json.dumps(tags_json, ensure_ascii=False)).chars(80)


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
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
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
            "tags_json": tags_json,
            "id_raca": raca.id_raca if raca else None,
            "id_linhagem": linhagem.id_linhagem if linhagem else None,
            "id_essencia": essencia.id_essencia if essencia else None,
            "origem_tipo": origem_tipo,
            "origem_nome": origem_nome,
        })

    if not tracos and not errors:
        errors.append("Nenhum traco racial foi encontrado. Confira se os blocos estao separados por ---.")

    return tracos, errors


RACA_ESSENCIA_KNOWN_KEYS = {
    "tipo", "slug", "nome", "raca", "raça", "linhagem", "essencia", "essência",
    "nivel", "nível", "nivel_requisito", "talento", "talento_racial", "opcional",
    "pre_requisito", "prerequisito", "requisito", "tags_json", "tagsjson", "tags",
    "tag", "etiquetas", "descricao", "descrição", "lore_apresentacao", "lore_apresentação",
    "lore_presentation", "lore_roleplay", "lore_sociedade", "lore_society", "tagline"
}


def _parse_raca_import_txt(content, raca):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    first_line = source.split("\n", 1)[0] if source else ""
    if _normalize_label(first_line).strip("[]") in {"tracos", "tracos_raciais"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    tracos = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block, known_keys=RACA_ESSENCIA_KNOWN_KEYS)
        
        tipo = data.get("tipo", "").strip().lower()
        if tipo == "raca" or tipo == "raça":
            slug = data.get("slug", "").strip()
            if slug and slug.lower() != raca.slug.lower():
                errors.append(f"Bloco {index}: raça '{slug}' no arquivo não corresponde à selecionada '{raca.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "raca",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "tagline": data.get("tagline", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo == "linhagem":
            slug = data.get("slug", "").strip()
            raca_slug = (data.get("raca") or data.get("raça") or "").strip()
            if raca_slug and raca_slug.lower() != raca.slug.lower():
                errors.append(f"Bloco {index}: a linhagem '{slug}' indica a raça '{raca_slug}', diferente da selecionada '{raca.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "linhagem",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "descricao": data.get("descricao", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo == "essencia" or tipo == "essência":
            continue

        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        
        nivel_raw = (data.get("nivel") or data.get("nivel_requisito") or "").strip()
        talento_racial = _parse_bool(
            data.get("talento_racial")
            or data.get("talento")
            or data.get("opcional")
        )
        
        if not nivel_raw:
            nivel = 1 if talento_racial else 0
        else:
            match = re.match(r'^(\d+)', nivel_raw)
            if match:
                nivel = int(match.group(1))
            else:
                nivel = 1 if talento_racial else 0

        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("requisito")
            or ""
        ).strip()
        
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
        )

        if not nome:
            errors.append(f"Bloco {index}: campo Nome ausente.")
            continue
        if not descricao:
            errors.append(f"Traco '{nome}': campo Descricao ausente.")
            continue

        raca_slug = (data.get("raca") or data.get("raça") or "").strip()
        linhagem_slug = (data.get("linhagem") or "").strip()
        essencia_slug = (data.get("essencia") or data.get("essência") or "").strip()

        if essencia_slug:
            continue

        target_linhagem = None
        if linhagem_slug:
            linhagem_obj = TbLinhagem.objects.filter(slug=linhagem_slug, id_raca=raca).first()
            has_linhagem_in_file = any(
                item.get("tipo_registro") == "linhagem" and item.get("slug") == linhagem_slug
                for item in tracos
            )
            if not linhagem_obj and not has_linhagem_in_file:
                errors.append(f"Traco '{nome}': linhagem '{linhagem_slug}' nao encontrada.")
                continue

        tracos.append({
            "tipo_registro": "traco",
            "nome": nome,
            "descricao": descricao,
            "nivel_requisito": nivel,
            "talento_racial": talento_racial,
            "pre_requisito": pre_requisito or None,
            "tags_json": tags_json,
            "linhagem_slug": linhagem_slug,
            "raca_slug": raca.slug,
        })

    if not tracos and not errors:
        errors.append("Nenhum traco racial foi encontrado no arquivo.")

    return tracos, errors


def _parse_essencia_import_txt(content, essencia):
    source = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    first_line = source.split("\n", 1)[0] if source else ""
    if _normalize_label(first_line).strip("[]") in {"tracos", "tracos_raciais"}:
        source = "\n".join(source.split("\n")[1:]).strip()

    tracos = []
    errors = []

    for index, block in enumerate(_split_blocks(source), start=1):
        data = _parse_key_value_block(block, known_keys=RACA_ESSENCIA_KNOWN_KEYS)
        
        tipo = data.get("tipo", "").strip().lower()
        if tipo == "essencia" or tipo == "essência":
            slug = data.get("slug", "").strip()
            if slug and slug.lower() != essencia.slug.lower():
                errors.append(f"Bloco {index}: essência '{slug}' no arquivo não corresponde à selecionada '{essencia.slug}'.")
                continue
            
            tracos.append({
                "tipo_registro": "essencia",
                "slug": slug,
                "nome": data.get("nome", "").strip(),
                "lore_presentation": data.get("lore_apresentacao") or data.get("lore_presentation") or "",
                "lore_roleplay": data.get("lore_roleplay") or "",
                "lore_society": data.get("lore_sociedade") or data.get("lore_society") or "",
            })
            continue

        if tipo in {"raca", "linhagem"}:
            continue

        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()
        
        nivel_raw = (data.get("nivel") or data.get("nivel_requisito") or "").strip()
        talento_racial = _parse_bool(
            data.get("talento_racial")
            or data.get("talento")
            or data.get("opcional")
        )
        
        if not nivel_raw:
            nivel = 1 if talento_racial else 0
        else:
            match = re.match(r'^(\d+)', nivel_raw)
            if match:
                nivel = int(match.group(1))
            else:
                nivel = 1 if talento_racial else 0

        pre_requisito = (
            data.get("pre_requisito")
            or data.get("prerequisito")
            or data.get("requisito")
            or ""
        ).strip()
        
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
        )

        if not nome:
            errors.append(f"Bloco {index}: campo Nome ausente.")
            continue
        if not descricao:
            errors.append(f"Traco '{nome}': campo Descricao ausente.")
            continue

        raca_slug = (data.get("raca") or data.get("raça") or "").strip()
        linhagem_slug = (data.get("linhagem") or "").strip()
        essencia_slug = (data.get("essencia") or data.get("essência") or "").strip()

        if essencia_slug and essencia_slug.lower() != essencia.slug.lower():
            errors.append(f"Traco '{nome}': essência '{essencia_slug}' não corresponde à essência selecionada '{essencia.slug}'.")
            continue

        tracos.append({
            "tipo_registro": "traco",
            "nome": nome,
            "descricao": descricao,
            "nivel_requisito": nivel,
            "talento_racial": talento_racial,
            "pre_requisito": pre_requisito or None,
            "tags_json": tags_json,
            "id_essencia": essencia.id_essencia,
            "id_raca": None,
            "id_linhagem": None,
            "essencia_nome": essencia.nome,
        })

    if not tracos and not errors:
        errors.append("Nenhum traço foi encontrado no arquivo.")

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
                "tags_json": _parse_tags_json(tags),
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
        tags_json = _parse_tags_json(
            data.get("tags_json")
            or data.get("tagsjson")
            or data.get("tags")
            or data.get("tag")
            or data.get("etiquetas")
        )
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
            "tags_json": tags_json,
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
            "multiclass_armas",
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
                        nivel=item["nivel"],
                        nome=item["nome"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.id_subclasse_id = item["id_subclasse"]
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
                        niveladquirido=item["niveladquirido"],
                        nome=item["nome"],
                    )
                    existing = query.first()
                    if existing and atualizar_existentes:
                        existing.id_subclasse_id = item["id_subclasse"]
                        existing.descricao = item["descricao"]
                        existing.table_only = item["table_only"]
                        existing.tags_json = item["tags_json"]
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
                        tags_json=item["tags_json"],
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
    list_display = ("nome", "classe_nome", "subclasse_nome", "niveladquirido", "table_only", "tags_preview", "short_description")
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

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


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
    fields = ("nome", "nivel_requisito", "talento_racial", "pre_requisito", "tags_json", "id_linhagem", "id_essencia", "descricao")
    autocomplete_fields = ("id_linhagem", "id_essencia")
    show_change_link = True


@admin.register(TbRaca)
class TbRacaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbraca/change_list.html"
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-arquivo/",
                self.admin_site.admin_view(self.importar_arquivo_view),
                name="home_tbraca_importar_arquivo",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbraca_importar_arquivo")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar traços e talentos de raça",
            "form": RacaBulkImportForm(),
            "preview_tracos": [],
            "errors": [],
            "payload": "",
            "raca_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbraca/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = RacaBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Não foi possível confirmar a importação.")
                return render(request, "admin/home/tbraca/import_form.html", context)

            raca = get_object_or_404(TbRaca, pk=confirm_form.cleaned_data["raca_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            tracos_criados = tracos_atualizados = linhagens_criadas = linhagens_atualizadas = 0
            raca_metadata_atualizado = False

            with transaction.atomic():
                for item in payload:
                    tipo_reg = item.get("tipo_registro", "traco")
                    if tipo_reg == "raca":
                        if item["slug"] == raca.slug:
                            raca.tagline = item.get("tagline") or raca.tagline
                            raca.lore_presentation = item.get("lore_presentation") or raca.lore_presentation
                            raca.lore_roleplay = item.get("lore_roleplay") or raca.lore_roleplay
                            raca.lore_society = item.get("lore_society") or raca.lore_society
                            raca.save()
                            raca_metadata_atualizado = True
                    elif tipo_reg == "linhagem":
                        linhagem, created = TbLinhagem.objects.get_or_create(
                            slug=item["slug"],
                            defaults={"id_raca": raca, "nome": item["nome"]}
                        )
                        linhagem.descricao = item.get("descricao") or linhagem.descricao
                        linhagem.lore_presentation = item.get("lore_presentation") or linhagem.lore_presentation
                        linhagem.lore_roleplay = item.get("lore_roleplay") or linhagem.lore_roleplay
                        linhagem.lore_society = item.get("lore_society") or linhagem.lore_society
                        linhagem.save()
                        if created:
                            linhagens_criadas += 1
                        else:
                            linhagens_atualizadas += 1
                    else:
                        linhagem_obj = None
                        if item.get("linhagem_slug"):
                            linhagem_obj = TbLinhagem.objects.filter(slug=item["linhagem_slug"], id_raca=raca).first()
                        
                        query = TbTracoracial.objects.filter(
                            nome=item["nome"],
                            id_raca_id=raca.id_raca,
                            id_linhagem=linhagem_obj,
                            id_essencia=None,
                        )
                        existing = query.first()
                        if existing and atualizar_existentes:
                            existing.descricao = item["descricao"]
                            existing.nivel_requisito = item["nivel_requisito"]
                            existing.talento_racial = item["talento_racial"]
                            existing.pre_requisito = item["pre_requisito"]
                            existing.tags_json = item["tags_json"]
                            existing.save()
                            tracos_atualizados += 1
                            continue
                        if existing and not atualizar_existentes:
                            continue

                        TbTracoracial.objects.create(
                            nome=item["nome"],
                            descricao=item["descricao"],
                            nivel_requisito=item["nivel_requisito"],
                            talento_racial=item["talento_racial"],
                            pre_requisito=item["pre_requisito"],
                            tags_json=item["tags_json"],
                            id_raca=raca,
                            id_linhagem=linhagem_obj,
                            id_essencia=None,
                        )
                        tracos_criados += 1

            msg = f"Importação concluída para a raça {raca.nome}:"
            if raca_metadata_atualizado:
                msg += " metadados da raça atualizados;"
            if linhagens_criadas or linhagens_atualizadas:
                msg += f" {linhagens_criadas} linhagens criadas, {linhagens_atualizadas} atualizadas;"
            msg += f" {tracos_criados} traços/talentos criados, {tracos_atualizados} atualizados."
            messages.success(request, msg)
            return redirect("admin:home_tbraca_changelist")

        form = RacaBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            raca = form.cleaned_data["raca"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_raca_import_txt(content, raca)
            context.update({
                "preview_tracos": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "raca_id": raca.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbraca/import_form.html", context)


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
    change_list_template = "admin/home/tbessencia/change_list.html"
    list_display = ("nome", "slug", "tracos_count")
    search_fields = ("nome", "slug", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug")}),
        ("Lore", {"classes": ("collapse",), "fields": ("lore_presentation", "lore_roleplay", "lore_society")}),
    )

    @admin.display(description="Tracos")
    def tracos_count(self, obj):
        return obj.tracos.count()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-arquivo/",
                self.admin_site.admin_view(self.importar_arquivo_view),
                name="home_tbessencia_importar_arquivo",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbessencia_importar_arquivo")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_arquivo_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar traços e talentos de essência",
            "form": EssenciaBulkImportForm(),
            "preview_tracos": [],
            "errors": [],
            "payload": "",
            "essencia_id": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/home/tbessencia/import_form.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = EssenciaBulkConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Não foi possível confirmar a importação.")
                return render(request, "admin/home/tbessencia/import_form.html", context)

            essencia = get_object_or_404(TbEssencia, pk=confirm_form.cleaned_data["essencia_id"])
            payload = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            tracos_criados = tracos_atualizados = 0
            essencia_metadata_atualizado = False

            with transaction.atomic():
                for item in payload:
                    tipo_reg = item.get("tipo_registro", "traco")
                    if tipo_reg == "essencia":
                        if item["slug"] == essencia.slug:
                            essencia.lore_presentation = item.get("lore_presentation") or essencia.lore_presentation
                            essencia.lore_roleplay = item.get("lore_roleplay") or essencia.lore_roleplay
                            essencia.lore_society = item.get("lore_society") or essencia.lore_society
                            essencia.save()
                            essencia_metadata_atualizado = True
                    else:
                        query = TbTracoracial.objects.filter(
                            nome=item["nome"],
                            id_essencia_id=essencia.id_essencia,
                            id_raca=None,
                            id_linhagem=None,
                        )
                        existing = query.first()
                        if existing and atualizar_existentes:
                            existing.descricao = item["descricao"]
                            existing.nivel_requisito = item["nivel_requisito"]
                            existing.talento_racial = item["talento_racial"]
                            existing.pre_requisito = item["pre_requisito"]
                            existing.tags_json = item["tags_json"]
                            existing.save()
                            tracos_atualizados += 1
                            continue
                        if existing and not atualizar_existentes:
                            continue

                        TbTracoracial.objects.create(
                            nome=item["nome"],
                            descricao=item["descricao"],
                            nivel_requisito=item["nivel_requisito"],
                            talento_racial=item["talento_racial"],
                            pre_requisito=item["pre_requisito"],
                            tags_json=item["tags_json"],
                            id_essencia=essencia,
                            id_raca=None,
                            id_linhagem=None,
                        )
                        tracos_criados += 1

            msg = f"Importação concluída para a essência {essencia.nome}:"
            if essencia_metadata_atualizado:
                msg += " metadados da essência atualizados;"
            msg += f" {tracos_criados} traços/talentos criados, {tracos_atualizados} atualizados."
            messages.success(request, msg)
            return redirect("admin:home_tbessencia_changelist")

        form = EssenciaBulkImportForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            essencia = form.cleaned_data["essencia"]
            content = _decode_upload(form.cleaned_data["arquivo"])
            tracos, errors = _parse_essencia_import_txt(content, essencia)
            context.update({
                "preview_tracos": tracos,
                "errors": errors,
                "payload": json.dumps(tracos, ensure_ascii=False),
                "essencia_id": essencia.pk,
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/home/tbessencia/import_form.html", context)


@admin.register(TbTracoracial)
class TbTracoracialAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbtracoracial/change_list.html"
    list_display = ("nome", "origem_badge", "nivel_requisito", "talento_racial", "pre_requisito_curto", "tags_preview", "short_description")
    list_filter = ("talento_racial", "nivel_requisito", "id_raca", "id_linhagem", "id_essencia")
    search_fields = ("nome", "descricao", "pre_requisito", "id_raca__nome", "id_linhagem__nome", "id_essencia__nome")
    autocomplete_fields = ("id_raca", "id_linhagem", "id_essencia")
    ordering = ("nivel_requisito", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "nivel_requisito", "talento_racial", "pre_requisito", "tags_json")}),
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
                        existing.tags_json = item["tags_json"]
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
                        tags_json=item["tags_json"],
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

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


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
    list_display = ("nome", "tipo_badge", "etiquetas_badges", "tags_preview", "pre_requisito_curto", "atributos_badges", "descricao_curta")
    list_filter = ("tipo", "etiqueta", "atrib_forca", "atrib_destreza", "atrib_constituicao", "atrib_inteligencia", "atrib_sabedoria", "atrib_carisma")
    search_fields = ("nome", "slug", "descricao", "etiqueta", "etiquetas_adicionais", "pre_requisito")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tipo", "etiqueta", "etiquetas_adicionais", "tags_json", "pre_requisito")}),
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
                        existing.tags_json = item["tags_json"]
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
                        tags_json=item["tags_json"],
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

    @admin.display(description="Tags JSON")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)

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
    list_display = ("nome", "tipo", "etiquetas_adicionais", "tags_preview", "pre_requisito", "slug", "short_description")
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
                        opcao.tags_json = item["tags_json"]
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
                            tags_json=item["tags_json"],
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

    @admin.display(description="Tags JSON")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


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
    list_display = ("nome", "categoria", "subcategoria", "preco", "peso", "tags_preview")
    list_filter = ("categoria", "subcategoria")
    search_fields = ("nome", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {
            "fields": ("nome", "slug", "categoria", "subcategoria", "preco", "peso", "imagem_url", "tags_json")
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

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


@admin.register(TbItemMagico)
class TbItemMagicoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "raridade", "tipo", "slot", "requer_sintonizacao", "tags_preview")
    list_filter = ("raridade", "slot", "requer_sintonizacao")
    search_fields = ("nome", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {
            "fields": ("nome", "slug", "tipo", "raridade", "slot", "imagem_url", "tags_json")
        }),
        ("Sintonização", {
            "fields": ("requer_sintonizacao", "detalhes_sintonizacao"),
        }),
        ("Descrição", {
            "fields": ("descricao_markdown",)
        }),
    )

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


# ─────────────────────────────────────────────────────────────────────────────
# Tabelas do Bot (Prisma) — somente leitura no admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TbMagia)
class TbMagiaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbmagia/change_list.html"
    list_display = ("nome", "nivel_display", "escola", "casting_time", "ritual", "concentracao", "alcance", "tags_preview")
    list_filter = ("nivel", "escola", "ritual", "concentracao")
    search_fields = ("nome", "slug", "escola", "classes", "subclasses", "descricao", "em_niveis_superiores")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nivel", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "slug", "nivel", "escola", "tags_json")}),
        ("Conjuracao", {"fields": ("casting_time", "ritual", "duracao", "concentracao", "alcance", "componentes")}),
        ("Acesso", {"fields": ("classes", "subclasses")}),
        ("Texto", {"fields": ("descricao", "em_niveis_superiores")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importar-excel/",
                self.admin_site.admin_view(self.importar_excel_view),
                name="home_tbmagia_importar_excel",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_url"] = reverse("admin:home_tbmagia_importar_excel")
        return super().changelist_view(request, extra_context=extra_context)

    def importar_excel_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar magias por Excel",
            "form": MagiaExcelImportForm(),
            "preview": None,
            "errors": [],
            "payload": "",
            "atualizar_existentes": True,
        }

        if request.method != "POST":
            return render(request, "admin/spell_import.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = MagiaExcelConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/spell_import.html", context)

            magias = json.loads(confirm_form.cleaned_data["payload"])
            atualizar_existentes = confirm_form.cleaned_data["atualizar_existentes"]
            created = 0
            updated = 0

            with transaction.atomic():
                for item in magias:
                    existing = TbMagia.objects.filter(slug=item["slug"]).first()
                    if existing and atualizar_existentes:
                        magia = existing
                        magia.nome = item["nome"]
                        magia.nivel = item["nivel"]
                        magia.casting_time = item["casting_time"]
                        magia.ritual = item["ritual"]
                        magia.duracao = item["duracao"]
                        magia.concentracao = item["concentracao"]
                        magia.escola = item["escola"]
                        magia.alcance = item["alcance"]
                        magia.componentes = item["componentes"]
                        magia.classes = item["classes"]
                        magia.subclasses = item["subclasses"]
                        magia.descricao = item["descricao"]
                        magia.em_niveis_superiores = item["em_niveis_superiores"]
                        magia.tags_json = item["tags_json"]
                        magia.save()
                        updated += 1
                    else:
                        TbMagia.objects.create(
                            nome=item["nome"],
                            slug=_unique_spell_slug(item["slug"]),
                            nivel=item["nivel"],
                            casting_time=item["casting_time"],
                            ritual=item["ritual"],
                            duracao=item["duracao"],
                            concentracao=item["concentracao"],
                            escola=item["escola"],
                            alcance=item["alcance"],
                            componentes=item["componentes"],
                            classes=item["classes"],
                            subclasses=item["subclasses"],
                            descricao=item["descricao"],
                            em_niveis_superiores=item["em_niveis_superiores"],
                            tags_json=item["tags_json"],
                        )
                        created += 1

            messages.success(request, f"Importacao concluida: {created} magias criadas, {updated} atualizadas.")
            return redirect("admin:home_tbmagia_changelist")

        form = MagiaExcelImportForm(request.POST, request.FILES)
        context["form"] = form

        if form.is_valid():
            try:
                magias, errors = _parse_magias_xlsx(form.cleaned_data["arquivo"])
            except forms.ValidationError as exc:
                magias, errors = [], exc.messages
            context.update({
                "preview": magias,
                "errors": errors,
                "payload": json.dumps(magias, ensure_ascii=False),
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
        return render(request, "admin/spell_import.html", context)

    @admin.display(description="Nivel", ordering="nivel")
    def nivel_display(self, obj):
        return "Truque" if obj.nivel == 0 else obj.nivel

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)


from .models import (
    BotQuest,
    BotMember,
    BotTransaction,
    BotSchedulerJob,
    BotDedicatedRank,
    BotCharacterLog,
    BotKeyValueStore,
)





@admin.register(BotQuest)
class BotQuestAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'questMaster', 'questDate', 'playersAmount', 'isPublished')
    list_filter = ('status', 'isPublished', 'type')
    search_fields = ('name', 'questMaster', 'description')
    ordering = ('-questDate',)




@admin.register(BotMember)
class BotMemberAdmin(admin.ModelAdmin):
    list_display = ('discordUserTag', 'discordUserId', 'email', 'isModerator', 'isAdmin', 'tokenSuperboost', 'tokenXpBoost', 'tokenMission')
    list_filter = ('isModerator', 'isAdmin', 'skipValidation')
    search_fields = ('discordUserTag', 'discordUserId', 'email')
    ordering = ('discordUserTag',)


@admin.register(BotTransaction)
class BotTransactionAdmin(admin.ModelAdmin):
    list_display = ('transactionCode', 'name', 'email', 'subscriptionPlan', 'status', 'grossAmount', 'paymentDate', 'claimed')
    list_filter = ('status', 'claimed', 'subscriptionPlan')
    search_fields = ('transactionCode', 'name', 'email')
    ordering = ('-paymentDate',)


@admin.register(BotSchedulerJob)
class BotSchedulerJobAdmin(admin.ModelAdmin):
    list_display = ('name', 'nextRunAt')
    search_fields = ('name',)
    ordering = ('nextRunAt',)


@admin.register(BotDedicatedRank)
class BotDedicatedRankAdmin(admin.ModelAdmin):
    list_display = ('priorityRankName', 'isActive', 'isPriorityLocked', 'validFrom', 'validUntil')
    list_filter = ('isActive', 'isPriorityLocked')
    ordering = ('-validFrom',)


@admin.register(BotCharacterLog)
class BotCharacterLogAdmin(admin.ModelAdmin):
    list_display = ('characterName', 'discordUserTag', 'className', 'rankName', 'level', 'adventuresPlayed', 'isNovice')
    list_filter = ('rankName', 'className', 'isNovice')
    search_fields = ('characterName', 'discordUserTag', 'discordUserId')
    ordering = ('characterName',)


@admin.register(BotKeyValueStore)
class BotKeyValueStoreAdmin(admin.ModelAdmin):
    list_display = ('key', 'updatedAt')
    search_fields = ('key',)
    ordering = ('key',)


_original_admin_get_urls = admin.site.get_urls


def _bonfire_admin_get_urls():
    custom_urls = [
        path(
            "server-logs/",
            admin.site.admin_view(server_logs_view),
            name="server_logs",
        ),
        path(
            "markdown-editor/",
            admin.site.admin_view(markdown_editor_view),
            name="markdown_editor",
        ),
        path(
            "download-backup/",
            admin.site.admin_view(download_backup_view),
            name="download_backup",
        ),
    ]
    return custom_urls + _original_admin_get_urls()


admin.site.get_urls = _bonfire_admin_get_urls


_original_get_app_list = admin.site.get_app_list

def _bonfire_admin_get_app_list(request, app_label=None):
    app_dict = admin.site._build_app_dict(request)
    if app_label:
        return _original_get_app_list(request, app_label)
        
    home_app = app_dict.get('home')
    auth_app = app_dict.get('auth')
    
    if auth_app:
        auth_app['name'] = 'Autenticação'
        
    if home_app:
        site_models = []
        bot_models = []
        for model in home_app['models']:
            if model['object_name'].startswith('Bot'):
                bot_models.append(model)
            else:
                site_models.append(model)
                
        home_app['name'] = 'Tables Site'
        home_app['models'] = site_models
        
        bot_app = {
            'name': 'Tables Bot',
            'app_label': 'tables_bot',
            'app_url': '',
            'has_module_perms': True,
            'models': bot_models,
        }
        
        # Order: Autenticação, Tables Bot, Tables Site, others
        app_list = []
        if auth_app:
            app_list.append(auth_app)
        app_list.append(bot_app)
        app_list.append(home_app)
        
        for app in app_dict.values():
            if app['app_label'] not in ('home', 'auth'):
                app_list.append(app)
                
        return app_list
        
    return sorted(app_dict.values(), key=lambda x: x['name'].lower())

admin.site.get_app_list = _bonfire_admin_get_app_list
