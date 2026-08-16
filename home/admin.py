import json
import re
import subprocess
import time
import types
import unicodedata
from datetime import datetime
from pathlib import Path

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
    AsaasCheckoutOrder,
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbEssencia,
    TbLinhagem,
    TbMapLayer,
    TbMapMarker,
    TbMapDesenho,
    TbOpcaojogo,
    TbOrganizacao,
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
    TbAntecedente,
    TbBestiario,
    TbArmadilha,
    TbCondicao,
    TbTransacao,
    TbPersonagem,
    TbPersonagemAventura,
    TbPersonagemRevisao,
    TbRecompensaMestre,
    TbAventuraMestre,
    TbTransacaoMestre,
    TbReiDaColina,
    TbConteudoEstatico,
)
from .security import validate_no_sql_danger


admin.site.site_header = "Bonfire Tales Admin"
admin.site.site_title = "Bonfire Tales Admin"
admin.site.index_title = "Painel de Conteudo"
# A permissao do site admin (has_permission) e sobrescrita mais abaixo, junto
# dos outros patches globais — ver _admin_superuser_only.


@admin.register(AsaasCheckoutOrder)
class AsaasCheckoutOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'discord_user_id', 'email', 'product_code', 'mode', 'amount', 'status',
                    'asaas_payment_id', 'created_at')
    list_filter = ('status', 'mode', 'product_code')
    search_fields = ('id', 'user__username', 'user__email', 'discord_user_id', 'email', 'asaas_checkout_id',
                     'asaas_payment_id')
    readonly_fields = ('id', 'user', 'discord_user_id', 'email', 'product_code', 'mode', 'amount',
                       'asaas_checkout_id', 'asaas_checkout_url', 'asaas_payment_id',
                       'paid_at', 'created_at', 'updated_at')


def download_backup_view(request):
    """Backup COMPLETO: todas as tabelas do app `home` (catálogo + dados de usuário:
    personagens, missões, mercado, etc.) MAIS o que é necessário pro login —
    `auth.Group` e `auth.User` (com senha-hash). FKs serializadas com chave natural
    (username/codename) para resolverem no restore mesmo com PKs diferentes. As FKs
    internas do catálogo (home→home) mantêm o PK. Ordem: Group, User, depois home (que
    referencia User)."""
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
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

    # auth primeiro (Group antes de User; User antes do home por causa de FK dono/autor)
    all_models = [Group, get_user_model()] + sorted_models

    records = []
    for model in all_models:
        try:
            qs = model.objects.all().order_by('pk')
            if qs.exists():
                records.extend(serializers.serialize('python', qs, use_natural_foreign_keys=True))
        except Exception:
            continue

    response_data = json.dumps(records, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)
    filename = f"backup_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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


CONSOLE_UNLOCK_TTL_SECONDS = 15 * 60


