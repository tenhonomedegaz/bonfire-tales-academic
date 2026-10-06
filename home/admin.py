import copy
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
from django.db import IntegrityError, models, transaction
from django.core import signing

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator, slugify

from .models import (
    AsaasCheckoutOrder,
    CosmeticCheckoutOffer,
    CosmeticCheckoutPurchase,
    EventCosmeticOffer,
    EventCosmeticRedemption,
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
    TbEmprestimoPersonagem,
    TbPersonagemTreinamento,
    TbSolicitacaoTranscricao,
    TbPersonagem,
    TbPersonagemAventura,
    TbPersonagemRevisao,
    TbRecompensaMestre,
    TbAventuraMestre,
    TbTransacaoMestre,
    TbReiDaColina,
    TbConteudoEstatico,
    TbTagLibraryRevision,
)
from .security import validate_no_sql_danger
from .conquista_admin_form import ConquistaAdminForm
from .organization_lists import organization_list


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


@admin.register(CosmeticCheckoutOffer)
class CosmeticCheckoutOfferAdmin(admin.ModelAdmin):
    list_display = ('cosmetico', 'amount', 'active')
    list_filter = ('active',)
    search_fields = ('cosmetico__slug', 'cosmetico__nome')
    autocomplete_fields = ('cosmetico',)


@admin.register(CosmeticCheckoutPurchase)
class CosmeticCheckoutPurchaseAdmin(admin.ModelAdmin):
    list_display = ('order', 'beneficiary', 'slug', 'payment_id', 'granted_at')
    search_fields = ('order__id', 'beneficiary__username', 'slug', 'payment_id')
    readonly_fields = ('order', 'beneficiary', 'cosmetico', 'slug', 'name',
                       'payment_id', 'event_id', 'granted_at')

    def has_add_permission(self, request):
        return False