def server_logs_view(request):
    from django.contrib.auth.hashers import check_password

    console_paths = _admin_console_paths()
    # Flag legado (sem validade) de sessoes antigas — remover para forcar reautenticacao.
    request.session.pop("admin_console_authenticated", None)
    unlocked_at = request.session.get("admin_console_authenticated_at")
    is_authenticated = isinstance(unlocked_at, (int, float)) and (time.time() - unlocked_at) <= CONSOLE_UNLOCK_TTL_SECONDS
    if isinstance(unlocked_at, (int, float)) and not is_authenticated:
        request.session.pop("admin_console_authenticated_at", None)
        messages.info(request, "A liberacao do console expirou — digite a senha novamente.")
    elif is_authenticated:
        # Renovacao deslizante: qualquer request autenticado estende a liberacao.
        request.session["admin_console_authenticated_at"] = time.time()
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
        "op_result": None,
    }

    if request.method == "POST":
        action = request.POST.get("action", "refresh")
        if action == "authenticate":
            password = request.POST.get("server_password", "")
            expected_hash = getattr(settings, 'SERVER_LOGS_PASSWORD_HASH', '')
            if check_password(password, expected_hash):
                request.session["admin_console_authenticated_at"] = time.time()
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
        elif action == "restore_backup":
            f = request.FILES.get("arquivo")
            if not f:
                messages.error(request, "Selecione um arquivo .json de backup.")
            elif request.POST.get("confirmar") != "RESTAURAR":
                messages.error(request, "Digite RESTAURAR para confirmar (a operacao sobrescreve dados existentes).")
            else:
                try:
                    from io import StringIO
                    from django.core.management import call_command
                    from django.core import serializers
                    from django.db import connection, transaction
                    from .deploy_sync import RESTORE_GUARDED_MODELS
                    texto = f.read().decode("utf-8")

                    # Guard: um fixture que so tem modelos de CONTEUDO (catalogo, com
                    # PKs do dev) nao pode ser aplicado por PK aqui — colide com a
                    # producao. Esse arquivo deve ir pelo painel "Merge de conteudo".
                    blocked = False
                    try:
                        dados = json.loads(texto)
                    except (ValueError, TypeError):
                        dados = None
                    if isinstance(dados, list):
                        labels = {str(r.get("model", "")).lower() for r in dados if isinstance(r, dict)}
                        content_labels = {
                            "home." + nome.lower()
                            for nome in RESTORE_GUARDED_MODELS
                        }
                        if labels and labels <= content_labels:
                            blocked = True
                            messages.error(
                                request,
                                "Este arquivo e um fixture de CONTEUDO (so catalogo, com PKs do dev). "
                                "Restaurar por PK colide com a producao — use o painel 'Merge de "
                                "conteudo (dev -> producao)', que casa por slug.",
                            )
                            context["op_result"] = {
                                "titulo": "Restauracao — RECUSADA",
                                "output": "Fixture contem apenas modelos de conteudo (catalogo); nada foi aplicado.",
                            }

                    if not blocked:
                        n = 0
                        app_labels = set()
                        with transaction.atomic():
                            for obj in serializers.deserialize("json", texto):
                                app_labels.add(obj.object._meta.app_label)
                                obj.save()
                                n += 1
                            if connection.vendor == "postgresql" and app_labels:
                                buf = StringIO()
                                call_command("sqlsequencereset", *sorted(app_labels), stdout=buf)
                                sql = "\n".join(
                                    line for line in buf.getvalue().splitlines()
                                    if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
                                ).strip()
                                if sql:
                                    with connection.cursor() as cur:
                                        cur.execute(sql)
                        messages.success(request, f"Backup restaurado: {n} registros carregados.")
                        context["op_result"] = {"titulo": "Restauracao de backup",
                                                "output": f"{n} registros restaurados de {f.name} (upsert por PK; sequences realinhadas)."}
                except Exception as exc:
                    messages.error(request, f"Falha ao restaurar: {exc}")
                    context["op_result"] = {"titulo": "Restauracao — ERRO", "output": str(exc)}
        elif action == "merge_conteudo":
            f = request.FILES.get("arquivo")
            if not f:
                messages.error(request, "Selecione o arquivo de conteudo (conteudo.json do dev).")
            else:
                try:
                    from .deploy_sync import sincronizar_conteudo, relatorio_texto
                    texto = f.read().decode("utf-8")
                    rel = sincronizar_conteudo(texto)
                    saida = relatorio_texto(rel)
                    if rel["mem_ok"]:
                        messages.success(request, "Conteudo sincronizado. Memoria (usuarios/missoes) intacta.")
                    else:
                        messages.warning(request, "Sincronizado, MAS a contagem da memoria mudou — verifique!")
                    context["op_result"] = {"titulo": "Merge de conteudo (chave natural)", "output": saida}
                except Exception as exc:
                    messages.error(request, f"Falha no merge: {exc}")
                    context["op_result"] = {"titulo": "Merge de conteudo — ERRO", "output": str(exc)}

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
            "descricao": str(record.get("descricao") or "").strip(),
            "em_niveis_superiores": str(record.get("em_niveis_superiores") or "").strip(),
        }
        item["tags_json"] = [
            tag for tag in (
                item["nivel_display"],
                item["escola"],
                *_split_csv_text(item["classes"]),
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

    reserved_resource_keys = {"nivel", "subclasse", "tipo", "resource_type", "recurso_tipo", "reset", "recarga"}
    valid_resource_types = {"table-only", "consumable", "choice"}
    resource_type_aliases = {
        "apenas-tabela": "table-only",
        "apenas_tabela": "table-only",
        "tabela": "table-only",
        "table": "table-only",
        "table-only": "table-only",
        "consumivel": "consumable",
        "consumable": "consumable",
        "escolha": "choice",
        "choice": "choice",
        "pick": "choice",
    }

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
        tipo_raw = (data.get("tipo") or data.get("resource_type") or data.get("recurso_tipo") or "").strip()
        tipo = resource_type_aliases.get(slugify(tipo_raw), tipo_raw if tipo_raw in valid_resource_types else "")
        if tipo_raw and tipo not in valid_resource_types:
            errors.append(f"Recurso bloco {index}: tipo '{tipo_raw}' invalido. Use table-only, consumable ou choice.")
            continue
        reset = (data.get("reset") or data.get("recarga") or "").strip() or None

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
                "tipo": tipo or "table-only",
                "reset": reset,
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


class TbClassehabilidadeInline(admin.StackedInline):
    model = TbClassehabilidade
    extra = 0
    fields = ("nome", "niveladquirido", "id_subclasse", "table_only", "descricao")
    autocomplete_fields = ("id_subclasse",)
    ordering = ("niveladquirido", "nome")
    show_change_link = True


class TbRecursoclasseInline(admin.TabularInline):
    model = TbRecursoclasse
    extra = 0
    fields = ("nivel", "nome", "slug", "tipo", "valor", "reset", "id_subclasse")
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
                        existing.tipo = item.get("tipo") or "table-only"
                        existing.reset = item.get("reset")
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
                        tipo=item.get("tipo") or "table-only",
                        reset=item.get("reset"),
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
    search_fields = ("nome", "nome_ingles", "descricao", "id_classe__nome", "id_subclasse__nome")
    autocomplete_fields = ("id_classe", "id_subclasse")
    ordering = ("id_classe__nome", "niveladquirido", "nome")
    fields = ("id_classe", "id_subclasse", "nome", "nome_ingles", "niveladquirido",
              "table_only", "tags_json", "descricao")

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
    list_display = ("nome", "classe_nome", "subclasse_nome", "nivel", "tipo", "valor", "reset")
    list_filter = ("tipo", "reset", "id_classe", "id_subclasse", "nivel")
    search_fields = ("nome", "slug", "valor", "id_classe__nome", "id_subclasse__nome")
    autocomplete_fields = ("id_classe", "id_subclasse")
    ordering = ("id_classe__nome", "nivel", "nome")

    @admin.display(description="Classe", ordering="id_classe__nome")
    def classe_nome(self, obj):
        return obj.id_classe.nome

    @admin.display(description="Subclasse", ordering="id_subclasse__nome")
    def subclasse_nome(self, obj):
        return obj.id_subclasse.nome if obj.id_subclasse else "-"


@admin.register(TbBestiario)
class TbBestiarioAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_filter = ("tipo", "tamanho", "escala_com_dono", "companheiro_classe")
    search_fields = ("nome", "slug", "tipo")
    autocomplete_fields = ("companheiro_classe", "companheiro_subclasse")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    list_display = ("nome", "tipo", "tamanho", "nd", "companheiro_de", "escala_com_dono")
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tipo", "tamanho", "nd", "alinhamento", "imagem_url")}),
        ("Atalhos de display", {"fields": ("ca", "pv")}),
        ("Statblock (schema 5etools — importável do criador de mobs/Roll20)", {"fields": ("statblock_json",)}),
        ("Mecânica Bonfire (summon / motor da ficha)", {"fields": ("tags_json",)}),
        ("Companheiro", {"fields": ("companheiro_classe", "companheiro_subclasse", "escala_com_dono")}),
        ("Descrição", {"fields": ("descricao_markdown",)}),
    )

    @admin.display(description="Companheiro de")
    def companheiro_de(self, obj):
        return obj.companheiro_subclasse or obj.companheiro_classe or "-"


@admin.register(TbArmadilha)
class TbArmadilhaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_filter = ("tipo", "comunidade")
    search_fields = ("nome", "slug", "tipo")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    list_display = ("nome", "tipo", "nd", "comunidade", "autor")
    raw_id_fields = ("autor",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tipo", "nd")}),
        ("Mecânica", {"fields": ("gatilho", "deteccao", "desarme", "save_atributo", "save_cd", "dano", "efeito")}),
        ("Descrição", {"fields": ("descricao_markdown",)}),
        ("Origem", {"fields": ("comunidade", "autor")}),
    )


@admin.register(TbTransacao)
class TbTransacaoAdmin(admin.ModelAdmin):
    list_display = ("id_transacao", "id_personagem", "tipo", "descricao", "valor_pc", "saldo_pc", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("descricao", "id_personagem__nome")
    raw_id_fields = ("id_personagem",)
    readonly_fields = ("criado_em",)


@admin.register(TbPersonagem)
class TbPersonagemAdmin(BonfireAdminMixin, admin.ModelAdmin):
    """Ficha de personagem (memoria de usuario). Sem registro, a changelist
    /admin/home/tbpersonagem/ dava 404 e o modelo nem aparecia no indice do
    admin ("nao consigo acessar a table de personagens"). FKs em raw_id para
    nao carregar selects gigantes; timestamps auto em readonly."""

    list_display = (
        "nome", "dono", "nivel", "raca_display", "aventuras",
        "carteira_pc", "braseiros", "publico", "arquivado", "atualizado_em",
    )
    list_display_links = ("nome",)
    list_filter = ("arquivado", "publico", "nivel", "ficha_theme")
    search_fields = ("nome", "dono__username", "jogador", "patente")
    list_select_related = ("dono", "id_raca")
    ordering = ("-atualizado_em",)
    date_hierarchy = "criado_em"
    raw_id_fields = ("dono", "id_raca", "id_linhagem", "id_essencia", "id_antecedente")
    readonly_fields = ("criado_em", "atualizado_em")
    fieldsets = (
        ("Identidade", {"fields": (
            ("nome", "dono"),
            ("publico", "arquivado"),
            ("tagline", "jogador", "patente"),
        )}),
        ("Origem", {"fields": (
            ("id_raca", "id_linhagem"),
            ("id_essencia", "id_antecedente"),
        )}),
        ("Atributos", {"fields": (
            ("forca", "destreza", "constituicao"),
            ("inteligencia", "sabedoria", "carisma"),
        )}),
        ("Combate e vitais", {"fields": (
            ("nivel", "ca", "iniciativa_bonus"),
            ("pv_maximo", "pv_atual", "pv_temporario"),
            ("velocidade",),
        )}),
        ("Economia e progressao", {"fields": (
            ("carteira_pc", "braseiros"),
            ("aventuras",),
        )}),
        ("Descricao fisica", {"fields": (
            ("idade", "altura", "peso", "tamanho"),
            ("genero", "olhos", "cabelo", "pele"),
        )}),
        # `notas_jogador` (onda F) é o bloco de mesa da aba Ficha; `anotacoes` segue sendo
        # a lore da aba Informações. Os dois no mesmo fieldset porque a staff edita ambos.
        ("Narrativa", {"fields": ("aparencia", "historia", "anotacoes", "notas_jogador")}),
        ("Visual da ficha", {"fields": (
            ("foto_url", "token_url"),
            ("banner_url", "ficha_background_url"),
            ("ficha_theme", "ficha_effect", "foto_frame"),
            "ficha_theme_custom",
        )}),
        ("Metadados", {"fields": (("criado_em", "atualizado_em"),)}),
    )

    @admin.display(description="Raca", ordering="id_raca__nome")
    def raca_display(self, obj):
        return obj.id_raca.nome if obj.id_raca_id else "-"


@admin.register(TbPersonagemAventura)
class TbPersonagemAventuraAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("id_lancamento", "id_personagem", "nome_aventura", "data_missao",
                    "mestre_display", "qtd_aventuras", "ouro_pago_po", "nivel_no_lancamento",
                    "criado_por", "criado_em", "revertido")
    list_filter = ("revertido", "data_missao")
    search_fields = ("nome_aventura", "id_personagem__nome", "criado_por__username",
                     "id_mestre__username")
    raw_id_fields = ("id_personagem", "id_mestre", "criado_por", "revertido_por")
    readonly_fields = ("criado_em", "revertido_em", "ouro_pago_po", "mestre_display")

    @admin.display(description="Mestre")
    def mestre_display(self, obj):
        return obj.mestre_display


@admin.register(TbPersonagemRevisao)
class TbPersonagemRevisaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ('id_revisao', 'id_personagem', 'tipo', 'nivel_antes', 'nivel_depois',
                    'aventuras_no_momento', 'criado_por', 'criado_em', 'revertida')
    list_filter = ('tipo', 'revertida')
    search_fields = ('id_personagem__nome', 'descricao', 'criado_por__username')
    raw_id_fields = ('id_personagem', 'criado_por', 'revertida_por')
    readonly_fields = ('snapshot_json', 'criado_em', 'revertida_em')


@admin.register(TbRecompensaMestre)
class TbRecompensaMestreAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "preco_mm", "mensalidade_mm", "ativo", "ordem")
    list_filter = ("tipo", "ativo")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("ordem", "preco_mm")


@admin.register(TbAventuraMestre)
class TbAventuraMestreAdmin(admin.ModelAdmin):
    list_display = ("nome", "mestre", "data", "jogadores", "recompensa_mm", "criado_em")
    search_fields = ("nome", "mestre__username")
    raw_id_fields = ("mestre",)
    readonly_fields = ("criado_em",)


@admin.register(TbTransacaoMestre)
class TbTransacaoMestreAdmin(admin.ModelAdmin):
    list_display = ("id_transacao", "mestre", "tipo", "descricao", "valor_mm", "saldo_mm", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("descricao", "mestre__username")
    raw_id_fields = ("mestre",)
    readonly_fields = ("criado_em",)


@admin.register(TbReiDaColina)
class TbReiDaColinaAdmin(admin.ModelAdmin):
    list_display = ("id", "holder", "preco_atual", "desde")
    raw_id_fields = ("holder",)


@admin.register(TbMapLayer)
class TbMapLayerAdmin(admin.ModelAdmin):
    list_display = ("id_layer", "nome", "ordem", "publica", "imagem_url")
    list_editable = ("ordem", "publica")
    ordering = ("ordem",)


@admin.register(TbCondicao)
class TbCondicaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_filter = ("categoria",)
    search_fields = ("nome", "slug", "nome_en", "resumo")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("ordem", "nome")
    list_display = ("nome", "slug", "categoria", "resumo", "ordem")
    fieldsets = (
        (None, {"fields": ("nome", "nome_en", "slug", "categoria", "ordem")}),
        ("Conteúdo", {"fields": ("resumo", "definicao", "efeitos_json")}),
    )


class TbLinhagemInline(admin.StackedInline):
    model = TbLinhagem
    extra = 0
    fields = ("nome", "slug", "imagem_url", "descricao")
    prepopulated_fields = {"slug": ("nome",)}
    show_change_link = True


class TbTracoracialInline(admin.StackedInline):
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
        (None, {"fields": ("nome", "slug", "tagline", "imagem_url", "permite_essencia")}),
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
        (None, {"fields": ("id_raca", "nome", "slug", "imagem_url", "descricao")}),
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
        (None, {"fields": ("nome", "slug", "imagem_url", "tags_json")}),
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
    search_fields = ("nome", "nome_ingles", "descricao", "pre_requisito", "id_raca__nome", "id_linhagem__nome", "id_essencia__nome")
    autocomplete_fields = ("id_raca", "id_linhagem", "id_essencia")
    ordering = ("nivel_requisito", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "nome_ingles", "nivel_requisito", "talento_racial", "pre_requisito", "tags_json")}),
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
    list_display = ("nome", "pin_preview", "categoria", "territorio", "camada", "lat", "lng")
    search_fields = ("nome", "categoria", "territorio")
    list_filter = ("categoria", "territorio", "camada")
    ordering = ("territorio", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "categoria")}),
        ("Coordenadas", {"fields": ("lat", "lng")}),
        ("Localização", {"fields": ("territorio", "camada")}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'territorio':
            from django.forms import ChoiceField
            from .models import TbTerritorio
            try:
                choices = [('', '---------')] + [(t.nome, t.nome) for t in TbTerritorio.objects.all().order_by('nome')]
            except Exception:
                choices = [('', '---------')]
            return ChoiceField(choices=choices, required=False, label=db_field.verbose_name or db_field.name, help_text=db_field.help_text, initial=db_field.get_default())
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Pin")
    def pin_preview(self, obj):
        from django.utils.safestring import mark_safe
        return mark_safe(
            '<span style="background:#f27007;width:12px;height:12px;border-radius:50%;display:inline-block;"></span>'
        )


@admin.register(TbMapDesenho)
class TbMapDesenhoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("tipo", "nome", "camada", "ativo")
    list_filter = ("tipo", "camada", "ativo")
    search_fields = ("nome",)
    ordering = ("camada", "ordem", "id_desenho")


@admin.register(TbTalento)
class TbTalentoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/home/tbtalento/change_list.html"
    list_display = ("nome", "tipo_badge", "etiquetas_badges", "tags_preview", "pre_requisito_curto", "atributos_badges", "descricao_curta")
    list_filter = ("tipo", "etiqueta", "atrib_forca", "atrib_destreza", "atrib_constituicao", "atrib_inteligencia", "atrib_sabedoria", "atrib_carisma")
    search_fields = ("nome", "nome_ingles", "slug", "descricao", "etiqueta", "etiquetas_adicionais", "pre_requisito")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "nome_ingles", "slug", "tipo", "etiqueta", "etiquetas_adicionais", "tags_json", "pre_requisito")}),
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