@admin.register(EventCosmeticOffer)
class EventCosmeticOfferAdmin(admin.ModelAdmin):
    list_display = ('event_key', 'cosmetico', 'cost_braseiros', 'starts_at', 'ends_at', 'active')
    list_filter = ('active', 'event_key')
    search_fields = ('event_key', 'cosmetico__slug', 'cosmetico__nome')
    autocomplete_fields = ('cosmetico',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'cosmetico':
            kwargs['queryset'] = TbCosmetico.objects.filter(
                origem__in=['loja_braseiro', 'evento_manual'])
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(EventCosmeticRedemption)
class EventCosmeticRedemptionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'character', 'cosmetico',
                    'cost_braseiros', 'balance_after', 'request_id')
    list_filter = ('offer__event_key',)
    search_fields = ('request_id', 'user__username', 'character__nome', 'cosmetico__slug')
    readonly_fields = ('request_id', 'offer', 'user', 'character', 'cosmetico',
                       'cost_braseiros', 'balance_after', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


def _tag_library_activate(raw, request, *, name, reason):
    from .tag_engine.governance import audit_library
    from .tag_engine.library import Library, clear_library_cache

    reason = str(reason or '').strip()
    if len(reason) < 5:
        raise ValueError('Informe o motivo da alteração para manter a auditoria.')
    report = audit_library(raw, baseline=Library(), scan_usage=True)
    if not report['valid']:
        return None, report
    with transaction.atomic():
        TbTagLibraryRevision.objects.select_for_update().filter(
            ativa=True).update(ativa=False)
        revision = TbTagLibraryRevision.objects.create(
            nome=(str(name or '').strip() or 'Revisão da biblioteca')[:160],
            motivo=reason,
            conteudo_json=raw,
            checksum=report['checksum'],
            ativa=True,
            validacao_json=report,
            criada_por=request.user,
            ativada_por=request.user,
            ativada_em=timezone.now(),
        )
    clear_library_cache()
    return revision, report


def _tag_library_primitive_rows(raw):
    rows = []
    for name, spec in (raw.get('primitives') or {}).items():
        if name.startswith('_') or not isinstance(spec, dict):
            continue
        examples = spec.get('exemplos') or spec.get('examples') or []
        if isinstance(examples, str):
            examples = [examples]
        value = spec.get('value') if isinstance(spec.get('value'), dict) else {}
        rows.append({
            'name': name,
            'category': spec.get('categoria') or '',
            'form': spec.get('forma') or '',
            'op': spec.get('op') or '',
            'target': spec.get('target') or '',
            'value_type': value.get('type') or '',
            'catalog': value.get('catalog') or '',
            'doc': spec.get('doc') or '',
            'examples': examples,
        })
    return sorted(rows, key=lambda row: row['name'])


def _tag_library_context(
        request, raw, *, report=None, selected_revision=None, test_result=None):
    from .tag_engine.governance import library_checksum
    from .tag_engine.library import Library

    active_library = Library()
    operations = []
    for name, spec in (raw.get('ops') or {}).items():
        if name.startswith('_') or not isinstance(spec, dict):
            continue
        operations.append({
            'name': name,
            'doc': spec.get('doc') or '',
            'signature': spec.get('assina') or '',
        })
    forms = [
        {'name': name, 'doc': (spec or {}).get('doc') or ''}
        for name, spec in (raw.get('token_forms') or {}).items()
        if not name.startswith('_') and isinstance(spec, dict)
    ]
    catalogs = sorted(
        name for name in (raw.get('catalogs') or {}) if not name.startswith('_'))
    active_revision = TbTagLibraryRevision.objects.filter(ativa=True).select_related(
        'criada_por', 'ativada_por').first()
    return {
        **admin.site.each_context(request),
        'title': 'Biblioteca de Tags',
        'library_source': active_library.source,
        'active_revision': active_revision,
        'selected_revision': selected_revision,
        'editor_json': json.dumps(raw, ensure_ascii=False, indent=2),
        'editor_checksum': library_checksum(raw),
        'primitive_rows': _tag_library_primitive_rows(raw),
        'primitive_rows_json': _tag_library_primitive_rows(raw),
        'operations': sorted(operations, key=lambda row: row['name']),
        'token_forms': sorted(forms, key=lambda row: row['name']),
        'catalogs': catalogs,
        'report': report,
        'test_result': test_result,
        'revisions': TbTagLibraryRevision.objects.select_related(
            'criada_por', 'ativada_por').all()[:30],
    }


def tag_library_view(request):
    """Consulta, edita, valida e versiona o DSL usado pelo motor."""
    from .tag_engine.governance import audit_library, parse_library_json
    from .tag_engine.library import LIB_PATH, Library

    selected_revision = None
    revision_id = request.GET.get('revision')
    if revision_id:
        selected_revision = get_object_or_404(TbTagLibraryRevision, pk=revision_id)
        raw = copy.deepcopy(selected_revision.conteudo_json)
    else:
        raw = copy.deepcopy(Library().raw)
    report = None
    test_result = None

    if request.method == 'POST':
        action = request.POST.get('action') or 'validate_json'
        try:
            if action == 'test_tags':
                from .tag_engine import evaluate_tags, validate_tags_json
                test_tags = [
                    line.strip() for line in str(
                        request.POST.get('test_tags') or '').splitlines()
                    if line.strip()
                ]
                if not test_tags:
                    raise ValueError('Informe ao menos uma tag para testar.')
                library = Library()
                diagnostics = validate_tags_json(
                    test_tags, library, data=None, strict_names=True)
                evaluated = evaluate_tags(test_tags, library=library)
                test_result = {
                    'tags': test_tags,
                    'tags_text': '\n'.join(test_tags),
                    'diagnostics': [
                        {
                            'level': row.level, 'code': row.code,
                            'message': row.message, 'fragment': row.fragment,
                        }
                        for row in diagnostics
                    ],
                    'operations': [
                        {
                            'verb': row.verb, 'op': row.op,
                            'target': row.target, 'value': row.value,
                            'active': row.active, 'scope': list(row.scope),
                            'qualifiers': list(row.qualifiers),
                        }
                        for row in evaluated.operations
                    ],
                    'state_json': json.dumps(
                        evaluated.state, ensure_ascii=False, indent=2,
                        cls=DjangoJSONEncoder,
                    ),
                }
            elif action in {'validate_json', 'activate_json'}:
                raw = parse_library_json(request.POST.get('library_json') or '')
                report = audit_library(raw, baseline=Library(), scan_usage=True)
                if action == 'activate_json':
                    revision, report = _tag_library_activate(
                        raw, request,
                        name=request.POST.get('revision_name'),
                        reason=request.POST.get('reason'),
                    )
                    if revision:
                        messages.success(
                            request,
                            'Biblioteca validada e ativada. O motor já está lendo a revisão %s.'
                            % revision.pk,
                        )
                        return redirect('%s?revision=%s' % (
                            reverse('admin:tag_library'), revision.pk))
                    messages.error(request, 'A revisão foi recusada; nada foi alterado.')
                elif report['valid']:
                    messages.success(request, 'JSON válido e sem novas regressões nas tags cadastradas.')
                else:
                    messages.error(request, 'A validação encontrou problemas; nada foi ativado.')
            elif action in {'save_primitive', 'delete_primitive'}:
                raw = copy.deepcopy(Library().raw)
                primitives = raw.setdefault('primitives', {})
                original = str(request.POST.get('primitive_original') or '').strip()
                if action == 'delete_primitive':
                    if not original or original not in primitives:
                        raise ValueError('Primitiva não encontrada na revisão ativa.')
                    primitives.pop(original)
                    default_name = 'Remover primitiva %s' % original
                else:
                    name = str(request.POST.get('primitive_name') or '').strip()
                    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
                        raise ValueError('O verbo deve usar somente snake_case, sem hífen.')
                    operation = str(request.POST.get('primitive_op') or '').strip()
                    if operation and operation not in (raw.get('ops') or {}):
                        raise ValueError('Escolha uma operação genérica cadastrada.')
                    if original and original != name:
                        primitives.pop(original, None)
                    spec = copy.deepcopy(primitives.get(name) or {})
                    spec.update({
                        'categoria': str(request.POST.get('primitive_category') or '').strip(),
                        'forma': str(request.POST.get('primitive_form') or '').strip(),
                        'op': operation or None,
                        'doc': str(request.POST.get('primitive_doc') or '').strip(),
                    })
                    target = str(request.POST.get('primitive_target') or '').strip()
                    if target:
                        spec['target'] = target
                    else:
                        spec.pop('target', None)
                    value_type = str(request.POST.get('primitive_value_type') or '').strip()
                    catalog = str(request.POST.get('primitive_catalog') or '').strip()
                    if value_type or catalog:
                        spec['value'] = {
                            **({'type': value_type} if value_type else {}),
                            **({'catalog': catalog} if catalog else {}),
                        }
                    else:
                        spec.pop('value', None)
                    examples = [
                        line.strip() for line in str(
                            request.POST.get('primitive_examples') or '').splitlines()
                        if line.strip()
                    ]
                    if examples:
                        spec['exemplos'] = examples
                    else:
                        spec.pop('exemplos', None)
                    primitives[name] = spec
                    default_name = '%s primitiva %s' % (
                        'Editar' if original else 'Criar', name)
                revision, report = _tag_library_activate(
                    raw, request,
                    name=request.POST.get('revision_name') or default_name,
                    reason=request.POST.get('reason'),
                )
                if revision:
                    messages.success(request, 'Primitiva salva e revisão ativada.')
                    return redirect('%s?revision=%s' % (
                        reverse('admin:tag_library'), revision.pk))
                messages.error(request, 'A alteração quebraria tags existentes e foi recusada.')
            elif action in {'activate_revision', 'activate_file'}:
                if action == 'activate_revision':
                    selected_revision = get_object_or_404(
                        TbTagLibraryRevision, pk=request.POST.get('revision_id'))
                    raw = copy.deepcopy(selected_revision.conteudo_json)
                    default_name = 'Reativar: %s' % selected_revision.nome
                else:
                    raw = copy.deepcopy(Library(path=LIB_PATH, prefer_db=False).raw)
                    default_name = 'Restaurar biblioteca distribuída com o código'
                revision, report = _tag_library_activate(
                    raw, request,
                    name=request.POST.get('revision_name') or default_name,
                    reason=request.POST.get('reason'),
                )
                if revision:
                    messages.success(request, 'Revisão validada e ativada.')
                    return redirect('%s?revision=%s' % (
                        reverse('admin:tag_library'), revision.pk))
                messages.error(request, 'A revisão não passou na validação atual.')
            else:
                raise ValueError('Ação administrativa desconhecida.')
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            messages.error(request, str(exc))

    return render(
        request, 'admin/tag_library.html',
        _tag_library_context(
            request, raw, report=report,
            selected_revision=selected_revision,
            test_result=test_result,
        ),
    )


def tag_library_download_view(request):
    from django.http import HttpResponse
    from .tag_engine.library import Library

    library = Library()
    response = HttpResponse(
        json.dumps(library.raw, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = 'attachment; filename="tag_library_ativa.json"'
    return response


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


def hunter_publication_status_view(request):
    """Read-only status behind admin login and the existing console unlock."""
    from django.http import HttpResponseForbidden, JsonResponse
    from .hunter_publication_diagnostic import publication_status

    unlocked_at = request.session.get('admin_console_authenticated_at')
    if (not request.user.is_superuser or
            not isinstance(unlocked_at, (int, float)) or
            not 0 <= time.time() - unlocked_at <= CONSOLE_UNLOCK_TTL_SECONDS):
        return HttpResponseForbidden()
    return JsonResponse(publication_status())


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
        elif action == "restore_map_geometry":
            f = request.FILES.get("arquivo")
            if not f:
                messages.error(request, "Selecione um arquivo .json de geometria do mapa.")
            elif request.POST.get("confirmar") != "RESTAURAR MAPA":
                messages.error(request, "Digite RESTAURAR MAPA para confirmar.")
            else:
                try:
                    from django.core import serializers
                    from django.db import transaction
                    from .models import TbTerritorio

                    texto = f.read().decode("utf-8")
                    dados = json.loads(texto)
                    if not isinstance(dados, list) or not dados:
                        raise ValueError("O patch deve ser uma lista JSON nao vazia.")
                    if len(dados) > 50:
                        raise ValueError("O patch de mapa excede o limite de 50 territorios.")

                    labels = {
                        str(row.get("model", "")).lower()
                        for row in dados
                        if isinstance(row, dict)
                    }
                    if labels != {"home.tbterritorio"} or len(labels) != 1:
                        raise ValueError(
                            "Este painel aceita exclusivamente registros home.tbterritorio."
                        )

                    objetos = list(serializers.deserialize("json", texto))
                    pks = [wrapper.object.pk for wrapper in objetos]
                    if len(pks) != len(set(pks)):
                        raise ValueError("O patch contem territorios duplicados.")

                    alterados = []
                    with transaction.atomic():
                        for wrapper in objetos:
                            patch = wrapper.object
                            atual = TbTerritorio.objects.select_for_update().filter(pk=patch.pk).first()
                            if atual is None:
                                raise ValueError(
                                    f"Territorio PK {patch.pk} nao existe na producao."
                                )
                            if atual.nome != patch.nome:
                                raise ValueError(
                                    f"PK {patch.pk} pertence a {atual.nome!r}, nao a {patch.nome!r}."
                                )
                            if not isinstance(patch.coordenadas_poligono, list) or not patch.coordenadas_poligono:
                                raise ValueError(
                                    f"Geometria vazia ou invalida para {atual.nome}."
                                )
                            TbTerritorio.objects.filter(pk=atual.pk).update(
                                coordenadas_poligono=patch.coordenadas_poligono
                            )
                            alterados.append(atual.nome)

                    nomes = ", ".join(alterados)
                    messages.success(
                        request,
                        f"Geometria restaurada em {len(alterados)} territorio(s).",
                    )
                    context["op_result"] = {
                        "titulo": "Restauracao de geometria do mapa",
                        "output": (
                            f"Somente CoordenadasPoligono foi atualizado em: {nomes}. "
                            "Usuarios, missoes, catalogo e demais campos permaneceram intactos."
                        ),
                    }
                except Exception as exc:
                    messages.error(request, f"Falha ao restaurar geometria: {exc}")
                    context["op_result"] = {
                        "titulo": "Restauracao de geometria - ERRO",
                        "output": str(exc),
                    }
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
                    if isinstance(dados, dict) and dados.get('kind') == 'bonfire.hunter_restore.v1':
                        from .hunter_restore_package import restore_hunter_package
                        result = restore_hunter_package(dados)
                        messages.success(request, 'Pacote do Cacador instalado com verificacao de identidades.')
                        context['op_result'] = {
                            'titulo': 'Restauracao do Cacador',
                            'output': ('Inseridos: {added}; ja identicos: {unchanged}; revisao: '
                                       '{ruleset_checksum}. Para publicar no criador, configure '
                                       'HUNTER_CREATOR_RULESET_CHECKSUM e reinicie o site.').format(**result),
                        }
                        blocked = True
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
    if text in {"1", "true", "sim", "s", "yes", "y", "verdadeiro"}:
        return True
    if text in {"", "0", "false", "nao", "não", "n", "no", "falso"}:
        return False
    raise ValueError(f"Ritual invalido: {value}")


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
            if any(value is not None and str(value).strip() for value in row):
                errors.append(f"Linha {row_number}: nome obrigatorio.")
            continue

        try:
            nivel = _parse_spell_level(record.get("nivel"))
            ritual = _parse_excel_bool(record.get("ritual"))
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
            "ritual": ritual,
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


@admin.register(TbPersonagemTreinamento)
class TbPersonagemTreinamentoAdmin(admin.ModelAdmin):
    list_display = (
        'id_treinamento', 'id_personagem', 'tipo', 'nome', 'status',
        'custo_pc', 'iniciado_em', 'conclui_em')
    list_filter = ('status', 'tipo')
    search_fields = ('id_personagem__nome', 'id_personagem__dono__username', 'nome')
    raw_id_fields = ('id_personagem',)
    readonly_fields = ('iniciado_em', 'concluido_em')


@admin.register(TbEmprestimoPersonagem)
class TbEmprestimoPersonagemAdmin(admin.ModelAdmin):
    list_display = (
        'id_emprestimo', 'credor', 'devedor', 'valor_original_pc',
        'valor_pago_pc', 'status', 'multa_aplicada', 'vence_em')
    list_filter = ('status', 'multa_aplicada')
    search_fields = (
        'credor__nome', 'devedor__nome', 'credor__dono__username',
        'devedor__dono__username')
    raw_id_fields = ('credor', 'devedor', 'proponente')
    readonly_fields = ('solicitado_em', 'aceito_em', 'encerrado_em')


@admin.register(TbSolicitacaoTranscricao)
class TbSolicitacaoTranscricaoAdmin(admin.ModelAdmin):
    list_display = (
        'id_solicitacao', 'solicitante', 'fonte', 'magia',
        'classe_solicitante', 'status', 'custo_po', 'criado_em')
    list_filter = ('status', 'classe_solicitante')
    search_fields = (
        'solicitante__nome', 'fonte__nome', 'magia__nome',
        'solicitante__dono__username', 'fonte__dono__username')
    raw_id_fields = (
        'solicitante', 'fonte', 'magia', 'classe_solicitante',
        'respondido_por')
    readonly_fields = ('criado_em', 'respondido_em')


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
    list_display = ("id_lancamento", "id_personagem", "origem", "nome_aventura", "data_missao",
                    "mestre_display", "qtd_aventuras", "ouro_pago_po", "nivel_no_lancamento",
                    "criado_por", "criado_em", "revertido")
    list_filter = ("origem", "revertido", "data_missao")
    search_fields = ("nome_aventura", "id_personagem__nome", "criado_por__username",
                     "id_mestre__username")
    raw_id_fields = ("id_personagem", "id_mestre", "criado_por", "revertido_por")
    readonly_fields = ("origem", "criado_em", "revertido_em", "ouro_pago_po", "mestre_display")

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.origem == 'recompensa_comunidade':
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.origem == 'recompensa_comunidade':
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

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
    list_display = ("nome", "tipo", "preco_mm", "preco_vitalicio_aprovado_mm", "ativo", "ordem")
    list_filter = ("tipo", "ativo")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("ordem", "preco_mm")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            return (*fields, 'preco_vitalicio_aprovado_mm')
        return fields

    def save_model(self, request, obj, form, change):
        from django.core.exceptions import PermissionDenied, ValidationError

        if obj.preco_vitalicio_aprovado_mm is not None:
            if not request.user.is_superuser:
                raise PermissionDenied
            if (obj.tipo != 'assinatura' or obj.preco_mm <= 0
                    or obj.preco_vitalicio_aprovado_mm != obj.preco_mm):
                raise ValidationError('O preço aprovado de Mestre Ouro deve coincidir com o preço único positivo.')
        super().save_model(request, obj, form, change)


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


class RaceImageAdminForm(forms.ModelForm):
    def clean_imagem_url(self):
        from .editorial_links import safe_editorial_image

        value = (self.cleaned_data.get('imagem_url') or '').strip()
        if value and not safe_editorial_image(value):
            raise forms.ValidationError('Use uma URL de imagem HTTP(S), /media/ ou /static/.')
        return value


class TbLinhagemInline(admin.StackedInline):
    model = TbLinhagem
    form = RaceImageAdminForm
    extra = 0
    fields = ("nome", "slug", "imagem_url", ("imagem_foco_x", "imagem_foco_y"), "descricao")
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
    form = RaceImageAdminForm
    change_list_template = "admin/home/tbraca/change_list.html"
    list_display = ("nome", "slug", "permite_essencia_badge", "linhagens_count", "tracos_count")
    list_filter = ("permite_essencia",)
    search_fields = ("nome", "slug", "tagline", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "tagline", "imagem_url", ("imagem_foco_x", "imagem_foco_y"), "permite_essencia")}),
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
    form = RaceImageAdminForm
    list_display = ("nome", "raca_nome", "slug", "short_description")
    list_filter = ("id_raca",)
    search_fields = ("nome", "slug", "descricao", "id_raca__nome")
    autocomplete_fields = ("id_raca",)
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("id_raca__nome", "nome")
    fieldsets = (
        (None, {"fields": ("id_raca", "nome", "slug", "imagem_url", ("imagem_foco_x", "imagem_foco_y"), "descricao")}),
        ("Lore", {"classes": ("collapse",), "fields": ("lore_presentation", "lore_roleplay", "lore_society")}),
    )

    @admin.display(description="Raca", ordering="id_raca__nome")
    def raca_nome(self, obj):
        return obj.id_raca.nome


@admin.register(TbEssencia)
class TbEssenciaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    form = RaceImageAdminForm
    change_list_template = "admin/home/tbessencia/change_list.html"
    list_display = ("nome", "slug", "tracos_count")
    search_fields = ("nome", "slug", "lore_presentation", "lore_roleplay", "lore_society")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nome",)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "imagem_url", ("imagem_foco_x", "imagem_foco_y"), "tags_json")}),
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


class RegionCoverFilter(admin.SimpleListFilter):
    title = 'imagem própria'
    parameter_name = 'imagem_propria'

    def lookups(self, request, model_admin):
        return (('pendente', 'Sem imagem própria'), ('pronta', 'Com imagem própria'))

    def queryset(self, request, queryset):
        with_image = queryset.exclude(brasao_url__isnull=True).exclude(brasao_url='')
        if self.value() == 'pronta':
            return with_image
        if self.value() == 'pendente':
            return queryset.exclude(pk__in=with_image.values('pk'))
        return queryset


@admin.register(TbRegiao)
class TbRegiaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "territorio", "cover_preview", "categoria", "camada", "etiquetas_adicionais")
    list_filter = (RegionCoverFilter, "categoria", "territorio", "camada")
    search_fields = ("nome", "slug", "territorio", "etiquetas_adicionais")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("territorio", "nome")

    @admin.display(description='Imagem própria')
    def cover_preview(self, obj):
        if not obj.brasao_url:
            return 'Pendente'
        from .views import _asset_url

        return format_html(
            '<img src="{}" alt="" style="width:72px;height:44px;object-fit:cover;border-radius:4px" '
            'loading="lazy">', _asset_url(obj.brasao_url),
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


class TerritoryCoverFilter(admin.SimpleListFilter):
    title = 'capa própria'
    parameter_name = 'capa_propria'

    def lookups(self, request, model_admin):
        return (('pendente', 'Sem capa própria'), ('pronta', 'Com capa própria'))

    def queryset(self, request, queryset):
        with_cover = queryset.exclude(imagem_url__isnull=True).exclude(imagem_url='')
        if self.value() == 'pronta':
            return with_cover
        if self.value() == 'pendente':
            return queryset.exclude(pk__in=with_cover.values('pk'))
        return queryset


@admin.register(TbTerritorio)
class TbTerritorioAdmin(BonfireAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "slug", "cover_preview", "color_preview", "short_description", "camada")
    list_filter = (TerritoryCoverFilter, "camada")
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

    @admin.display(description='Capa própria')
    def cover_preview(self, obj):
        if not obj.imagem_url:
            return 'Pendente'
        from .views import _asset_url

        return format_html(
            '<img src="{}" alt="" style="width:72px;height:44px;object-fit:cover;border-radius:4px" '
            'loading="lazy">', _asset_url(obj.imagem_url),
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


class OrganizacaoAdminForm(forms.ModelForm):
    class Meta:
        model = TbOrganizacao
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        for field in ('regioes', 'territorios', 'aliados', 'inimigos', 'tags'):
            if field not in cleaned:
                continue
            try:
                cleaned[field] = organization_list(cleaned[field], strict=True)
            except ValueError as exc:
                self.add_error(field, str(exc))
        return cleaned


@admin.register(TbOrganizacao)
class TbOrganizacaoAdmin(BonfireAdminMixin, admin.ModelAdmin):
    form = OrganizacaoAdminForm
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

class TbMagiaAdminForm(forms.ModelForm):
    classes_selecionadas = forms.ModelMultipleChoiceField(
        label='Classes com acesso base', queryset=TbClasse.objects.none(),
        required=False, widget=forms.SelectMultiple(attrs={'size': 13}),
        help_text='Somente classes cadastradas. Expansões por talentos e habilidades continuam nas tags.',
    )

    class Meta:
        model = TbMagia
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = TbClasse.objects.all().order_by('nome')
        self.fields['classes_selecionadas'].queryset = queryset
        if self.instance and self.instance.pk:
            from .spell_access import spell_class_slugs
            self.fields['classes_selecionadas'].initial = queryset.filter(
                slug__in=spell_class_slugs(self.instance, classes=queryset))

    def save(self, commit=True):
        from .spell_access import set_spell_class_access
        instance = super().save(commit=False)
        set_spell_class_access(
            instance, self.cleaned_data.get('classes_selecionadas') or [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(TbMagia)
class TbMagiaAdmin(BonfireAdminMixin, admin.ModelAdmin):
    form = TbMagiaAdminForm
    change_list_template = "admin/home/tbmagia/change_list.html"
    list_display = ("nome", "nivel_display", "escola", "casting_time", "ritual", "concentracao", "alcance", "tags_preview")
    list_filter = ("nivel", "escola", "ritual", "concentracao")
    search_fields = ("nome", "nome_ingles", "slug", "escola", "classes", "descricao", "em_niveis_superiores")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("nivel", "nome")
    fieldsets = (
        (None, {"fields": ("nome", "nome_ingles", "slug", "nivel", "escola", "tags_json")}),
        ("Conjuracao", {"fields": ("casting_time", "ritual", "duracao", "concentracao", "alcance", "componentes")}),
        ("Acesso", {"fields": ("classes_selecionadas",)}),
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
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Importar magias por Excel",
            "form": MagiaExcelImportForm(),
            "preview": None,
            "errors": [],
            "payload": "",
            "atualizar_existentes": True,
            "result": None,
        }

        if request.method != "POST":
            return render(request, "admin/spell_import.html", context)

        if request.POST.get("confirmar") == "1":
            confirm_form = MagiaExcelConfirmForm(request.POST)
            if not confirm_form.is_valid():
                messages.error(request, "Nao foi possivel confirmar a importacao.")
                return render(request, "admin/spell_import.html", context)
            try:
                batch = signing.loads(
                    confirm_form.cleaned_data["payload"],
                    salt="admin-spell-import-v1", max_age=1800,
                )
            except signing.BadSignature:
                context["errors"] = ["Previa invalida ou expirada. Leia o arquivo novamente."]
                return render(request, "admin/spell_import.html", context)
            if batch.get("user_id") != request.user.pk:
                context["errors"] = ["A previa pertence a outro usuario."]
                return render(request, "admin/spell_import.html", context)

            magias = batch["spells"]
            targets = batch["targets"]
            created = 0
            updated = 0
            skipped = 0
            try:
                with transaction.atomic():
                    from .spell_access import access_key
                    class_lookup = {
                        key: classe for classe in TbClasse.objects.select_for_update()
                        for key in (access_key(classe.nome), access_key(classe.slug))
                    }
                    for item, target in zip(magias, targets, strict=True):
                        class_targets = []
                        for token in re.split(r"[,;|]", item["classes"]):
                            token = token.strip()
                            if token:
                                classe = class_lookup.get(access_key(token))
                                if not classe:
                                    raise ValueError(f"classes nao cadastradas: {token}. Leia o arquivo novamente.")
                                fingerprint = [classe.pk, classe.nome, classe.slug]
                                if fingerprint not in class_targets:
                                    class_targets.append(fingerprint)
                        if class_targets != item.get("class_targets"):
                            raise ValueError("As classes mudaram desde a previa. Leia o arquivo novamente.")
                        existing = TbMagia.objects.select_for_update().filter(slug=item["slug"]).first()
                        if (existing.pk if existing else None) != target["pk"] or (
                            existing and self._spell_import_snapshot(existing) != target["snapshot"]
                        ):
                            raise ValueError("O catalogo mudou desde a previa. Leia o arquivo novamente.")
                        if existing and not batch["update_existing"]:
                            skipped += 1
                            continue
                        values = {field: item[field] for field in self._spell_import_fields()}
                        if existing:
                            changed_fields = [field for field, value in values.items()
                                              if field != 'classes' and getattr(existing, field) != value]
                            for field in changed_fields:
                                value = values[field]
                                setattr(existing, field, value)
                            if changed_fields:
                                existing.save(update_fields=changed_fields)
                            magia = existing
                        else:
                            magia = TbMagia.objects.create(slug=item["slug"], **values)
                            created += 1
                        self._sync_imported_classes(magia, item["classes"])
                        if existing:
                            if self._spell_import_snapshot(magia) != target["snapshot"]:
                                updated += 1
                                self.log_change(request, magia, "Importada por Excel")
                            else:
                                skipped += 1
                        else:
                            self.log_addition(request, magia, "Importada por Excel")
            except (ValueError, TypeError, KeyError) as exc:
                context["errors"] = [str(exc)]
                return render(request, "admin/spell_import.html", context)
            except IntegrityError:
                context["errors"] = ["O lote conflitou com o catalogo. Nenhuma linha foi aplicada; leia o arquivo novamente."]
                return render(request, "admin/spell_import.html", context)
            context["result"] = {"created": created, "updated": updated, "skipped": skipped}
            return render(request, "admin/spell_import.html", context)

        form = MagiaExcelImportForm(request.POST, request.FILES)
        context["form"] = form

        if form.is_valid():
            try:
                magias, errors = _parse_magias_xlsx(form.cleaned_data["arquivo"])
            except forms.ValidationError as exc:
                magias, errors = [], exc.messages
            slugs = [item["slug"] for item in magias]
            if len(slugs) != len(set(slugs)):
                errors.append("A planilha contem magias com o mesmo slug. Corrija antes de importar.")
            from .spell_access import access_key
            class_lookup = {
                key: classe for classe in TbClasse.objects.all()
                for key in (access_key(classe.nome), access_key(classe.slug))
            }
            for item in magias:
                unknown = [token.strip() for token in re.split(r"[,;|]", item["classes"])
                           if token.strip() and access_key(token) not in class_lookup]
                if unknown:
                    errors.append(f'{item["nome"]}: classes nao cadastradas: {", ".join(unknown)}.')
            if not magias and not errors:
                errors.append("Nenhuma magia valida encontrada na planilha.")
            targets = []
            if not errors:
                existing_by_slug = TbMagia.objects.filter(slug__in=slugs).in_bulk(field_name="slug")
                targets = [{
                    "pk": existing.pk if existing else None,
                    "snapshot": self._spell_import_snapshot(existing) if existing else None,
                } for existing in (existing_by_slug.get(slug) for slug in slugs)]
                for item, target in zip(magias, targets, strict=True):
                    selected_classes = []
                    for token in re.split(r"[,;|]", item["classes"]):
                        classe = class_lookup.get(access_key(token.strip()))
                        if classe and classe not in selected_classes:
                            selected_classes.append(classe)
                    item["tags_json"] = [tag for tag in (
                        item["nivel_display"], item["escola"],
                        *(classe.nome for classe in selected_classes),
                    ) if tag]
                    item["class_targets"] = [
                        [classe.pk, classe.nome, classe.slug] for classe in selected_classes
                    ]
                    proposed = {field: item[field] for field in self._spell_import_fields()
                                if field != "classes"}
                    proposed["classes"] = ', '.join(classe.nome for classe in selected_classes)
                    proposed["classes_slugs"] = [classe.slug for classe in selected_classes]
                    item["import_action"] = (
                        "Atualizar" if target["pk"] and form.cleaned_data["atualizar_existentes"]
                        and proposed != target["snapshot"]
                        else "Ignorar" if target["pk"] else "Criar"
                    )
            context.update({
                "preview": magias,
                "errors": errors,
                "payload": signing.dumps({
                    "user_id": request.user.pk,
                    "spells": magias,
                    "targets": targets,
                    "update_existing": form.cleaned_data["atualizar_existentes"],
                }, salt="admin-spell-import-v1") if not errors else "",
                "atualizar_existentes": form.cleaned_data["atualizar_existentes"],
            })
            return render(request, "admin/spell_import.html", context)
        return render(request, "admin/spell_import.html", context)

    @staticmethod
    def _spell_import_fields():
        return (
            "nome", "nivel", "casting_time", "ritual", "duracao", "concentracao",
            "escola", "alcance", "componentes", "classes", "descricao",
            "em_niveis_superiores", "tags_json",
        )

    @classmethod
    def _spell_import_snapshot(cls, magia):
        return {field: getattr(magia, field) for field in (*cls._spell_import_fields(), "classes_slugs")}

    @staticmethod
    def _sync_imported_classes(magia, raw_classes):
        from .spell_access import access_key, set_spell_class_access
        lookup = {}
        for classe in TbClasse.objects.select_for_update():
            lookup[access_key(classe.nome)] = classe
            lookup[access_key(classe.slug)] = classe
        classes = []
        for token in re.split(r'[,;|]', raw_classes or ''):
            token = token.strip()
            if not token:
                continue
            classe = lookup.get(access_key(token))
            if not classe:
                raise ValueError(f'classes nao cadastradas: {token}. Leia o arquivo novamente.')
            if classe not in classes:
                classes.append(classe)
        previous = (magia.classes_slugs, magia.classes)
        set_spell_class_access(magia, classes, save=False)
        if (magia.classes_slugs, magia.classes) != previous:
            magia.save(update_fields=['classes_slugs', 'classes'])

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
            "server-logs/hunter-publication-status/",
            admin.site.admin_view(hunter_publication_status_view),
            name="hunter_publication_status",
        ),
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
            "tag-library/",
            admin.site.admin_view(tag_library_view),
            name="tag_library",
        ),
        path(
            "tag-library/download/",
            admin.site.admin_view(tag_library_download_view),
            name="tag_library_download",
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
    from .admin_navigation import grouped_admin_apps

    return grouped_admin_apps(app_dict, reverse('admin:index'))

admin.site.get_app_list = _bonfire_admin_get_app_list


class _ConteudoEstaticoForm(forms.ModelForm):
    class Meta:
        model = TbConteudoEstatico
        fields = '__all__'

    def clean_cta_url(self):
        from .editorial_links import safe_editorial_link

        value = self.cleaned_data.get('cta_url', '')
        if value and not safe_editorial_link(value):
            raise forms.ValidationError('Use um caminho local iniciado por / ou uma URL HTTP(S) válida.')
        return value

    def clean_imagem_url(self):
        from .editorial_links import safe_editorial_image

        value = self.cleaned_data.get('imagem_url', '')
        if value and not safe_editorial_image(value):
            raise forms.ValidationError('Use uma URL HTTP(S) ou um caminho iniciado por /static/ ou /media/.')
        return value


@admin.register(TbConteudoEstatico)
class TbConteudoEstaticoAdmin(admin.ModelAdmin):
    form = _ConteudoEstaticoForm
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
                'template; editar texto, imagem ou CTA não exige deploy. '
                'Para a capa padrão do Mundo, use página "mundo", chave '
                '"mundo-capa-padrao" e a URL da imagem. Capas próprias de '
                'territórios e regiões têm prioridade.'
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
from .models import TbConquista, TbEventoConquista, TbUsuarioConquista


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
    form = ConquistaAdminForm
    list_display = ('nome', 'slug', 'secreta', 'criterio', 'recompensa', 'ativo', 'ordem')
    list_filter = ('secreta', 'criterio', 'ativo')
    search_fields = ('nome', 'slug', 'descricao')
    list_editable = ('ativo', 'ordem')
    prepopulated_fields = {'slug': ('nome',)}
    raw_id_fields = ('recompensa',)
    fieldsets = (
        (None, {'fields': ('nome', 'slug', 'descricao', 'icone_url', 'icone_file')}),
        ('Visibilidade', {'fields': ('secreta', 'ativo', 'ordem')}),
        ('Critério', {'fields': ('criterio', 'metrica_assistida', 'classe_inicial',
                               'classe_nivel', 'alvo_nivel', 'classe_unica', 'rank_alvo',
                               'itens_comprados', 'operador_unidades', 'alvo_unidades',
                               'criterio_json'),
                      'description': 'Início de classe: metric=class_started, '
                                     'scope=account, filters.class_slug=slug real, '
                                     'schema_version=1, operator=gte, target=1. '
                                     'Unidades compradas: metric=items_purchased_units, '
                                     'scope=account, aggregate=sum, schema_version=1, '
                                     'filters.items=[{"catalog":"mundano","id":ID_REAL}], '
                                     'operator=gt ou gte, target=inteiro positivo. '
                                     'Aventuras jogadas: metric=adventures_played, '
                                     'aggregate=sum, filters={"valid":true,"origin":"played_session"}. '
                                     'Nível atual: metric=character_level, classe principal e alvo entre 2 e 20; '
                                     'sem multiclasse exige nível 20 e histórico de classe única. '
                                     'Rank: metric=rank_reached, patentes Ametista a Rubi com level-up comprovado. '
                                     'Defina os limiares e operadores com o PO antes de ativar.'}),
        ('Recompensa', {'fields': ('recompensa',),
                        'description': 'Cosmético desbloqueado no inventário ao conceder.'}),
    )
    actions = ('conceder_a_usuarios', 'reprocessar_nivel')

    @admin.action(description='Reprocessar fatos de nível e rank para marcos selecionados',
                  permissions=['change'])
    def reprocessar_nivel(self, request, queryset):
        """Avalia contas com revisões de nível após cadastrar um novo marco."""
        from django.contrib.auth import get_user_model
        from .conquistas import avaliar_nivel_personagem
        from .models import TbEventoConquista

        if not queryset.filter(
                ativo=True, criterio='automatico',
                criterio_json__metric__in=['character_level', 'rank_reached']).exists():
            self.message_user(request, 'Selecione um marco de nível ou rank ativo.', level=messages.WARNING)
            return
        account_ids = TbEventoConquista.objects.filter(
            origem='site', tipo='character_level_up').values_list(
                'conta_id', flat=True).distinct()
        count = 0
        for user in get_user_model().objects.filter(pk__in=account_ids).iterator():
            avaliar_nivel_personagem(user)
            count += 1
        self.message_user(request, f'{count} conta(s) reavaliada(s) com fatos de nível.')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'criterio_json':
            kwargs['help_text'] = ('Critérios disponíveis: characters_created, stories_published, '
                                   'items_purchased, items_purchased_units, class_started e '
                                   'adventures_played, character_level, rank_reached e quests_completed. '
                                   'Para unidades, use IDs reais do catálogo; '
                                   'escolha gt ou gte e o limiar com o PO.')
        return super().formfield_for_dbfield(db_field, request, **kwargs)

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
                    with transaction.atomic():
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
    list_display = ('user', 'conquista', 'concedida_em', 'concedida_por', 'revogada_em')
    list_filter = ('conquista', 'concedida_em', 'revogada_em')
    search_fields = ('user__username', 'conquista__nome', 'conquista__slug')
    autocomplete_fields = ('user', 'conquista', 'concedida_por')
    readonly_fields = ('concedida_em', 'evidencia_json', 'definicao_json')
    ordering = ('-concedida_em',)
    actions = ('revogar_manuais',)

    @admin.action(description='Revogar concessões manuais selecionadas', permissions=['change'])
    def revogar_manuais(self, request, queryset):
        """Revoga somente regras manuais; a repetição não afeta outras origens."""
        from .conquistas import revogar_conquista_manual

        revoked = 0
        for grant in queryset.select_related('conquista').iterator():
            if revogar_conquista_manual(grant):
                revoked += 1
        self.message_user(request, f'{revoked} concessão(ões) manual(is) revogada(s).')


@admin.register(TbEventoConquista)
class TbEventoConquistaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'conta', 'origem', 'chave_origem', 'ocorrido_em')
    list_filter = ('tipo', 'origem')
    search_fields = ('conta__username', 'chave_origem')
    readonly_fields = ('id', 'origem', 'chave_origem', 'tipo', 'versao_payload',
                       'payload_json', 'conta', 'personagem', 'agregado_id',
                       'ocorrido_em', 'ingerido_em')
    ordering = ('-ocorrido_em',)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


# Metadados das chaves e auditoria. Criacao, rotacao e revogacao passam pelos
# endpoints superuser-only em /admin/api-keys/; hashes nunca sao exibidos.
from .db_access_models import DbAccessAudit, ManagedApiKey


@admin.register(ManagedApiKey)
class ManagedApiKeyAdmin(admin.ModelAdmin):
    change_list_template = 'admin/db_access_key_changelist.html'
    list_display = ('name', 'prefix', 'scopes', 'expires_at', 'revoked_at',
                    'created_at', 'last_used_at')
    list_filter = ('created_at', 'expires_at', 'revoked_at')
    search_fields = ('name', 'prefix')
    readonly_fields = ('id', 'name', 'prefix', 'scopes', 'expires_at', 'revoked_at',
                       'created_by', 'created_at', 'last_used_at', 'rotated_from',
                       'rate_window_started', 'rate_count')
    exclude = ('secret_hash',)
    actions = None

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DbAccessAudit)
class DbAccessAuditAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'api_key', 'action', 'model_label',
                    'object_pk', 'status_code', 'field_names')
    list_filter = ('action', 'model_label', 'status_code', 'occurred_at')
    readonly_fields = ('api_key', 'action', 'model_label', 'object_pk',
                       'status_code', 'field_names', 'occurred_at')
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import (MestreOuroDireito, MestreOuroRevisao,
                     SocialCreditEntry, SocialCreditHistoricalCampaign,
                     SocialCreditPolicy,
                     SocialCreditReaderRecognition, SocialCreditRedemption,
                     SocialCreditWallet)


class _ReadOnlySocialCreditAdmin(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MestreOuroDireito)
class MestreOuroDireitoAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('user', 'primeira_compra', 'adquirido_em', 'concedido_em')
    search_fields = ('user__username',)
    readonly_fields = list_display

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


@admin.register(MestreOuroRevisao)
class MestreOuroRevisaoAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('user', 'motivo', 'registrada_em')
    search_fields = ('user__username',)
    readonly_fields = list_display

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


@admin.register(SocialCreditWallet)
class SocialCreditWalletAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'balance', 'updated_at')


@admin.register(SocialCreditEntry)
class SocialCreditEntryAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('created_at', 'wallet', 'kind', 'delta', 'balance_after', 'operation_ref')
    search_fields = ('wallet__user__username', 'operation_ref')
    list_filter = ('kind', 'created_at')
    readonly_fields = ('wallet', 'operation_ref', 'kind', 'delta', 'balance_after',
                       'reversal_of', 'policy', 'created_at')


class SocialCreditPolicyForm(forms.ModelForm):
    class Meta:
        model = SocialCreditPolicy
        exclude = ('active',)
        labels = {
            'version': 'Versão',
            'first_publication_amount': 'Créditos pela primeira publicação',
            'reader_recognition_enabled': 'Habilitar reconhecimento por leitores',
            'reader_milestone_size': 'Leitores únicos por marco',
            'reader_milestone_amount': 'Créditos por marco',
            'reader_consolidation_hours': 'Horas de consolidação',
            'reader_story_credit_cap': 'Teto por Crônica',
            'reader_author_period_credit_cap': 'Teto por autor no período',
            'reader_period_days': 'Dias do período de leitores',
            'redemption_enabled': 'Habilitar resgate',
            'redemption_cost': 'Custo do resgate em créditos',
            'redemption_gold_pc': 'Recompensa em PC',
            'redemption_gold_source': 'Tabela de ouro aprovada',
            'redemption_counts_for_progression': 'Conta para progressão',
            'redemption_period_days': 'Dias do período de resgate',
            'redemption_period_limit': 'Limite de resgates no período',
            'redemption_character_limit': 'Limite de resgates por personagem',
        }