@admin.register(TbAntecedente)
class TbAntecedenteAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "slug", "resumo")
    search_fields = ("nome", "slug", "descricao", "resumo", "pre_requisito", "proficiencias", "idiomas", "equipamento", "etiquetas_adicionais")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)


@admin.register(TbAcessoopcao)
class TbAcessoopcaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("id_opcao", "id_classe", "id_subclasse")
    list_filter = ("id_opcao", "id_classe", "id_subclasse")
    autocomplete_fields = ("id_opcao", "id_classe", "id_subclasse")
    search_fields = ("id_opcao__nome", "id_classe__nome", "id_subclasse__nome")


@admin.register(TbRegiao)
class TbRegiaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "territorio", "categoria", "camada", "etiquetas_adicionais")
    list_filter = ("categoria", "territorio", "camada")
    search_fields = ("nome", "slug", "territorio", "etiquetas_adicionais")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("territorio", "nome")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'territorio':
            from django.forms import ChoiceField
            from .models import TbTerritorio
            try:
                choices = [('', '---------')] + [(t.nome, t.nome) for t in TbTerritorio.objects.all().order_by('nome')]
            except Exception:
                choices = [('', '---------')]
            return ChoiceField(choices=choices, required=False, label=db_field.verbose_name or db_field.name, help_text=db_field.help_text, initial=db_field.get_default())
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(TbTerritorio)
class TbTerritorioAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "color_preview", "short_description", "camada")
    list_filter = ("camada",)
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
        ("Mapa", {"fields": ("cor_hex", "coordenadas_poligono", "camada")}),
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


@admin.register(TbOrganizacao)
class TbOrganizacaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "tipo", "sede")
    list_filter = ("tipo",)
    search_fields = ("nome", "slug", "tipo", "sede", "descricao")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tipo", "sede")}),
        ("Vinculos", {"fields": ("regioes", "territorios", "aliados", "inimigos")}),
        ("Detalhes", {"fields": ("lideranca", "tags", "descricao")}),
    )


@admin.register(TbItemMundano)
class TbItemMundanoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "categoria", "subcategoria", "preco", "peso", "tags_preview")
    list_filter = ("categoria", "subcategoria")
    search_fields = ("nome", "nome_ingles", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    readonly_fields = ("mecanica_resumo",)
    fieldsets = (
        (None, {
            "fields": ("nome", "slug", "categoria", "subcategoria", "preco", "peso", "imagem_url", "tags_json")
        }),
        ("Mecânica (derivada das tags)", {
            "fields": ("mecanica_resumo",),
        }),
        ("Descrição", {
            "fields": ("descricao_markdown",)
        }),
    )

    @admin.display(description="Tags")
    def tags_preview(self, obj):
        return _format_tags_preview(obj.tags_json)

    @admin.display(description="Mecânica (derivada das tags)")
    def mecanica_resumo(self, obj):
        from home.item_mecanica import mecanica_de_tags, dano_display, propriedades_display, ca_display

        mec = mecanica_de_tags(obj.tags_json, obj.subcategoria)
        partes = []
        dano = dano_display(mec)
        if dano:
            partes.append(format_html("<strong>Dano:</strong> {}", dano))
        ca = ca_display(mec)
        if ca:
            partes.append(format_html("<strong>CA:</strong> {}", ca))
        props = propriedades_display(mec)
        if props:
            partes.append(format_html("<strong>Propriedades:</strong> {}", props))
        if mec.get("maestrias"):
            partes.append(format_html("<strong>Maestrias:</strong> {}", ", ".join(mec["maestrias"])))
        if mec.get("forca_minima"):
            partes.append(format_html("<strong>Força mínima:</strong> {}", mec["forca_minima"]))
        if mec.get("furtividade_desvantagem"):
            partes.append(format_html("<strong>Furtividade:</strong> {}", "desvantagem"))
        if not partes:
            return "(sem mecânica derivada das tags)"
        return mark_safe("<br>".join(partes))


@admin.register(TbItemMagico)
class TbItemMagicoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "raridade", "tipo", "slot", "requer_sintonizacao", "tags_preview")
    list_filter = ("raridade", "slot", "requer_sintonizacao")
    search_fields = ("nome", "slug", "descricao_markdown")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {
            "fields": ("nome", "nome_ingles", "slug", "tipo", "raridade", "slot", "imagem_url", "tags_json")
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
    search_fields = ("nome", "nome_ingles", "slug", "escola", "classes", "descricao", "em_niveis_superiores")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nivel", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "nome_ingles", "slug", "nivel", "escola", "tags_json")}),
        ("Conjuracao", {"fields": ("casting_time", "ritual", "duracao", "concentracao", "alcance", "componentes")}),
        ("Acesso", {"fields": ("classes",)}),
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


@admin.register(TbConteudoEstatico)
class TbConteudoEstaticoAdmin(admin.ModelAdmin):
    list_display = ('pagina', 'ordem', 'titulo', 'chave', 'ativo', 'atualizado_em')
    list_filter = ('pagina', 'ativo')
    list_editable = ('ordem', 'ativo')
    search_fields = ('titulo', 'subtitulo', 'conteudo_markdown', 'chave')
    ordering = ('pagina', 'ordem', 'chave')
    readonly_fields = ('atualizado_em',)
    fieldsets = (
        ('Identificação', {'fields': ('pagina', 'chave', 'titulo', 'subtitulo')}),
        ('Conteúdo', {
            'fields': ('conteudo_markdown', 'imagem_url'),
            'description': (
                'Aceita Markdown Bonfire. A chave é o contrato estável usado pelo '
                'template; editar texto, imagem ou CTA não exige deploy.'
            ),
        }),
        ('Ação', {'fields': ('cta_texto', 'cta_url')}),
        ('Publicação', {'fields': ('ativo', 'ordem', 'atualizado_em')}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Personalização de perfil/ficha (F1) — CRUD do catálogo de cosméticos + inventário
# (import local pra não mexer no bloco de imports do topo, tocado por outro agente).
# ─────────────────────────────────────────────────────────────────────────────
from .models import TbCosmetico, TbUsuarioCosmetico


class _TbCosmeticoForm(forms.ModelForm):
    """Form do admin de cosméticos: valida a definicao_json do tema pelo
    sanitizador (hex-only, enums whitelisted). Para tipo != 'tema', força {} —
    a definição só faz sentido em temas."""
    class Meta:
        model = TbCosmetico
        fields = '__all__'

    def clean_definicao_json(self):
        from .cosmetics import sanitize_definicao_tema
        raw = self.cleaned_data.get('definicao_json')
        tipo = (self.data.get('tipo') or getattr(self.instance, 'tipo', '')).strip()
        if tipo != 'tema':
            return {}
        return sanitize_definicao_tema(raw)


@admin.register(TbCosmetico)
class TbCosmeticoAdmin(admin.ModelAdmin):
    form = _TbCosmeticoForm
    list_display = ('tipo', 'nome', 'slug', 'raridade', 'origem', 'escopo', 'ativo', 'ordem')
    list_filter = ('tipo', 'origem', 'raridade', 'ativo', 'escopo', 'animado')
    search_fields = ('nome', 'slug')
    list_editable = ('ativo', 'ordem')
    prepopulated_fields = {'slug': ('nome',)}
    fieldsets = (
        (None, {'fields': ('tipo', 'nome', 'slug', 'descricao', 'raridade')}),
        ('Render', {'fields': ('css_class', 'asset_url', 'asset_file', 'animado')}),
        ('Tema (dados)', {
            'fields': ('definicao_json', 'css_file'),
            'description': (
                'Só para tipo=Tema. definicao_json: {accent,accent2,surface,deep '
                '(#RRGGBB), gradiente (bool), particula (subir|cair|flutuar|nenhuma), '
                'vel (lenta|media|rapida), glow (bool)} — validado/sanitizado ao salvar. '
                'css_file: CSS avançado opcional (incluído via &lt;link&gt; quando o tema é equipado).'),
        }),
        ('Aquisição', {'fields': ('origem', 'preco', 'requer_plano')}),
        ('Disponibilidade', {'fields': ('escopo', 'ativo', 'ordem')}),
    )


@admin.register(TbUsuarioCosmetico)
class TbUsuarioCosmeticoAdmin(admin.ModelAdmin):
    list_display = ('user', 'cosmetico', 'origem', 'desbloqueado_em')
    list_filter = ('origem', 'cosmetico__tipo')
    search_fields = ('user__username', 'cosmetico__nome', 'cosmetico__slug')
    autocomplete_fields = ('user', 'cosmetico')
    readonly_fields = ('desbloqueado_em',)
    ordering = ('-desbloqueado_em',)


# ─────────────────────────────────────────────────────────────────────────────
# Conquistas (F3) — CRUD + concessão em massa (fonte única: conquistas.py).
# ─────────────────────────────────────────────────────────────────────────────
from .models import TbConquista, TbUsuarioConquista


class _ConcederConquistaForm(forms.Form):
    """Formulário da página intermediária de concessão em massa. Aceita usuários
    por multi-select E/OU uma lista colada de usernames (um por linha/vírgula)."""
    usuarios = forms.ModelMultipleChoiceField(
        queryset=None, required=False,
        widget=forms.SelectMultiple(attrs={'size': 14, 'style': 'min-width:280px'}),
        label='Selecionar usuários',
    )
    usernames = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 5, 'cols': 40}),
        label='Ou colar usernames',
        help_text='Um por linha ou separados por vírgula. Ignora vazios e desconhecidos.',
    )

    def __init__(self, *args, **kwargs):
        from django.contrib.auth import get_user_model
        super().__init__(*args, **kwargs)
        self.fields['usuarios'].queryset = (
            get_user_model().objects.filter(is_active=True).order_by('username'))

    def usuarios_resolvidos(self):
        """União de (multi-select ∪ usernames colados), sem duplicar. Retorna
        (users: list, desconhecidos: list[str])."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        selecionados = list(self.cleaned_data.get('usuarios') or [])
        por_pk = {u.pk: u for u in selecionados}
        desconhecidos = []
        texto = (self.cleaned_data.get('usernames') or '').replace(',', '\n')
        nomes = [n.strip() for n in texto.splitlines() if n.strip()]
        if nomes:
            # Django username é case-sensitive por padrão; casa também por lower.
            achados_lower = {u.username.lower(): u
                             for u in User.objects.filter(username__in=nomes)}
            for nome in nomes:
                u = achados_lower.get(nome.lower())
                if u:
                    por_pk[u.pk] = u
                else:
                    desconhecidos.append(nome)
        return list(por_pk.values()), desconhecidos


@admin.register(TbConquista)
class TbConquistaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'secreta', 'criterio', 'recompensa', 'ativo', 'ordem')
    list_filter = ('secreta', 'criterio', 'ativo')
    search_fields = ('nome', 'slug', 'descricao')
    list_editable = ('ativo', 'ordem')
    prepopulated_fields = {'slug': ('nome',)}
    raw_id_fields = ('recompensa',)
    fieldsets = (
        (None, {'fields': ('nome', 'slug', 'descricao', 'icone_url', 'icone_file')}),
        ('Visibilidade', {'fields': ('secreta', 'ativo', 'ordem')}),
        ('Critério', {'fields': ('criterio', 'criterio_json')}),
        ('Recompensa', {'fields': ('recompensa',),
                        'description': 'Cosmético desbloqueado no inventário ao conceder.'}),
    )
    actions = ('conceder_a_usuarios',)

    @admin.action(description='Conceder conquista(s) selecionada(s) a usuários…')
    def conceder_a_usuarios(self, request, queryset):
        """Ação com página intermediária: escolhe usuários (multi-select ou lista
        colada) e concede TODAS as conquistas selecionadas a TODOS eles, via
        conceder_conquista (idempotente, seta concedida_por=request.user)."""
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        from .conquistas import conceder_conquista

        conquistas = list(queryset)
        if request.POST.get('confirmar'):
            form = _ConcederConquistaForm(request.POST)
            if form.is_valid():
                users, desconhecidos = form.usuarios_resolvidos()
                if not users:
                    self.message_user(
                        request, 'Nenhum usuário válido informado.', level=messages.WARNING)
                else:
                    total_concedidas = total_ja = 0
                    for conq in conquistas:
                        for u in users:
                            if conceder_conquista(u, conq, por=request.user):
                                total_concedidas += 1
                            else:
                                total_ja += 1
                    self.message_user(
                        request,
                        '%d concessão(ões) nova(s) e %d já existente(s) em %d usuário(s) × %d conquista(s).'
                        % (total_concedidas, total_ja, len(users), len(conquistas)),
                        level=messages.SUCCESS)
                    if desconhecidos:
                        self.message_user(
                            request,
                            'Usernames ignorados (não encontrados): %s' % ', '.join(desconhecidos),
                            level=messages.WARNING)
                    return None  # volta pro changelist
        else:
            form = _ConcederConquistaForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Conceder conquistas a usuários',
            'conquistas': conquistas,
            'form': form,
            'action_checkbox_name': ACTION_CHECKBOX_NAME,
            'selected_ids': [str(c.pk) for c in conquistas],
            'opts': self.model._meta,
        }
        return render(request, 'admin/home/tbconquista/conceder.html', context)


@admin.register(TbUsuarioConquista)
class TbUsuarioConquistaAdmin(admin.ModelAdmin):
    list_display = ('user', 'conquista', 'concedida_em', 'concedida_por')
    list_filter = ('conquista', 'concedida_em')
    search_fields = ('user__username', 'conquista__nome', 'conquista__slug')
    autocomplete_fields = ('user', 'conquista', 'concedida_por')
    readonly_fields = ('concedida_em',)
    ordering = ('-concedida_em',)


# ─────────────────────────────────────────────────────────────────────────────
# UX GLOBAL DO ADMIN (aplicado a TODOS os ModelAdmin registrados)
#   1. Coluna "Excluir" por linha em toda changelist -> leva direto para a
#      pagina de confirmacao PADRAO do Django (mantem protecao de FK). Sem
#      precisar de checkbox + dropdown + "Go". A acao em massa continua existindo.
#   2. Campos com null=True deixam de ser tratados como obrigatorios ao editar
#      (reclamacao recorrente do PO: colunas NULL no banco viravam obrigatorias).
# Implementacao: patch unico no registry, depois de todos os register().
# ─────────────────────────────────────────────────────────────────────────────
def _bonfire_row_delete_link(obj):
    """Callable de list_display: link de exclusao por linha (1 clique)."""
    try:
        url = reverse(
            "admin:%s_%s_delete" % (obj._meta.app_label, obj._meta.model_name),
            args=[obj.pk],
        )
    except Exception:
        return ""
    return format_html(
        '<a class="bonfire-row-delete" href="{}" title="Excluir" '
        'aria-label="Excluir este registro">'
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">'
        '<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
        '<line x1="10" y1="11" x2="10" y2="17"/>'
        '<line x1="14" y1="11" x2="14" y2="17"/></svg>'
        '<span class="bonfire-row-delete-txt">Excluir</span></a>',
        url,
    )


_bonfire_row_delete_link.short_description = mark_safe(
    '<span class="bonfire-del-head">Excluir</span>'
)


def _bonfire_install_row_delete(model_admin):
    """Injeta a coluna de exclusao via get_list_display (respeita permissao).
    Usa MethodType para que continue sendo um metodo ligado (o system check do
    admin inspeciona `get_list_display.__func__`)."""
    if getattr(model_admin, "_bonfire_delete_installed", False):
        return
    model_admin._bonfire_delete_installed = True
    _orig_get_list_display = model_admin.get_list_display

    def get_list_display(self, request, _orig=_orig_get_list_display):
        display = list(_orig(request))
        try:
            can_delete = self.has_delete_permission(request)
        except Exception:
            can_delete = False
        if can_delete and _bonfire_row_delete_link not in display:
            display.append(_bonfire_row_delete_link)
        return display

    model_admin.get_list_display = types.MethodType(get_list_display, model_admin)


def _bonfire_install_nullable_optional(model_admin):
    """Campos null=True do modelo nao devem ser obrigatorios no form do admin."""
    if getattr(model_admin, "_bonfire_nullable_installed", False):
        return
    model_admin._bonfire_nullable_installed = True
    _orig_get_form = model_admin.get_form

    def get_form(request, obj=None, _orig=_orig_get_form, _self=model_admin, **kwargs):
        FormClass = _orig(request, obj, **kwargs)
        try:
            meta = _self.model._meta
        except Exception:
            return FormClass
        for field_name, form_field in FormClass.base_fields.items():
            if not form_field.required:
                continue
            try:
                model_field = meta.get_field(field_name)
            except Exception:
                continue
            # Coluna aceita NULL no banco -> pode ficar em branco no admin.
            if getattr(model_field, "null", False):
                form_field.required = False
        return FormClass

    model_admin.get_form = get_form


def _bonfire_patch_admin_registry():
    for model_admin in admin.site._registry.values():
        _bonfire_install_row_delete(model_admin)
        _bonfire_install_nullable_optional(model_admin)


_bonfire_patch_admin_registry()


def _admin_superuser_only(request):
    # Decisao do PO (2026-07-17): admin inteiro e so de superuser; staff usa os recursos inline do site.
    return bool(request.user and request.user.is_active and request.user.is_superuser)


# Assinatura sem self de proposito: o atributo de instancia sombreia o metodo
# bound de AdminSite, entao a funcao e chamada so com (request).
admin.site.has_permission = _admin_superuser_only