@admin.register(SocialCreditPolicy)
class SocialCreditPolicyAdmin(admin.ModelAdmin):
    list_display = ('version', 'first_publication_amount', 'reader_recognition_enabled',
                    'redemption_enabled', 'active', 'created_at')
    list_filter = ('active', 'reader_recognition_enabled', 'redemption_enabled')
    search_fields = ('version',)
    readonly_fields = ('active_display', 'created_at_display')
    exclude = ('active',)
    actions = ('activate_version', 'deactivate_version')
    form = SocialCreditPolicyForm
    fieldsets = (
        ('Versão e autoria', {
            'fields': ('version', 'first_publication_amount',
                       'active_display', 'created_at_display'),
            'description': ('Crie um rascunho com versão única. A parcela por primeira '
                            'publicação deve ser aprovada pelo PO antes da ativação.'),
        }),
        ('Reconhecimento por leitores', {
            'fields': ('reader_recognition_enabled', 'reader_milestone_size',
                       'reader_milestone_amount', 'reader_consolidation_hours',
                       'reader_story_credit_cap', 'reader_author_period_credit_cap',
                       'reader_period_days'),
            'description': ('Defina marco, janela e tetos por história e autor. '
                            'Campos completos são obrigatórios ao ativar esta modalidade.'),
        }),
        ('Resgate de aventura e recompensa', {
            'fields': ('redemption_enabled', 'redemption_cost', 'redemption_gold_pc',
                       'redemption_gold_source', 'redemption_counts_for_progression',
                       'redemption_period_days', 'redemption_period_limit',
                       'redemption_character_limit'),
            'description': ('Informe custo, tabela de ouro, efeito na progressão e limites '
                            'aprovados pelo PO antes de habilitar o resgate.'),
        }),
    )

    @admin.display(description='Ativa')
    def active_display(self, obj):
        return 'Sim' if obj and obj.active else 'Não'

    @admin.display(description='Criada em')
    def created_at_display(self, obj):
        return obj.created_at if obj and obj.created_at else '—'

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if not request.user.is_active or not request.user.is_superuser:
            return False
        if obj is None:
            return True
        return not obj.active and not self._has_usage(obj)

    def has_delete_permission(self, request, obj=None):
        return False

    @staticmethod
    def _has_usage(policy):
        return (SocialCreditEntry.objects.filter(policy=policy).exists()
                or SocialCreditReaderRecognition.objects.filter(policy=policy).exists()
                or SocialCreditRedemption.objects.filter(policy=policy).exists()
                or SocialCreditHistoricalCampaign.objects.filter(policy=policy).exists())

    def save_model(self, request, obj, form, change):
        from django.core.exceptions import PermissionDenied

        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied
        if change:
            current = SocialCreditPolicy.objects.select_for_update().get(pk=obj.pk)
            if current.active or self._has_usage(current):
                raise PermissionDenied
        obj.active = False
        super().save_model(request, obj, form, change)

    def _change_activation(self, request, queryset, *, activate):
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        from django.core.exceptions import ValidationError
        from .social_credits import _validate_reader_policy, _validate_redemption_policy

        if not request.user.is_active or not request.user.is_superuser:
            self.message_user(request, 'Ação reservada a superusuários.', level=messages.ERROR)
            return None
        if queryset.count() != 1:
            self.message_user(request, 'Selecione exatamente uma versão.', level=messages.ERROR)
            return None
        policy = queryset.first()
        confirmed = request.POST.get('confirm_version')
        if confirmed == policy.version:
            with transaction.atomic():
                # Serialize policy switches, including two different versions racing.
                locked = list(SocialCreditPolicy.objects.select_for_update().order_by('pk'))
                policy = next(item for item in locked if item.pk == policy.pk)
                if policy.active == activate:
                    self.message_user(request, 'A versão já está nesse estado.', level=messages.WARNING)
                    return None
                if activate:
                    if SocialCreditPolicy.objects.filter(active=True).exclude(pk=policy.pk).exists():
                        self.message_user(request, 'Desative a versão atual antes de ativar outra.',
                                          level=messages.ERROR)
                        return None
                    policy.active = True
                    try:
                        policy.full_clean()
                        if policy.reader_recognition_enabled:
                            _validate_reader_policy(policy)
                        if policy.redemption_enabled:
                            _validate_redemption_policy(policy)
                    except (ValidationError, ValueError) as exc:
                        self.message_user(request, f'Política incompleta: {exc}',
                                          level=messages.ERROR)
                        return None
                policy.active = activate
                policy.save(update_fields=['active'])
            verb = 'ativada' if activate else 'desativada'
            self.message_user(request, f'Versão {policy.version} {verb}.', level=messages.SUCCESS)
            return None

        return render(request, 'admin/home/socialcreditpolicy/confirm_activation.html', {
            **self.admin_site.each_context(request),
            'title': 'Ativar política social' if activate else 'Desativar política social',
            'policy': policy,
            'activate': activate,
            'error': bool(confirmed),
            'action_name': 'activate_version' if activate else 'deactivate_version',
            'action_checkbox_name': ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
        })

    @admin.action(description='Ativar versão selecionada com confirmação')
    def activate_version(self, request, queryset):
        return self._change_activation(request, queryset, activate=True)

    @admin.action(description='Desativar versão selecionada com confirmação')
    def deactivate_version(self, request, queryset):
        return self._change_activation(request, queryset, activate=False)


@admin.register(SocialCreditReaderRecognition)
class SocialCreditReaderRecognitionAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('first_seen_at', 'cronica', 'reader', 'policy')
    readonly_fields = ('cronica', 'reader', 'first_seen_at', 'policy')


@admin.register(SocialCreditRedemption)
class SocialCreditRedemptionAdmin(_ReadOnlySocialCreditAdmin):
    list_display = ('created_at', 'user', 'character', 'cost', 'gold_pc', 'policy',
                    'reversal_review_requested_at', 'reversed_at')
    search_fields = ('user__username', 'character__nome', 'request_id')
    readonly_fields = ('request_id', 'user', 'character', 'policy', 'credit_entry',
                       'adventure_entry', 'cost', 'gold_pc', 'gold_source',
                       'counts_for_progression', 'created_at',
                       'reversal_reason', 'reversal_review_reason', 'reversal_review_requested_at',
                       'reversal_review_requested_by', 'reversed_at', 'reversed_by',
                       'credit_reversal_entry', 'gold_reversal_entry')
