import json
import re
import unicodedata
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.paginator import Paginator
from django.db.models import Count, Q, F
from django.db.models.functions import Lower
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import escape, format_html, format_html_join
from django.utils import timezone
from django.db import connection, transaction
from django.utils.text import slugify
from django.views.decorators.http import require_POST


from .models import (
    TbClasse,
    TbClassehabilidade,
    TbCronica,
    TbEssencia,
    TbJornal,
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
from .security import validate_no_sql_danger


def _log_wiki_edit(request, obj, message="Edited inline via wiki"):
    try:
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            action_flag=CHANGE,
            change_message=message
        )
    except Exception:
        pass


def _log_wiki_creation(request, obj, message="Created inline via wiki"):
    try:
        from django.contrib.admin.models import LogEntry, ADD
        from django.contrib.contenttypes.models import ContentType
        
        LogEntry.objects.log_action(
            user_id=request.user.id,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            action_flag=ADD,
            change_message=message
        )
    except Exception:
        pass


class BotMongoUnavailable(Exception):
    """Raised when a requested PostgreSQL table is not available."""
    pass


SITE_COLLECTIONS = {
    'classes': settings.SITE_POSTGRES_TABLES.get('classes', 'home_tbclasse'),
    'subclasses': settings.SITE_POSTGRES_TABLES.get('subclasses', 'home_tbsubclasse'),
    'class_features': settings.SITE_POSTGRES_TABLES.get('class_features', 'home_tbclassehabilidade'),
    'class_resources': settings.SITE_POSTGRES_TABLES.get('class_resources', 'home_tbrecursoclasse'),
    'races': settings.SITE_POSTGRES_TABLES.get('races', 'home_tbraca'),
    'lineages': settings.SITE_POSTGRES_TABLES.get('lineages', 'home_tblinhagem'),
    'essences': settings.SITE_POSTGRES_TABLES.get('essences', 'home_tbessencia'),
    'racial_traits': settings.SITE_POSTGRES_TABLES.get('racial_traits', 'home_tbtracoracial'),
    'map_markers': settings.SITE_POSTGRES_TABLES.get('map_markers', 'home_tbmapmarker'),
    'regions': settings.SITE_POSTGRES_TABLES.get('regions', 'home_tbregiao'),
    'territories': settings.SITE_POSTGRES_TABLES.get('territories', 'home_tbterritorio'),
    'talents': settings.SITE_POSTGRES_TABLES.get('talents', 'home_tbtalento'),
    'options': settings.SITE_POSTGRES_TABLES.get('options', 'home_tbopcaojogo'),
    'backgrounds': settings.SITE_POSTGRES_TABLES.get('backgrounds', 'backgrounds'),
    'spells': settings.SITE_POSTGRES_TABLES.get('spells', 'spells'),
    'bestiary': settings.SITE_POSTGRES_TABLES.get('bestiary', 'bestiary'),
    'organizations': settings.SITE_POSTGRES_TABLES.get('organizations', 'organizations'),
}


class StaffSignupForm(UserCreationForm):
    email = forms.EmailField(label="Email", required=False)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email", "password1", "password2")


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Usuário ou e-mail")

    def clean(self):
        username_or_email = self.cleaned_data.get("username", "").strip()
        if "@" in username_or_email:
            User = get_user_model()
            user = User.objects.filter(email__iexact=username_or_email).order_by("id").first()
            if user:
                self.cleaned_data["username"] = user.get_username()
        return super().clean()


class ViewRecord(SimpleNamespace):
    def __str__(self):
        return str(getattr(self, 'nome', '') or getattr(self, 'slug', '') or getattr(self, 'id', ''))


class RelatedList(list):
    def all(self):
        return self


def _postgres_table_for_key(key):
    table_name = SITE_COLLECTIONS.get(key)
    if not table_name:
        raise BotMongoUnavailable(f"Tabela PostgreSQL nao configurada para: {key}")
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    if table_name not in table_names:
        raise BotMongoUnavailable(f"Tabela PostgreSQL nao encontrada: {table_name}")
    return table_name


def _postgres_columns(table_name):
    with connection.cursor() as cursor:
        return [column.name for column in connection.introspection.get_table_description(cursor, table_name)]


def _quote_name(name):
    return connection.ops.quote_name(name)


from decimal import Decimal
from datetime import date


def _serialize_mongo_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, dict)):
        return value
    return value


def serialize_document(document):
    return {key: _serialize_mongo_value(value) for key, value in (document or {}).items()}


def _row_to_document(columns, row):
    return serialize_document(dict(zip(columns, row)))


class _PostgresCollection:
    def __init__(self, key):
        self.table_name = _postgres_table_for_key(key)
        self.columns = _postgres_columns(self.table_name)

    def update_one(self, filter_query, update, upsert=False):
        document = dict(update.get('$set') or {})
        if upsert:
            document = {**(update.get('$setOnInsert') or {}), **document}
        where_items = {key: value for key, value in (filter_query or {}).items() if key in self.columns}
        data = {key: value for key, value in document.items() if key in self.columns}
        if not where_items:
            raise BotMongoUnavailable("Filtro sem colunas validas para PostgreSQL.")
        if not data:
            return

        where_sql = " AND ".join(f"{_quote_name(key)} = %s" for key in where_items)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {_quote_name(self.table_name)} WHERE {where_sql}",
                list(where_items.values()),
            )
            exists = cursor.fetchone()[0] > 0
            if exists:
                set_sql = ", ".join(f"{_quote_name(key)} = %s" for key in data)
                cursor.execute(
                    f"UPDATE {_quote_name(self.table_name)} SET {set_sql} WHERE {where_sql}",
                    [*data.values(), *where_items.values()],
                )
            elif upsert:
                insert_data = {**where_items, **data}
                columns_sql = ", ".join(_quote_name(key) for key in insert_data)
                placeholders = ", ".join(["%s"] * len(insert_data))
                cursor.execute(
                    f"INSERT INTO {_quote_name(self.table_name)} ({columns_sql}) VALUES ({placeholders})",
                    list(insert_data.values()),
                )


def _mongo_collection(key):
    return _PostgresCollection(key)


def _mongo_docs(key, sort=None, query=None):
    table_name = _postgres_table_for_key(key)
    columns = _postgres_columns(table_name)
    query = query or {}
    valid_query = {field: value for field, value in query.items() if field in columns}
    where_sql = ""
    params = []
    if valid_query:
        where_sql = " WHERE " + " AND ".join(f"{_quote_name(field)} = %s" for field in valid_query)
        params = list(valid_query.values())
    order_parts = []
    for field, direction in (sort or []):
        if field in columns:
            order_parts.append(f"{_quote_name(field)} {'DESC' if direction == -1 else 'ASC'}")
    order_sql = f" ORDER BY {', '.join(order_parts)}" if order_parts else ""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {_quote_name(table_name)}{where_sql}{order_sql}", params)
        rows = cursor.fetchall()
    return [_row_to_document(columns, row) for row in rows]


def _mongo_one(key, query):
    documents = _mongo_docs(key, query=query)
    return documents[0] if documents else None


def _mongo_upsert_site_document(key, id_field, id_value, payload):
    if id_value in (None, '', 'undefined', 'null'):
        return
    try:
        collection = _mongo_collection(key)
        document = dict(payload)
        document[id_field] = id_value
        collection.update_one({id_field: id_value}, {'$set': document}, upsert=True)
    except BotMongoUnavailable:
        pass


def _asset_url(value, fallback='assets/fire_background.png'):
    value = (value or '').strip()
    if not value:
        return static(fallback)
    
    if value.startswith(('http://', 'https://', '/')):
        return value
        
    if value.lower().startswith(('i.imgur.com/', 'imgur.com/')):
        return f"https://{value}"
        
    return static(value)


def _normalize_text(value):
    return re.sub(r'[\u0300-\u036f]', '', unicodedata.normalize('NFD', str(value or ''))).lower().strip()


def _split_catalog_list(value):
    if value in (None, ''):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r'[,;/\n]+', str(value)) if part.strip()]


def _tags_json_value(data):
    value = data.get('tags_json') if isinstance(data, dict) else None
    if value in (None, '') and isinstance(data, dict):
        value = data.get('TagsJSON')
    if value in (None, ''):
        return []
    if isinstance(value, (list, dict)):
        return value
    return _split_catalog_list(value)


def _slug_match_values(value):
    values = _split_catalog_list(value)
    matches = set()
    for item in values:
        matches.add(_normalize_text(item))
        matches.add(slugify(item))
    return {item for item in matches if item}


def _doc_value(document, keys, default=''):
    for key in keys:
        if key in document and document.get(key) not in (None, ''):
            return document.get(key)
    return default


def _display_territory(value):
    normalized = _normalize_text(value)
    if 'auralino' in normalized:
        return 'Reino Auraliano'
    if 'territorio independente' in normalized:
        return 'Territórios Independentes'
    return value or 'Sem território'


def _territory_color(value):
    normalized = _normalize_text(value)
    rules = (
        (('eryndor',), '#7ddc6f'),
        (('auraliano', 'auralino', 'aural'), '#f2c94c'),
        (('floresta eterna',), '#176c3a'),
        (('volgran',), '#b8c0c7'),
        (('karag', 'dum'), '#555b61'),
        (('vyrmrealm',), '#dc2626'),
        (('territorios independentes', 'territorio independente'), '#2563eb'),
        (('norte gelido', 'arvoria'), '#8ecae6'),
    )
    for terms, color in rules:
        if any(term in normalized for term in terms):
            return color
    return '#f27007'


def _get_contrast_color(hex_color):
    
    if not hex_color or not isinstance(hex_color, str):
        return '#070707'
    
    hex_color = hex_color.lstrip('#').lower()
    if hex_color in ('000', '000000', 'black'):
        return '#ffffff'
        
    return '#070707'


def _get_display_color(hex_color):
    
    if not hex_color or not isinstance(hex_color, str):
        return '#f27007'
    
    clean_hex = hex_color.lstrip('#').lower()
    if clean_hex in ('000', '000000', 'black'):
        return '#ffffff'
    return hex_color


def _rec(**kwargs):
    return ViewRecord(**kwargs)


def _bool(value):
    return bool(value)


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'


def _mongo_classe(doc):
    if not doc:
        return None
    return _rec(
        id_classe=doc.get('Id_Classe'),
        nome=doc.get('Nome') or '',
        slug=doc.get('Slug') or '',
        tagline=doc.get('Tagline') or '',
        atributo_principal=doc.get('AtributoPrincipal'),
        dado_vida=doc.get('DadoVida'),
        pv_nivel_1=doc.get('PVNivel1'),
        pv_por_nivel=doc.get('PVPORNivel'),
        resistencias=doc.get('Resistencias'),
        pericias=doc.get('Pericias'),
        armas=doc.get('Armas'),
        ferramentas=doc.get('Ferramentas'),
        armaduras=doc.get('Armaduras'),
        equipamento=doc.get('Equipamento'),
        multiclass_requisitos=doc.get('MulticlassRequisitos'),
        multiclass_pericias=doc.get('MulticlassPericias'),
        multiclass_armas=doc.get('MulticlassArmas'),
        multiclass_ferramentas=doc.get('MulticlassFerramentas'),
        multiclass_armaduras=doc.get('MulticlassArmaduras'),
    )


def _mongo_subclasse(doc, classes_by_id=None):
    if not doc:
        return None
    classe = classes_by_id.get(doc.get('Id_Classe')) if classes_by_id else None
    return _rec(
        id_subclasse=doc.get('Id_Subclasse'),
        id_classe=classe,
        id_classe_id=doc.get('Id_Classe'),
        nome=doc.get('Nome') or '',
        slug=doc.get('Slug') or '',
        tagline=doc.get('Tagline'),
    )


def _mongo_habilidade(doc, classes_by_id=None, subclasses_by_id=None):
    subclasse = subclasses_by_id.get(doc.get('Id_Subclasse')) if subclasses_by_id and doc.get('Id_Subclasse') else None
    classe = classes_by_id.get(doc.get('Id_Classe')) if classes_by_id else None
    return _rec(
        id_habilidade=doc.get('Id_Habilidade'),
        id_classe=classe,
        id_classe_id=doc.get('Id_Classe'),
        id_subclasse=subclasse,
        id_subclasse_id=doc.get('Id_Subclasse'),
        nome=doc.get('Nome') or '',
        descricao=doc.get('Descricao') or '',
        niveladquirido=doc.get('NivelAdquirido') or 0,
        table_only=_bool(doc.get('TableOnly')),
        tags_json=doc.get('TagsJSON') or [],
    )


def _mongo_recurso(doc, classes_by_id=None, subclasses_by_id=None):
    subclasse = subclasses_by_id.get(doc.get('Id_Subclasse')) if subclasses_by_id and doc.get('Id_Subclasse') else None
    classe = classes_by_id.get(doc.get('Id_Classe')) if classes_by_id else None
    return _rec(
        id_recurso=doc.get('Id_Recurso'),
        id_classe=classe,
        id_classe_id=doc.get('Id_Classe'),
        id_subclasse=subclasse,
        id_subclasse_id=doc.get('Id_Subclasse'),
        nome=doc.get('Nome') or '',
        slug=doc.get('Slug') or '',
        nivel=doc.get('Nivel') or 0,
        valor=doc.get('Valor'),
    )


def _mongo_raca(doc):
    return _rec(
        id_raca=doc.get('Id_Raca'),
        nome=doc.get('Nome') or '',
        slug=doc.get('Slug') or '',
        tagline=doc.get('Tagline'),
        lore_presentation=doc.get('LorePresentation'),
        lore_roleplay=doc.get('LoreRoleplay'),
        lore_society=doc.get('LoreSociety'),
        permite_essencia=_bool(doc.get('PermiteEssencia')),
    )


def _mongo_linhagem(doc, tracos=None):
    return _rec(
        id_linhagem=doc.get('Id_Linhagem'),
        id_raca_id=doc.get('Id_Raca'),
        nome=doc.get('Nome') or '',
        slug=doc.get('Slug') or '',
        lore_presentation=doc.get('LorePresentation'),
        lore_roleplay=doc.get('LoreRoleplay'),
        lore_society=doc.get('LoreSociety'),
        descricao=doc.get('Descricao'),
        tracos_linhagem=RelatedList(tracos or []),
    )


def _mongo_traco(doc):
    return _rec(
        id_traco=doc.get('Id_Traco'),
        id_raca_id=doc.get('Id_Raca'),
        id_linhagem_id=doc.get('Id_Linhagem'),
        id_essencia_id=doc.get('Id_Essencia'),
        nome=doc.get('Nome') or '',
        descricao=doc.get('Descricao') or '',
        nivel_requisito=doc.get('NivelRequisito') or 0,
        talento_racial=_bool(doc.get('TalentoRacial')),
        pre_requisito=doc.get('PreRequisito'),
        tags_json=doc.get('TagsJSON') or [],
    )


def home_view(request):
    try:
        from .models import TbJornal
        ultimas_noticias = TbJornal.objects.all().order_by('-data_publicacao')[:3]
    except Exception:
        ultimas_noticias = []
        
    return render(request, 'home/pages/home.html', {
        'ultimas_noticias': ultimas_noticias
    })


def register_view(request):
    if request.method == "POST":
        form = StaffSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get("email") or ""
            user.save()
            login(request, user)
            if user.email:
                _enviar_verificacao_email(request, user)
            return redirect("home")
    else:
        form = StaffSignupForm()

    return render(request, "home/register.html", {
        "form": form,
    })


def _enviar_verificacao_email(request, user):
    """Manda o link de confirmação de e-mail (token assinado, expira em 24h). Falha em
    silêncio se o envio não estiver configurado (cai no backend de console em dev)."""
    from django.conf import settings
    from django.core import signing
    from django.core.mail import send_mail
    if not user.email:
        return
    token = signing.dumps({'uid': user.pk, 'email': user.email.lower()}, salt='email-verify')
    link = request.build_absolute_uri(reverse('verify_email', args=[token]))
    corpo = ('Olá, %s!\n\nConfirme seu e-mail no Bonfire Tales clicando no link abaixo '
             '(expira em 24 horas):\n\n%s\n\nSe não foi você, pode ignorar esta mensagem.'
             % (user.username, link))
    try:
        send_mail('Confirme seu e-mail — Bonfire Tales', corpo,
                  settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception:
        pass


def verify_email(request, token):
    """Confirma o e-mail a partir do token assinado. Só e-mail verificado 'trava' o uso
    por outra conta — então um e-mail só pendente nunca bloqueia o dono real."""
    from django.core import signing
    from .models import UserProfile
    try:
        data = signing.loads(token, salt='email-verify', max_age=60 * 60 * 24)
    except signing.SignatureExpired:
        return render(request, 'home/pages/verificar_email.html', {'status': 'expirado'})
    except signing.BadSignature:
        return render(request, 'home/pages/verificar_email.html', {'status': 'invalido'})
    User = get_user_model()
    user = User.objects.filter(pk=data.get('uid')).first()
    email = (data.get('email') or '').lower()
    if not user or (user.email or '').lower() != email:
        status = 'invalido'  # e-mail mudou depois que o link foi gerado
    elif UserProfile.objects.filter(user__email__iexact=email, email_verified=True).exclude(user=user).exists():
        status = 'conflito'
    else:
        prof, _ = UserProfile.objects.get_or_create(user=user)
        prof.email_verified = True
        prof.save(update_fields=['email_verified'])
        status = 'ok'
    return render(request, 'home/pages/verificar_email.html', {'status': status})


@login_required(login_url='/login/')
def profile_view(request):
    from .models import UserProfile
    from django.contrib.auth import update_session_auth_hash

    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    messages = []
    errors = []

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_profile':
            new_username = request.POST.get('username', '').strip()
            new_email = request.POST.get('email', '').strip()
            new_avatar = request.POST.get('avatar_url', '').strip()
            vlibras_enabled = request.POST.get('vlibras_enabled') == 'on'
            User = get_user_model()
            user_changed = False

            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                    errors.append('Esse nome de usuário já está em uso.')
                elif len(new_username) < 3:
                    errors.append('O nome de usuário deve ter pelo menos 3 caracteres.')
                elif len(new_username) > 30:
                    errors.append('O nome de usuário deve ter no máximo 30 caracteres.')
                else:
                    user.username = new_username
                    user_changed = True

            # E-mail editável (importante p/ casar a cobrança do Asaas). Unicidade só
            # entre e-mails VERIFICADOS: um e-mail só pendente não bloqueia ninguém,
            # evitando que alguém "reserve" o e-mail de outra pessoa.
            email_mudou = False
            if new_email != (user.email or ''):
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                try:
                    if new_email:
                        validate_email(new_email)
                    if new_email and UserProfile.objects.filter(
                            user__email__iexact=new_email, email_verified=True).exclude(user=user).exists():
                        errors.append('Esse e-mail já está confirmado em outra conta.')
                    else:
                        user.email = new_email
                        user_changed = True
                        email_mudou = True
                except ValidationError:
                    errors.append('E-mail inválido.')

            if user_changed:
                user.save()

            profile.avatar_url = new_avatar or None
            profile.vlibras_enabled = vlibras_enabled
            if email_mudou:
                profile.email_verified = False
            profile.save()
            if not errors:
                messages.append('Perfil salvo com sucesso!')
            if email_mudou and user.email and not errors:
                _enviar_verificacao_email(request, user)
                messages.append('Enviamos um link de confirmação para %s. Confirme para validar o e-mail.' % user.email)

        elif action == 'resend_verification':
            if not user.email:
                errors.append('Defina um e-mail primeiro (em Dados do Perfil).')
            elif profile.email_verified:
                messages.append('Seu e-mail já está confirmado.')
            else:
                _enviar_verificacao_email(request, user)
                messages.append('Link de confirmação reenviado para %s.' % user.email)

        elif action == 'set_password_initial':
            # Conta criada via login com Discord (sem senha): define a senha de acesso
            # SEM exigir a senha atual, para passar a entrar também com e-mail/usuário.
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            if user.has_usable_password():
                errors.append('Você já tem uma senha definida; use "Alterar Senha".')
            elif len(new_password) < 6:
                errors.append('A nova senha deve ter pelo menos 6 caracteres.')
            elif new_password != confirm_password:
                errors.append('As senhas não coincidem.')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                messages.append('Senha definida! Agora você também pode entrar com e-mail/usuário e senha.')

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                errors.append('A senha atual está incorreta.')
            elif len(new_password) < 6:
                errors.append('A nova senha deve ter pelo menos 6 caracteres.')
            elif new_password != confirm_password:
                errors.append('As senhas não coincidem.')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                messages.append('Senha alterada com sucesso!')

    from django.conf import settings as _settings
    return render(request, 'home/pages/perfil.html', {
        'profile': profile,
        'success_messages': messages,
        'error_messages': errors,
        'discord_msg': request.GET.get('discord'),
        'discord_oauth_on': bool(_settings.DISCORD_OAUTH_CLIENT_ID),
        'has_password': user.has_usable_password(),
    })


# ───────────────────────── Discord OAuth2 (custom enxuto) ─────────────────────
_DISCORD_API = 'https://discord.com/api'


def _discord_redirect_uri(request):
    from django.conf import settings
    return (settings.DISCORD_OAUTH_REDIRECT_URI or '').strip() or request.build_absolute_uri(reverse('discord_callback'))


def _discord_post_token(code, redirect_uri):
    import urllib.request, urllib.parse
    from django.conf import settings
    data = urllib.parse.urlencode({
        'client_id': settings.DISCORD_OAUTH_CLIENT_ID,
        'client_secret': settings.DISCORD_OAUTH_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }).encode()
    req = urllib.request.Request(_DISCORD_API + '/oauth2/token', data=data,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded',
                                          'Accept': 'application/json',
                                          # Cloudflare (na frente da API do Discord) bloqueia o UA
                                          # padrão do python-urllib com "error code: 1010". O Discord
                                          # também exige um User-Agent identificável.
                                          'User-Agent': 'BonfireTales/1.0 (+https://bonfiretales.com.br)'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _discord_get_me(access_token):
    import urllib.request
    req = urllib.request.Request(_DISCORD_API + '/users/@me',
                                 headers={'Authorization': 'Bearer ' + access_token,
                                          'Accept': 'application/json',
                                          'User-Agent': 'BonfireTales/1.0 (+https://bonfiretales.com.br)'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _discord_unique_username(User, base):
    base = re.sub(r'[^A-Za-z0-9_.-]', '', base or '') or 'discord'
    base = base[:24]
    nome, i = base, 1
    while User.objects.filter(username=nome).exists():
        i += 1
        nome = '%s%d' % (base, i)
    return nome


def discord_login(request):
    """Inicia o OAuth2 do Discord (login com Discord OU vincular conta logada)."""
    import secrets
    import urllib.parse
    from django.conf import settings
    if not settings.DISCORD_OAUTH_CLIENT_ID or not settings.DISCORD_OAUTH_CLIENT_SECRET:
        return redirect('/login/?discord=off')
    state = secrets.token_urlsafe(24)
    request.session['discord_oauth_state'] = state
    request.session['discord_oauth_next'] = request.GET.get('next') or ('/perfil/' if request.user.is_authenticated else '/')
    params = urllib.parse.urlencode({
        'client_id': settings.DISCORD_OAUTH_CLIENT_ID,
        'redirect_uri': _discord_redirect_uri(request),
        'response_type': 'code',
        'scope': 'identify email',
        'state': state,
        'prompt': 'consent',
    })
    return redirect(_DISCORD_API + '/oauth2/authorize?' + params)


def discord_callback(request):
    """Callback do Discord: troca code por token, busca o usuário e vincula/loga/cria."""
    from .models import UserProfile
    if request.GET.get('error'):
        return redirect('/login/?discord=cancelado')
    code = request.GET.get('code')
    state = request.GET.get('state')
    saved_state = request.session.pop('discord_oauth_state', None)
    if not code or not state or state != saved_state:
        import sys
        print('[discord_callback] state check falhou: code=%s state=%s saved_state=%s (sessão persistiu? %s)'
              % (bool(code), bool(state), bool(saved_state), bool(saved_state)), file=sys.stderr)
        return redirect('/login/?discord=erro_state')
    nxt = request.session.pop('discord_oauth_next', '/')
    try:
        token = _discord_post_token(code, _discord_redirect_uri(request))
        duser = _discord_get_me(token['access_token'])
    except Exception as e:
        import sys, urllib.error
        detalhe = repr(e)
        if isinstance(e, urllib.error.HTTPError):
            try:
                detalhe += ' | body=' + e.read().decode('utf-8', 'replace')[:400]
            except Exception:
                pass
        print('[discord_callback] falha na troca de token/usuário: %s | redirect_uri usado=%s'
              % (detalhe, _discord_redirect_uri(request)), file=sys.stderr)
        return redirect('/login/?discord=erro_token')
    discord_id = str(duser.get('id') or '')
    discord_name = duser.get('global_name') or duser.get('username') or ''
    discord_email = duser.get('email')
    if not discord_id:
        return redirect('/login/?discord=erro')
    User = get_user_model()

    # 1) Usuário já logado → VINCULAR ao Discord
    if request.user.is_authenticated:
        clash = (UserProfile.objects.filter(discord_user_id=discord_id)
                 .exclude(user=request.user).select_related('user').first())
        # Só bloqueia se o Discord já estiver numa conta REAL (com senha). Se estiver preso
        # a uma conta "fantasma" (criada pelo próprio login com Discord, sem senha definida),
        # o dono — que acabou de provar posse via OAuth — reivindica: solta o vínculo da
        # fantasma e segue. É isso que destrava "conectar Discord a uma conta já existente".
        if clash and clash.user.has_usable_password():
            return redirect('/perfil/?discord=ja_vinculado')
        with transaction.atomic():
            if clash:
                clash.discord_user_id = None
                clash.discord_username = None
                clash.save(update_fields=['discord_user_id', 'discord_username'])
            prof, _ = UserProfile.objects.get_or_create(user=request.user)
            prof.discord_user_id = discord_id
            prof.discord_username = discord_name
            prof.save(update_fields=['discord_user_id', 'discord_username'])
        return redirect('/perfil/?discord=vinculado')

    # 2) Não logado → achar conta pelo discord_user_id
    prof = UserProfile.objects.filter(discord_user_id=discord_id).select_related('user').first()
    if prof:
        login(request, prof.user)
        return redirect(nxt)

    # 3) Casar por e-mail (vincula a conta existente) ou criar nova
    user = User.objects.filter(email__iexact=discord_email).first() if discord_email else None
    if user is None:
        user = User.objects.create_user(username=_discord_unique_username(User, discord_name or ('discord_' + discord_id)),
                                        email=discord_email or '')
        user.set_unusable_password()
        user.save()
    prof, _ = UserProfile.objects.get_or_create(user=user)
    prof.discord_user_id = discord_id
    prof.discord_username = discord_name
    # Discord já entrega o e-mail confirmado → confia nele (vale p/ login e cobrança),
    # desde que ninguém mais já tenha verificado esse mesmo e-mail.
    ja_verif = bool(discord_email) and UserProfile.objects.filter(
        user__email__iexact=discord_email, email_verified=True).exclude(user=user).exists()
    prof.email_verified = bool(discord_email and duser.get('verified') and not ja_verif)
    prof.save(update_fields=['discord_user_id', 'discord_username', 'email_verified'])
    login(request, user)
    return redirect(nxt)


@login_required(login_url='/login/')
@require_POST
def discord_unlink(request):
    """Desvincula a conta do Discord."""
    from .models import UserProfile
    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    prof.discord_user_id = None
    prof.discord_username = None
    prof.save(update_fields=['discord_user_id', 'discord_username'])
    return redirect('/perfil/?discord=desvinculado')


def classes_view(request):
    return _postgres_classes_view(request)


def _postgres_classes_view(request):
    classes = TbClasse.objects.all().order_by('nome')
    total_habilidades = TbClassehabilidade.objects.count()
    total_subclasses = TbSubclasse.objects.count()
    context = {
        'classe': None,
        'all_classes': classes,
        'class_traits': [],
        'multiclass_traits': [],
        'subclasses': [],
        'habilidade_sections': [],
        'progression_table': [],
        'colunas': [],
        'spell_slots_count': 0,
        'total_habilidades': total_habilidades,
        'total_subclasses': total_subclasses,
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/classe_detail_content.html', context)
    return render(request, 'home/pages/classe_detail.html', context)


def _mongo_classes_view(request):
    classes = [_mongo_classe(doc) for doc in _mongo_docs('classes', [('Nome', 1)])]
    context = {
        'classe': None,
        'all_classes': classes,
        'class_traits': [],
        'multiclass_traits': [],
        'subclasses': [],
        'habilidade_sections': [],
        'progression_table': [],
        'colunas': [],
        'spell_slots_count': 0,
        'total_habilidades': _mongo_collection('class_features').count_documents({}),
        'total_subclasses': _mongo_collection('subclasses').count_documents({}),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/classe_detail_content.html', context)
    return render(request, 'home/pages/classe_detail.html', context)


def _normalize_key(value):
    normalized = unicodedata.normalize('NFKD', value or '')
    without_accents = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '_', without_accents.lower()).strip('_')


def _is_feature_column(column_name):
    return _normalize_key(column_name) in {
        'habilidades',
        'habilidades_de_classe',
        'caracteristicas',
        'caracteristicas_de_classe',
        'features',
    }


def _spell_slot_level(column_name):
    match = re.match(r'^\s*(\d+)\s*[º°ª]?\s*$', column_name or '')
    if not match:
        return None
    level = int(match.group(1))
    return level if 1 <= level <= 9 else None


def _display_column_name(column_name):
    if _is_feature_column(column_name):
        return 'Habilidades'
    spell_level = _spell_slot_level(column_name)
    if spell_level:
        return f'{spell_level}º'
    return column_name


def _column_key(column):
    if column['is_feature']:
        return 'habilidades'
    if column['spell_level']:
        return f"spell_{column['spell_level']}"
    return _normalize_key(column['name'])


def _tag_levels(tags_json, verb):
    """Extrai os níveis de uma tag de classe como `verb{4, 8, 12, ...}`."""
    for tag in (tags_json or []):
        match = re.match(rf'^{re.escape(verb)}\s*\{{(.+)\}}\s*$', str(tag).strip())
        if match:
            return {int(n) for n in re.findall(r'\d+', match.group(1))}
    return set()


def _eh_feature_asi(nome):
    """True se a habilidade é a feature de ASI (Aumento de Atributo ou Talento).

    Os níveis de ASI são declarados na tag da classe (`asi-choices`), então a
    feature real não precisa de tag própria; ela é detectada pelo nome para sair
    da coluna da tabela (o marcador 'Incremento de Atributo ou Talento' é injetado no lugar)."""
    chave = _normalize_key(nome)
    if 'atributo' not in chave:
        return False
    return any(p in chave for p in ('aumento', 'incremento', 'aprimoramento', 'talento'))


def _valor_recurso_no_nivel(recurso, nivel):
    """Valor de um recurso no nível dado.

    Formato consolidado (`valores_json` = {nivel: valor}): pega o maior nível
    <= nivel (carry-forward). Formato legado (1 linha por nível): só casa no
    nível exato, preservando a renderização antiga das classes ainda não
    repaginadas."""
    vj = recurso.valores_json or {}
    if vj:
        candidatos = [int(k) for k in vj if int(k) <= nivel]
        if candidatos:
            return vj[str(max(candidatos))]
        return None
    if recurso.nivel == nivel:
        return recurso.valor
    return None


@ensure_csrf_cookie  # edição inline (wiki) lê o csrftoken do cookie
def classe_detail_view(request, slug):
    return _postgres_classe_detail_view(request, slug)


def _postgres_classe_detail_view(request, slug):
    classe = get_object_or_404(TbClasse, slug=slug)
    all_classes = TbClasse.objects.all().order_by('nome')
    subclasses = TbSubclasse.objects.filter(id_classe=classe).order_by('nome')
    selected_subclass_slug = request.GET.get('subclasse', '')

    base_habilidades_qs = TbClassehabilidade.objects.filter(
        id_classe=classe,
        id_subclasse__isnull=True,
    ).order_by('niveladquirido', 'nome')
    subclass_habilidades_qs = TbClassehabilidade.objects.filter(
        id_classe=classe,
        id_subclasse__isnull=False,
    ).select_related('id_subclasse').order_by('niveladquirido', 'nome')

    habilidades = list(base_habilidades_qs.filter(table_only=False))
    subclass_habilidades = list(subclass_habilidades_qs.filter(table_only=False))
    habilidade_sections = sorted(
        [
            {
                'habilidade': habilidade,
                'is_subclass': False,
                'subclasse': None,
                'subclasse_slug': '',
            }
            for habilidade in habilidades
        ] + [
            {
                'habilidade': habilidade,
                'is_subclass': True,
                'subclasse': habilidade.id_subclasse,
                'subclasse_slug': habilidade.id_subclasse.slug if habilidade.id_subclasse else '',
            }
            for habilidade in subclass_habilidades
        ],
        key=lambda item: (
            item['habilidade'].niveladquirido,
            1 if item['is_subclass'] else 0,
            item['subclasse'].nome if item['subclasse'] else '',
            1 if _normalize_key(item['habilidade'].nome) == 'magias_de_origem' else 0,
            item['habilidade'].nome,
        )
    )

    class_traits = [
        ('Atributo Principal', classe.atributo_principal),
        ('Dado de Vida', classe.dado_vida),
        ('PV Nivel 1', classe.pv_nivel_1),
        ('PV por Nivel', classe.pv_por_nivel),
        ('Resistencias', classe.resistencias),
        ('Pericias', classe.pericias),
        ('Armas', classe.armas),
        ('Ferramentas', classe.ferramentas),
        ('Armaduras', classe.armaduras),
        ('Equipamento', classe.equipamento),
    ]
    class_traits = [{'label': label, 'value': value} for label, value in class_traits if value]

    multiclass_traits = [
        ('Requisitos', classe.multiclass_requisitos),
        ('Pericias', classe.multiclass_pericias),
        ('Armas', classe.multiclass_armas),
        ('Ferramentas', classe.multiclass_ferramentas),
        ('Armaduras', classe.multiclass_armaduras),
    ]
    multiclass_traits = [
        {'label': label, 'value': value if value and str(value).strip() else '-'}
        for label, value in multiclass_traits
    ]

    columns = []
    seen_columns = set()
    recursos = TbRecursoclasse.objects.filter(
        id_classe=classe,
    ).select_related('id_subclasse').order_by(F('id_subclasse_id').asc(nulls_first=True), 'id_recurso')

    for recurso in recursos:
        is_feature = _is_feature_column(recurso.nome)
        spell_level = _spell_slot_level(recurso.nome)
        column = {
            'name': _display_column_name(recurso.nome),
            'source_names': [recurso.nome],
            'is_feature': is_feature,
            'spell_level': spell_level,
            'has_base': recurso.id_subclasse_id is None,
            'subclass_slugs': [] if recurso.id_subclasse_id is None else [recurso.id_subclasse.slug],
        }
        key = _column_key(column)

        if key not in seen_columns:
            seen_columns.add(key)
            columns.append(column)
            continue

        for existing in columns:
            if _column_key(existing) != key:
                continue
            if recurso.nome not in existing['source_names']:
                existing['source_names'].append(recurso.nome)
            if recurso.id_subclasse_id is None:
                existing['has_base'] = True
            elif recurso.id_subclasse.slug not in existing['subclass_slugs']:
                existing['subclass_slugs'].append(recurso.id_subclasse.slug)
            break

    if not any(column['is_feature'] for column in columns):
        insert_at = 1 if columns and _normalize_key(columns[0]['name']) in {'pb', 'proficiencia', 'bonus_de_proficiencia'} else len(columns)
        columns.insert(insert_at, {
            'name': 'Habilidades',
            'source_names': [],
            'is_feature': True,
            'spell_level': None,
            'has_base': True,
            'subclass_slugs': [],
        })

    for column in columns:
        column['subclass_slugs_attr'] = ' '.join(column['subclass_slugs'])
        column['subclass_only'] = not column['has_base'] and bool(column['subclass_slugs'])

    spell_columns = sorted([column for column in columns if column['spell_level']], key=lambda column: column['spell_level'])
    regular_columns = [column for column in columns if not column['spell_level']]
    base_spell_slots_count = len([column for column in spell_columns if not column['subclass_only']])
    columns = regular_columns + spell_columns

    # Níveis de ASI vêm da tag de classe (asi-choices{...}); o marcador
    # "Incremento de Atributo ou Talento" é injetado na tabela, então não precisamos de
    # linhas table_only placeholder. As features ASI reais ficam como seções
    # (explicação na wiki), mas saem da coluna da tabela (detectadas pelo nome)
    # para não duplicar o marcador injetado.
    asi_levels = _tag_levels(classe.tags_json, 'asi-choices')

    habilidades_para_tabela = [h for h in base_habilidades_qs if not _eh_feature_asi(h.nome)]
    habilidades_para_tabela.extend(
        h for h in subclass_habilidades_qs if not _eh_feature_asi(h.nome)
    )

    habilidades_por_nivel = {}
    for habilidade in habilidades_para_tabela:
        habilidades_por_nivel.setdefault(habilidade.niveladquirido, []).append(habilidade)

    def render_habilidades_nivel(nivel):
        partes = [
            format_html(
                '<span class="block {}"{}>{}</span>',
                'hidden subclass-feature text-[var(--spark)] font-bold' if item.id_subclasse_id else 'text-[var(--text)]',
                format_html(' data-subclass-slug="{}"', item.id_subclasse.slug) if item.id_subclasse_id else '',
                item.nome,
            )
            for item in habilidades_por_nivel.get(nivel, [])
        ]
        if nivel in asi_levels:
            partes.append(format_html(
                '<span class="block text-[var(--text)]">{}</span>', 'Incremento de Atributo ou Talento'
            ))
        if not partes:
            return '-'
        return format_html_join('', '{}', ((parte,) for parte in partes))

    base_recursos = list(recursos.filter(id_subclasse__isnull=True))
    sub_recursos = list(recursos.filter(id_subclasse__isnull=False))

    progression_table = []
    for nivel in range(1, 21):
        recs_nivel = {}
        subclass_recs_nivel = {}
        for recurso in base_recursos:
            valor = _valor_recurso_no_nivel(recurso, nivel)
            if valor is not None:
                recs_nivel.setdefault(recurso.nome, valor)

        for recurso in sub_recursos:
            valor = _valor_recurso_no_nivel(recurso, nivel)
            if valor is not None:
                subclass_recs_nivel.setdefault(recurso.nome, []).append(
                    (valor, recurso.id_subclasse.slug)
                )

        def render_recurso_coluna(column):
            parts = []
            has_value = False
            has_subclass_value = False

            for name in column['source_names']:
                if name in recs_nivel:
                    has_value = True
                    parts.append(format_html('<span class="block">{}</span>', recs_nivel[name] or '-'))

                for value, subclasse_slug in subclass_recs_nivel.get(name, []):
                    has_subclass_value = True
                    parts.append(format_html(
                        '<span class="hidden subclass-feature text-[var(--spark)] font-bold" data-subclass-slug="{}">{}</span>',
                        subclasse_slug,
                        value or '-',
                    ))

            if has_subclass_value and not has_value:
                parts.insert(0, format_html('<span class="subclass-resource-empty">{}</span>', '-'))

            if not parts:
                return '-'

            return format_html_join('', '{}', ((part,) for part in parts))

        valores = []
        for column in columns:
            if column['is_feature']:
                valores.append(render_habilidades_nivel(nivel))
                continue

            valores.append(render_recurso_coluna(column))

        progression_table.append({
            'nivel': nivel,
            'valores': valores,
            'cells': [{'col': column, 'valor': valor} for column, valor in zip(columns, valores)],
            'pares': [{'col': column, 'nome': column['name'], 'valor': valor} for column, valor in zip(columns, valores)],
        })

    context = {
        'classe': classe,
        'all_classes': all_classes,
        'habilidades': habilidades,
        'subclasses': subclasses,
        'selected_subclass_slug': selected_subclass_slug,
        'subclass_habilidades': subclass_habilidades,
        'habilidade_sections': habilidade_sections,
        'class_traits': class_traits,
        'multiclass_traits': multiclass_traits,
        'colunas': columns,
        'regular_columns_count': len(regular_columns),
        'spell_slots_count': len(spell_columns),
        'base_spell_slots_count': base_spell_slots_count,
        'progression_table': progression_table,
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/classe_detail_content.html', context)
    return render(request, 'home/pages/classe_detail.html', context)


def _mongo_classe_detail_view(request, slug):
    classe_doc = _mongo_one('classes', {'Slug': slug})
    if not classe_doc:
        raise Http404("Classe nao encontrada")

    all_classes = [_mongo_classe(doc) for doc in _mongo_docs('classes', [('Nome', 1)])]
    classes_by_id = {classe.id_classe: classe for classe in all_classes}
    classe = _mongo_classe(classe_doc)
    classes_by_id[classe.id_classe] = classe

    subclass_docs = _mongo_docs('subclasses', [('Nome', 1)], {'Id_Classe': classe.id_classe})
    subclasses = [_mongo_subclasse(doc, classes_by_id) for doc in subclass_docs]
    subclasses_by_id = {sub.id_subclasse: sub for sub in subclasses}
    selected_subclass_slug = request.GET.get('subclasse', '')

    habilidade_docs = _mongo_docs('class_features', [('NivelAdquirido', 1), ('Nome', 1)], {'Id_Classe': classe.id_classe})
    all_habilidades = [_mongo_habilidade(doc, classes_by_id, subclasses_by_id) for doc in habilidade_docs]
    base_habilidades = [item for item in all_habilidades if not item.id_subclasse_id]
    subclass_habilidades_all = [item for item in all_habilidades if item.id_subclasse_id]
    habilidades = [item for item in base_habilidades if not item.table_only]
    subclass_habilidades = [item for item in subclass_habilidades_all if not item.table_only]

    habilidade_sections = sorted(
        [
            {'habilidade': habilidade, 'is_subclass': False, 'subclasse': None, 'subclasse_slug': ''}
            for habilidade in habilidades
        ] + [
            {
                'habilidade': habilidade,
                'is_subclass': True,
                'subclasse': habilidade.id_subclasse,
                'subclasse_slug': habilidade.id_subclasse.slug if habilidade.id_subclasse else '',
            }
            for habilidade in subclass_habilidades
        ],
        key=lambda item: (
            item['habilidade'].niveladquirido,
            1 if item['is_subclass'] else 0,
            item['subclasse'].nome if item['subclasse'] else '',
            1 if _normalize_key(item['habilidade'].nome) == 'magias_de_origem' else 0,
            item['habilidade'].nome,
        )
    )

    class_traits = [
        ('Atributo Principal', classe.atributo_principal),
        ('Dado de Vida', classe.dado_vida),
        ('PV Nivel 1', classe.pv_nivel_1),
        ('PV por Nivel', classe.pv_por_nivel),
        ('Resistencias', classe.resistencias),
        ('Pericias', classe.pericias),
        ('Armas', classe.armas),
        ('Ferramentas', classe.ferramentas),
        ('Armaduras', classe.armaduras),
        ('Equipamento', classe.equipamento),
    ]
    class_traits = [{'label': label, 'value': value} for label, value in class_traits if value]

    multiclass_traits = [
        ('Requisitos', classe.multiclass_requisitos),
        ('Pericias', classe.multiclass_pericias),
        ('Armas', classe.multiclass_armas),
        ('Ferramentas', classe.multiclass_ferramentas),
        ('Armaduras', classe.multiclass_armaduras),
    ]
    multiclass_traits = [{'label': label, 'value': value} for label, value in multiclass_traits if value]

    recursos = [
        _mongo_recurso(doc, classes_by_id, subclasses_by_id)
        for doc in _mongo_docs('class_resources', [('Id_Subclasse', 1), ('Id_Recurso', 1)], {'Id_Classe': classe.id_classe})
    ]

    columns = []
    seen_columns = set()
    for recurso in recursos:
        is_feature = _is_feature_column(recurso.nome)
        spell_level = _spell_slot_level(recurso.nome)
        column = {
            'name': _display_column_name(recurso.nome),
            'source_names': [recurso.nome],
            'is_feature': is_feature,
            'spell_level': spell_level,
            'has_base': recurso.id_subclasse_id is None,
            'subclass_slugs': [] if recurso.id_subclasse_id is None else [recurso.id_subclasse.slug],
        }
        key = _column_key(column)
        if key not in seen_columns:
            seen_columns.add(key)
            columns.append(column)
            continue

        for existing in columns:
            if _column_key(existing) != key:
                continue
            if recurso.nome not in existing['source_names']:
                existing['source_names'].append(recurso.nome)
            if recurso.id_subclasse_id is None:
                existing['has_base'] = True
            elif recurso.id_subclasse.slug not in existing['subclass_slugs']:
                existing['subclass_slugs'].append(recurso.id_subclasse.slug)
            break

    if not any(column['is_feature'] for column in columns):
        insert_at = 1 if columns and _normalize_key(columns[0]['name']) in {'pb', 'proficiencia', 'bonus_de_proficiencia'} else len(columns)
        columns.insert(insert_at, {
            'name': 'Habilidades',
            'source_names': [],
            'is_feature': True,
            'spell_level': None,
            'has_base': True,
            'subclass_slugs': [],
        })

    for column in columns:
        column['subclass_slugs_attr'] = ' '.join(column['subclass_slugs'])
        column['subclass_only'] = not column['has_base'] and bool(column['subclass_slugs'])

    spell_columns = sorted([column for column in columns if column['spell_level']], key=lambda column: column['spell_level'])
    regular_columns = [column for column in columns if not column['spell_level']]
    base_spell_slots_count = len([column for column in spell_columns if not column['subclass_only']])
    columns = regular_columns + spell_columns

    habilidades_por_nivel = {}
    for habilidade in all_habilidades:
        habilidades_por_nivel.setdefault(habilidade.niveladquirido, []).append(habilidade)

    def render_habilidades_nivel(nivel):
        itens = habilidades_por_nivel.get(nivel, [])
        if not itens:
            return '-'
        return format_html_join(
            '',
            '{}',
            (
                (
                    format_html(
                        '<span class="block {}"{}>{}</span>',
                        'hidden subclass-feature text-[var(--spark)] font-bold' if item.id_subclasse_id else 'text-[var(--text)]',
                        format_html(' data-subclass-slug="{}"', item.id_subclasse.slug) if item.id_subclasse_id else '',
                        item.nome,
                    ),
                )
                for item in itens
            )
        )

    recursos_por_nivel = {}
    for recurso in recursos:
        recursos_por_nivel.setdefault(recurso.nivel, []).append(recurso)

    progression_table = []
    for nivel in range(1, 21):
        recs_nivel = {}
        subclass_recs_nivel = {}
        for recurso in recursos_por_nivel.get(nivel, []):
            if recurso.id_subclasse_id is None:
                recs_nivel.setdefault(recurso.nome, recurso.valor)
            else:
                subclass_recs_nivel.setdefault(recurso.nome, []).append((recurso.valor, recurso.id_subclasse.slug))

        def render_recurso_coluna(column):
            parts = []
            has_value = False
            has_subclass_value = False
            for name in column['source_names']:
                if name in recs_nivel:
                    has_value = True
                    parts.append(format_html('<span class="block">{}</span>', recs_nivel[name] or '-'))
                for value, subclasse_slug in subclass_recs_nivel.get(name, []):
                    has_subclass_value = True
                    parts.append(format_html(
                        '<span class="hidden subclass-feature text-[var(--spark)] font-bold" data-subclass-slug="{}">{}</span>',
                        subclasse_slug,
                        value or '-',
                    ))
            if has_subclass_value and not has_value:
                parts.insert(0, format_html('<span class="subclass-resource-empty">{}</span>', '-'))
            if not parts:
                return '-'
            return format_html_join('', '{}', ((part,) for part in parts))

        valores = []
        for column in columns:
            if column['is_feature']:
                valores.append(render_habilidades_nivel(nivel))
            else:
                valores.append(render_recurso_coluna(column))

        progression_table.append({
            'nivel': nivel,
            'valores': valores,
            'cells': [{'col': column, 'valor': valor} for column, valor in zip(columns, valores)],
            'pares': [{'col': column, 'nome': column['name'], 'valor': valor} for column, valor in zip(columns, valores)],
        })

    context = {
        'classe': classe,
        'all_classes': all_classes,
        'habilidades': habilidades,
        'subclasses': subclasses,
        'selected_subclass_slug': selected_subclass_slug,
        'subclass_habilidades': subclass_habilidades,
        'habilidade_sections': habilidade_sections,
        'class_traits': class_traits,
        'multiclass_traits': multiclass_traits,
        'colunas': columns,
        'regular_columns_count': len(regular_columns),
        'spell_slots_count': len(spell_columns),
        'base_spell_slots_count': base_spell_slots_count,
        'progression_table': progression_table,
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/classe_detail_content.html', context)
    return render(request, 'home/pages/classe_detail.html', context)


def racas_view(request):
    return _postgres_racas_view(request)


def _postgres_racas_view(request):
    racas = TbRaca.objects.all().order_by('nome')
    context = {
        'raca': None,
        'all_racas': racas,
        'selected_raca_id': None,
        'tracos_base': [],
        'linhagens': [],
        'total_linhagens': TbLinhagem.objects.count(),
        'total_tracos': TbTracoracial.objects.count(),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


@ensure_csrf_cookie  # edição inline (wiki) faz POST com X-CSRFToken lido do cookie
def raca_detail_view(request, slug):
    return _postgres_raca_detail_view(request, slug)


def _postgres_raca_detail_view(request, slug):
    raca = get_object_or_404(TbRaca, slug=slug)
    racas = TbRaca.objects.all().order_by('nome')
    tracos_base = raca.tracos.all().order_by('nivel_requisito', 'nome')
    linhagens = raca.linhagens.all().prefetch_related('tracos_linhagem').order_by('nome')
    essencias = TbEssencia.objects.all().prefetch_related('tracos').order_by('nome')

    # Image mapping
    RACE_IMAGES = {
        'anao': 'https://i.imgur.com/base-dwarf-placeholder.png',
        'humano': 'https://i.imgur.com/base-human-placeholder.png',
        'elfo': 'https://i.imgur.com/base-elf-placeholder.png',
        'orc': 'https://i.imgur.com/base-orc-placeholder.png',
    }

    LINEAGE_IMAGES = {
        'montanha': 'https://i.imgur.com/mountain-dwarf-placeholder.png',
        'profundezas': 'https://i.imgur.com/deep-dwarf-placeholder.png',
        'erthari': 'https://i.imgur.com/erthari-human-placeholder.png',
        'salarin': 'https://i.imgur.com/salarin-human-placeholder.png',
        'durkarn': 'https://i.imgur.com/durkarn-human-placeholder.png',
        'goruun': 'https://i.imgur.com/goruun-human-placeholder.png',
    }

    ESSENCE_IMAGES = {
        'vampirismo': 'https://i.imgur.com/vampire-essence-placeholder.png',
        'nephilim': 'https://i.imgur.com/nephilim-essence-placeholder.png',
        'draconica': 'https://i.imgur.com/draconic-essence-placeholder.png',
        'elemental': 'https://i.imgur.com/elemental-essence-placeholder.png',
    }

    # Stat mapping
    RACE_STATS_MAP = {
        'anao': {
            'creatureType': 'Humanoide',
            'size': 'Médio (1,20m – 1,50m)',
            'speed': '9 metros [30 pés]',
            'lifespan': '350 anos'
        },
        'humano': {
            'creatureType': 'Humanoide',
            'size': 'Médio (1,50m – 1,90m)',
            'speed': '9 metros [30 pés]',
            'lifespan': '90 anos'
        },
        'elfo': {
            'creatureType': 'Humanoide',
            'size': 'Médio (1,60m – 1,90m)',
            'speed': '9 metros [30 pés]',
            'lifespan': '700 anos'
        },
        'orc': {
            'creatureType': 'Humanoide',
            'size': 'Médio (1,80m – 2,10m)',
            'speed': '9 metros [30 pés]',
            'lifespan': '80 anos'
        }
    }

    default_stats = {
        'creatureType': 'Humanoide',
        'size': 'Médio',
        'speed': '9 metros [30 pés]',
        'lifespan': '100 anos'
    }

    stats = RACE_STATS_MAP.get(raca.slug, default_stats)
    raca.image_url = RACE_IMAGES.get(raca.slug, 'https://i.imgur.com/base-human-placeholder.png')

    for lin in linhagens:
        lin.image_url = LINEAGE_IMAGES.get(lin.slug, raca.image_url)

    for ess in essencias:
        ess.image_url = ESSENCE_IMAGES.get(ess.slug, 'https://i.imgur.com/nephilim-essence-placeholder.png')

    # Collect talents
    talents = []
    # 1. Base race talents
    for t in tracos_base:
        if t.talento_racial:
            t.source = "Raça"
            t.source_color = "text-[var(--text)] border-[var(--stroke)]"
            talents.append(t)
    # 2. Lineage talents
    for lin in linhagens:
        for t in lin.tracos_linhagem.all():
            if t.talento_racial:
                t.source = "Linhagem"
                t.source_color = "text-[var(--ember)] border-[var(--ember)]"
                talents.append(t)
    # 3. Essence talents
    for ess in essencias:
        for t in ess.tracos.all():
            if t.talento_racial:
                t.source = "Essência"
                t.source_color = "text-purple-400 border-purple-500"
                talents.append(t)

    # 4. Other races base talents (only when current race is human, for Goruun, Durkarn, Sálarin)
    if raca.slug == 'humano':
        other_talents = TbTracoracial.objects.filter(
            id_raca__slug__in=['anao', 'elfo', 'orc'],
            talento_racial=True,
            id_linhagem=None,
            id_essencia=None
        ).select_related('id_raca')
        for t in other_talents:
            t.source = t.id_raca.nome
            if t.id_raca.slug == 'anao':
                t.source_color = "text-amber-500 border-amber-600"
            elif t.id_raca.slug == 'elfo':
                t.source_color = "text-emerald-500 border-emerald-600"
            else: # orc
                t.source_color = "text-red-500 border-red-600"
            talents.append(t)

    talents.sort(key=lambda x: x.nome)

    context = {
        'raca': raca,
        'all_racas': racas,
        'selected_raca_id': raca.id_raca,
        'tracos_base': tracos_base,
        'linhagens': linhagens,
        'essencias': essencias,
        'stats': stats,
        'talents': talents,
        'levels': [1, 5, 9, 13, 17],
        'total_linhagens': TbLinhagem.objects.count(),
        'total_tracos': TbTracoracial.objects.count(),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


def _mongo_racas_view(request):
    racas = [_mongo_raca(doc) for doc in _mongo_docs('races', [('Nome', 1)])]
    context = {
        'raca': None,
        'all_racas': racas,
        'selected_raca_id': None,
        'tracos_base': [],
        'linhagens': [],
        'total_linhagens': _mongo_collection('lineages').count_documents({}),
        'total_tracos': _mongo_collection('racial_traits').count_documents({}),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


def _mongo_raca_detail_view(request, slug):
    raca_doc = _mongo_one('races', {'Slug': slug})
    if not raca_doc:
        raise Http404("Raca nao encontrada")
    raca = _mongo_raca(raca_doc)
    racas = [_mongo_raca(doc) for doc in _mongo_docs('races', [('Nome', 1)])]
    tracos = [_mongo_traco(doc) for doc in _mongo_docs('racial_traits', [('NivelRequisito', 1), ('Nome', 1)])]
    tracos_base = [traco for traco in tracos if traco.id_raca_id == raca.id_raca]
    tracos_por_linhagem = {}
    for traco in tracos:
        if traco.id_linhagem_id:
            tracos_por_linhagem.setdefault(traco.id_linhagem_id, []).append(traco)

    linhagens = [
        _mongo_linhagem(doc, tracos_por_linhagem.get(doc.get('Id_Linhagem'), []))
        for doc in _mongo_docs('lineages', [('Nome', 1)], {'Id_Raca': raca.id_raca})
    ]

    context = {
        'raca': raca,
        'all_racas': racas,
        'selected_raca_id': raca.id_raca,
        'tracos_base': tracos_base,
        'linhagens': linhagens,
        'total_linhagens': _mongo_collection('lineages').count_documents({}),
        'total_tracos': _mongo_collection('racial_traits').count_documents({}),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


def regras_punicoes_view(request):
    return render(request, 'home/pages/regras_punicoes.html')


def guia_mestres_view(request):
    return render(request, 'home/pages/guia_mestres.html')


def _parse_mongo_date(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return timezone.localtime(parsed)


def _quest_discord_url(quest):
    guild_id = quest.get('guildId')
    channel_id = quest.get('channelId')
    if guild_id and channel_id:
        return f'https://discord.com/channels/{guild_id}/{channel_id}'
    return ''


def sistemas_missoes_view(request):
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    allowed_status = {'idle', 'running', 'paused', 'frozen', 'finished'}
    if status not in allowed_status:
        status = ''

    quests = []
    mongo_error = ''
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT id, name, description, "questDate", "playersAmount",
                       "subscribedPlayers", "questPlayers", status, type, tags,
                       "questMaster", "tableUrl", "guildId", "channelId"
                FROM "Quest"
                WHERE "isPublished" = true
            """
            params = []
            if status:
                query += ' AND status = %s'
                params.append(status)
            if search:
                query += ' AND name ILIKE %s'
                params.append(f'%{search}%')
            
            query += ' ORDER BY "questDate" DESC LIMIT 100'
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                quest = dict(zip(columns, row))
                
                # Parse JSON arrays safely
                def parse_json(val):
                    if isinstance(val, list): return val
                    if isinstance(val, str):
                        try:
                            return json.loads(val)
                        except:
                            return []
                    return []
                
                subscribed_players = parse_json(quest['subscribedPlayers'])
                quest_players = parse_json(quest['questPlayers'])
                players_amount = quest['playersAmount'] or 0
                
                quests.append({
                    'id': quest['id'],
                    'name': quest['name'] or 'Missao sem nome',
                    'description': quest['description'] or '',
                    'quest_date': quest['questDate'],
                    'players_amount': players_amount,
                    'filled_slots': len(quest_players),
                    'queue_amount': len(subscribed_players),
                    'status': quest['status'] or 'idle',
                    'type': quest['type'] or '',
                    'tags': parse_json(quest['tags']),
                    'quest_master': quest['questMaster'] or '',
                    'table_url': quest['tableUrl'] or '',
                    'discord_url': f"https://discord.com/channels/{quest['guildId']}/{quest['channelId']}" if quest.get('guildId') and quest.get('channelId') else "",
                    'is_full': bool(players_amount and len(quest_players) >= players_amount),
                })
    except Exception as exc:
        mongo_error = str(exc)

    context = {
        'quests': quests,
        'search': search,
        'status': status,
        'mongo_error': mongo_error,
        'status_options': [
            ('', 'Ativas'),
            ('idle', 'Abertas'),
            ('running', 'Em andamento'),
            ('paused', 'Pausadas'),
            ('frozen', 'Congeladas'),
            ('finished', 'Finalizadas'),
        ],
    }
    return render(request, 'home/pages/missoes.html', context)


def placeholder_view(request, title='Notas de Atualizacao'):
    return render(request, 'home/pages/placeholder.html', {'page_title': title})


# ════════════════════════ Página de Colaborador (Asaas) ════════════════════════
# Vitrine de doação/assinatura que espelha o embed do comando `/colab-info` do bot
# (src/modules/discord/commands/bonfire/subscription/subscriptionEmbeds.ts). Usa os
# MESMOS links de checkout do Asaas. Os benefícios são concedidos no Discord pelo bot
# após o pagamento (webhook → tabela `transactions` → claim). Os preços trimestral/
# semestral/anual vêm de `bonfireSubscriptionOffers` (config do bot).
COLABORADOR_TIERS = [
    {
        'key': 'conde',
        'titulo': 'Conde / Condessa',
        'emoji': '👑',
        'preco_mes': '19,90',
        'destaque': False,
        'beneficios': [
            ('📌', 'Preferência em filas de missões (a partir do rank Ametista)'),
        ],
        'assinatura': 'https://www.asaas.com/c/8875kbi9lmlnbpbs',
        'unico': 'https://www.asaas.com/c/0d19cyn73or5ee4m',
        'planos': [
            {'label': 'Trimestral', 'off': '10% OFF', 'preco': '53,73', 'url': 'https://www.asaas.com/c/gggvz2l87g6ah4rs'},
            {'label': 'Semestral', 'off': '15% OFF', 'preco': '101,49', 'url': 'https://www.asaas.com/c/74zeloshnmy8qf6d'},
            {'label': 'Anual', 'off': '25% OFF', 'preco': '179,10', 'url': 'https://www.asaas.com/c/8kbe3dbsjx5tl9c5'},
        ],
    },
    {
        'key': 'marques',
        'titulo': 'Marquês / Marquesa',
        'emoji': '👑',
        'preco_mes': '29,90',
        'destaque': False,
        'beneficios': [
            ('👥', '+1 Slot de personagem durante o mês (limite de +1, fora os de níveis específicos)'),
            ('📌', 'Preferência em filas de missões (a partir do rank Ametista)'),
            ('⚔️', '+1 Missão Especial (mensal)'),
        ],
        'assinatura': 'https://www.asaas.com/c/2icusjwxwyth44dl',
        'unico': 'https://www.asaas.com/c/vdc8h0lg9c6ni55z',
        'planos': [
            {'label': 'Trimestral', 'off': '10% OFF', 'preco': '80,73', 'url': 'https://www.asaas.com/c/ckm5u78s3yhkztf4'},
            {'label': 'Semestral', 'off': '15% OFF', 'preco': '152,49', 'url': 'https://www.asaas.com/c/js1wn7vwapvcis2k'},
            {'label': 'Anual', 'off': '25% OFF', 'preco': '269,10', 'url': 'https://www.asaas.com/c/mo3xjc7myj5q67g7'},
        ],
    },
    {
        'key': 'duque',
        'titulo': 'Duque / Duquesa',
        'emoji': '👑',
        'preco_mes': '39,90',
        'destaque': True,
        'beneficios': [
            ('👥', '+1 Slot de personagem durante o período (limite de +1, fora os de níveis específicos)'),
            ('📌', 'Preferência em filas de missões (a partir do rank Ametista)'),
            ('⚔️', '+1 Missão Especial (mensal)'),
            ('💥', '+1 Boost para uma missão (mensal)'),
            ('🔒', 'Possibilidade de colocar 1 personagem no cofre durante o mês'),
        ],
        'assinatura': 'https://www.asaas.com/c/p7ne3agr03yphhqx',
        'unico': 'https://www.asaas.com/c/ir2nwmgt3s950e02',
        'planos': [
            {'label': 'Trimestral', 'off': '10% OFF', 'preco': '107,73', 'url': 'https://www.asaas.com/c/m7uakneidrvso7a9'},
            {'label': 'Semestral', 'off': '15% OFF', 'preco': '203,49', 'url': 'https://www.asaas.com/c/en2ibwj3r29s77ig'},
            {'label': 'Anual', 'off': '25% OFF', 'preco': '359,10', 'url': 'https://www.asaas.com/c/hojk0lk7zssxsa8w'},
        ],
    },
]

COLABORADOR_TOKENS = [
    {'emoji': '⚔️', 'nome': 'Missão Especial', 'preco': '14,90',
     'desc': 'Garante +1 missão especial para você participar.',
     'url': 'https://www.asaas.com/c/4i2hskg41p4mszkg'},
    {'emoji': '💥', 'nome': 'Boost', 'preco': '19,90',
     'desc': 'Aumenta as recompensas de uma missão.',
     'url': 'https://www.asaas.com/c/seyli68v427zvbds'},
    {'emoji': '🚀', 'nome': 'Superboost', 'preco': '69,90',
     'desc': 'Turbina ainda mais as recompensas de uma missão.',
     'url': 'https://www.asaas.com/c/69cthesmlfcu15th'},
]


def colaborador_view(request):
    """Vitrine de pacotes de colaborador e tokens (links de checkout do Asaas)."""
    return render(request, 'home/pages/colaborador.html', {
        'page_title': 'Seja um Colaborador',
        'tiers': COLABORADOR_TIERS,
        'tokens': COLABORADOR_TOKENS,
    })


def _parse_skills_lvl1(tags_json):
    """(n, lista) de skills-lvl1{pick:N de [..]}; lista None = qualquer das 18."""
    for t in (tags_json or []):
        m = re.search(r'skills-lvl1\{([^}]*)\}', str(t))
        if m:
            inner = m.group(1)
            mn = re.search(r'pick:\s*(\d+)', inner)
            ml = re.search(r'\[([^\]]*)\]', inner)
            lista = [x.strip() for x in ml.group(1).split(',') if x.strip()] if ml else None
            return (int(mn.group(1)) if mn else 2, lista)
    return (2, None)


def _classe_maestria_n(classe, nivel=1):
    """Quantas ARMAS o jogador escolhe para Maestria de Arma neste nível (valor do
    recurso 'Maestria*com/em Armas'); 0 se a classe não concede maestria."""
    from .models import TbRecursoclasse
    for r in TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True):
        if 'maestria' in (r.slug or '').lower():
            vj = r.valores_json or {}
            ks = sorted(int(k) for k in vj if int(k) <= nivel)
            if ks:
                try:
                    return int(str(vj[str(ks[-1])]).strip())
                except (ValueError, TypeError):
                    return 0
    return 0


def _criador_armas():
    """Catálogo de armas (TbItemMundano categoria=arma) com suas maestrias resolvidas."""
    from .models import TbItemMundano, TbOpcaojogo
    mast = {o.slug: o.nome for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
    sub_label = {'arma_simples': 'Arma Simples', 'arma_simples_dist': 'Arma Simples à Distância',
                 'arma_marcial': 'Arma Marcial', 'arma_marcial_dist': 'Arma Marcial à Distância',
                 'arma_fogo': 'Arma de Fogo'}
    out = []
    for w in TbItemMundano.objects.filter(categoria='arma').order_by('subcategoria', 'nome'):
        mslugs = []
        for t in (w.tags_json or []):
            m = re.search(r'maestrias\{([^}]*)\}', str(t))
            if m:
                mslugs = [x.strip() for x in m.group(1).split(',') if x.strip()]
        out.append({'slug': w.slug, 'nome': w.nome, 'dano': w.dano or '',
                    'propriedades': w.propriedades or '',
                    'cat': sub_label.get(w.subcategoria, w.subcategoria or 'Arma'),
                    'maestrias': [mast.get(s, s) for s in mslugs]})
    return out


def _classe_escolhas_nv1(classe):
    """Escolhas de classe no nível 1 (além de perícias/maestria): estilo de luta e
    perícia-expertise. Lê os pick: das habilidades base de nível 1."""
    from .models import TbClassehabilidade
    from .character_engine import _SKILL_INFO
    estilo_n = expertise_n = 0
    expertise_fixa = []
    for h in TbClassehabilidade.objects.filter(id_classe=classe, id_subclasse__isnull=True, niveladquirido=1):
        for t in (h.tags_json or []):
            t = str(t)
            m = re.search(r'pick:opcao:estilo-de-luta:(\d+)', t)
            if m:
                estilo_n = int(m.group(1))
            m = re.search(r'pick:pericia-expertise:\{([^}]*)\}', t)
            if m:
                m2 = re.search(r'classlvl=1:(\d+)', m.group(1))
                if m2:
                    expertise_n = int(m2.group(1))
                else:
                    expertise_fixa += [s.strip() for s in re.split(r'[,\s]+', m.group(1)) if s.strip() in _SKILL_INFO]
    return {'estilo_n': estilo_n, 'expertise_n': expertise_n, 'expertise_fixa': expertise_fixa}


def _classe_conjuracao(classe):
    """Dados de conjuração da classe no nível 1: atributo, contagem de truques e de
    magias de 1º nível (explícita do recurso, ou None = fórmula mod+nível), + as listas."""
    from .models import TbClassehabilidade, TbRecursoclasse, TbMagia
    sc = None
    fontes = [classe] + list(TbClassehabilidade.objects.filter(
        id_classe=classe, id_subclasse__isnull=True, niveladquirido=1))
    for src in fontes:
        for t in (getattr(src, 'tags_json', None) or []):
            m = re.search(r'spellcasting\{([^}]*)\}', str(t))
            if m:
                sc = m.group(1)
    if not sc:
        return None
    ability = (re.search(r'ability:(\w+)', sc) or [None, 'int'])[1]

    def res_v1(substrs):
        for r in TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True):
            if any(s in (r.slug or '').lower() for s in substrs):
                vj = r.valores_json or {}
                ks = sorted(int(k) for k in vj if int(k) <= 1)
                if ks:
                    try:
                        return int(str(vj[str(ks[-1])]).strip())
                    except (ValueError, TypeError):
                        pass
        return None

    truques = [{'slug': m.slug, 'nome': m.nome}
               for m in TbMagia.objects.filter(nivel=0, classes__icontains=classe.nome).order_by('nome')]
    nv1 = [{'slug': m.slug, 'nome': m.nome, 'escola': m.escola or ''}
           for m in TbMagia.objects.filter(nivel=1, classes__icontains=classe.nome).order_by('nome')]
    return {'ability': ability, 'truques_n': res_v1(['truque']) or 0,
            'magias_n': res_v1(['magias-conhecidas', 'magias-preparadas']),
            'truques': truques, 'magias_nv1': nv1}


_AB_SIG = {'str': 'FOR', 'dex': 'DES', 'con': 'CON', 'int': 'INT', 'wis': 'SAB', 'cha': 'CAR'}

# Moedas em peças de cobre (PC). 1 PO = 100 PC, 1 PP = 10 PC, 1 PL = 1000 PC, 1 PE = 50 PC.
_MOEDA_PC = {'PC': 1, 'PP': 10, 'PO': 100, 'PL': 1000, 'PE': 50, 'CP': 1, 'SP': 10, 'GP': 100}


def _preco_em_pc(preco):
    """'5 PO' / '1 PP' / '1.500 PO' / '0,2 PC' -> peças de cobre (int). None se não comprável."""
    if not preco:
        return None
    m = re.match(r'\s*([\d.,]+)\s*(PC|PP|PO|PL|PE|CP|SP|GP)', str(preco).strip(), re.I)
    if not m:
        return None
    try:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
    except ValueError:
        return None
    return int(round(val * _MOEDA_PC.get(m.group(2).upper(), 0)))


def _pc_display(pc):
    """Peças de cobre -> 'X PO, Y PP, Z PC'."""
    pc = int(pc or 0)
    po, resto = divmod(pc, 100)
    pp, pc2 = divmod(resto, 10)
    parts = []
    if po:
        parts.append('%d PO' % po)
    if pp:
        parts.append('%d PP' % pp)
    if pc2:
        parts.append('%d PC' % pc2)
    return ', '.join(parts) or '0 PC'


_PRECO_VENDA_RATIO = 0.5  # itens mágicos vendem por 50% do preço de compra do mercado
_PRECO_VENDA_MUNDANO_RATIO = 0.8  # itens mundanos vendem por 80% do valor de compra


def _preco_venda_pc(item_magico):
    """Preço de VENDA (em PC) de um item mágico do catálogo."""
    if not item_magico or item_magico.preco is None:
        return 0
    return int(round(float(item_magico.preco) * 100 * _PRECO_VENDA_RATIO))


def _preco_venda_mundano_pc(custo_str):
    """Preço de VENDA (PC) de um item mundano = 80% do valor de compra. None se sem preço."""
    base = _preco_em_pc(custo_str)
    return int(round(base * _PRECO_VENDA_MUNDANO_RATIO)) if base is not None else None


def _registrar_transacao(personagem, tipo, descricao, delta_pc):
    """Registra um movimento de carteira (chamar DEPOIS de atualizar carteira_pc)."""
    from .models import TbTransacao
    TbTransacao.objects.create(
        id_personagem=personagem, tipo=tipo, descricao=(descricao or '')[:255],
        valor_pc=int(delta_pc), saldo_pc=int(personagem.carteira_pc or 0))

# Proficiência de armadura por classe (padrão D&D 5.5e) — não está nas tags do banco.
_ARMADURA_PROF = {
    'barbaro': ['leve', 'media', 'escudo'], 'bardo': ['leve'],
    'cacador': ['leve', 'media', 'escudo'], 'clerigo': ['leve', 'media', 'escudo'],
    'druida': ['leve', 'media', 'escudo'], 'feiticeiro': [],
    'guerreiro': ['leve', 'media', 'pesada', 'escudo'], 'ladino': ['leve'],
    'mago': [], 'mistico': ['leve'], 'monge': [],
    'paladino': ['leve', 'media', 'pesada', 'escudo'], 'artifice': ['leve', 'media', 'escudo'],
}


def _spell_count_nv1(conj, base, mais2, mais1):
    """Nº de magias de 1º nível: explícito do recurso, ou fórmula mod-de-conjuração + 1 (mín 1)."""
    if conj.get('magias_n') is not None:
        return conj['magias_n']
    ab = _AB_SIG.get(conj.get('ability'), 'INT')
    score = int(base.get(ab, 8)) + (2 if mais2 == ab else 0) + (1 if mais1 == ab else 0)
    return max(1, (score - 10) // 2 + 1)


def _criador_armaduras():
    """Catálogo de armaduras+escudo (TbItemMundano categoria=armadura) com CA estruturada."""
    from .models import TbItemMundano
    out = []
    for a in TbItemMundano.objects.filter(categoria='armadura').exclude(tipo_equip__isnull=True).order_by('ca_base'):
        out.append({'slug': a.slug, 'nome': a.nome, 'ca': a.ca or '', 'tipo_equip': a.tipo_equip,
                    'sub': a.subcategoria or '', 'forca_minima': a.forca_minima,
                    'furtividade': bool(a.furtividade_desvantagem)})
    return out


def _criador_catalogos():
    from .models import (TbRaca, TbLinhagem, TbEssencia, TbClasse, TbAntecedente,
                         TbTalento, TbTracoracial, TbIdioma, TbItemMundano, TbOpcaojogo)
    from .character_engine import _SKILL_INFO
    racas = []
    for r in TbRaca.objects.all().order_by('nome'):
        linhagens = [{'slug': l.slug, 'nome': getattr(l, 'nome', l.slug)}
                     for l in TbLinhagem.objects.filter(id_raca=r).order_by('nome')]
        racas.append({'slug': r.slug, 'nome': r.nome,
                      'permite_essencia': bool(getattr(r, 'permite_essencia', True)),
                      'linhagens': linhagens})
    classes = []
    for c in TbClasse.objects.all().order_by('nome'):
        n, lista = _parse_skills_lvl1(c.tags_json)
        sub = _tag_levels(c.tags_json, 'subclass-choices')
        esc1 = _classe_escolhas_nv1(c)
        classes.append({'slug': c.slug, 'nome': c.nome, 'pericias_n': n, 'pericias_lista': lista,
                        'equipamento': (c.equipamento or '').strip(),
                        'maestria_n': _classe_maestria_n(c, 1),
                        'estilo_n': esc1['estilo_n'], 'expertise_n': esc1['expertise_n'],
                        'expertise_fixa': esc1['expertise_fixa'],
                        'conjuracao': _classe_conjuracao(c),
                        'armaduras_prof': _ARMADURA_PROF.get(c.slug, []),
                        'subclasse_nivel': min(sub) if sub else None})
    def _vertente_de(t):
        # talentos elementais trazem "Vertente Sylph/Oread/Ifrit/Undine" no pré-requisito/descrição
        txt = ((t.pre_requisito or '') + ' ' + (t.descricao or '')).lower()
        m = re.search(r'vertente\s+(ifrit|undine|oread|sylph)', txt)
        return m.group(1) if m else ''

    def _traco_dict(t):
        return {'nome': t.nome, 'pre': (t.pre_requisito or '').strip(),
                'descricao': (t.descricao or '').strip(), 'vertente': _vertente_de(t)}

    # Talentos raciais de nível 1, separados por fonte: raça base, linhagem (sub-raça) e
    # essência. O front mostra os da raça SEMPRE e adiciona os da linhagem/essência selecionadas.
    talentos_raca, talentos_linhagem, talentos_essencia = {}, {}, {}
    for r in TbRaca.objects.all():
        qs = TbTracoracial.objects.filter(id_raca=r, talento_racial=True,
                                          nivel_requisito__lte=1).order_by('nome')
        talentos_raca[r.slug] = [_traco_dict(t) for t in qs]
    for l in TbLinhagem.objects.all():
        qs = TbTracoracial.objects.filter(id_linhagem=l, talento_racial=True,
                                          nivel_requisito__lte=1).order_by('nome')
        if qs:
            talentos_linhagem[l.slug] = [_traco_dict(t) for t in qs]
    for e in TbEssencia.objects.all():
        qs = TbTracoracial.objects.filter(id_essencia=e, talento_racial=True,
                                          nivel_requisito__lte=1).order_by('nome')
        if qs:
            talentos_essencia[e.slug] = [_traco_dict(t) for t in qs]

    # Escolhas de RAÇA automáticas: traços (não-talento) que concedem perícia/idioma/ferramenta
    # extra via tag pick:<tipo>:<n>[ de [lista]] (ex.: humano Habilidoso pick:pericia:2). O front
    # renderiza um seletor por escolha, reativo à raça/linhagem/essência, igual às escolhas de classe.
    _pick_re = re.compile(r'pick:(pericia|idioma|ferramenta):(\d+)(?:\s+de\s+\[([^\]]*)\])?')

    def _racial_picks(qs_traits):
        out = []
        for t in qs_traits:
            for tag in (t.tags_json or []):
                for m in _pick_re.finditer(str(tag)):
                    de = [s.strip() for s in (m.group(3) or '').split(',') if s.strip()]
                    out.append({'tipo': m.group(1), 'n': int(m.group(2)), 'de': de, 'fonte': t.nome})
        return out

    racial_choices_raca, racial_choices_linhagem, racial_choices_essencia = {}, {}, {}
    for r in TbRaca.objects.all():
        p = _racial_picks(TbTracoracial.objects.filter(id_raca=r, nivel_requisito__lte=1).exclude(talento_racial=True))
        if p:
            racial_choices_raca[r.slug] = p
    for l in TbLinhagem.objects.all():
        p = _racial_picks(TbTracoracial.objects.filter(id_linhagem=l, nivel_requisito__lte=1).exclude(talento_racial=True))
        if p:
            racial_choices_linhagem[l.slug] = p
    for e in TbEssencia.objects.all():
        p = _racial_picks(TbTracoracial.objects.filter(id_essencia=e, nivel_requisito__lte=1).exclude(talento_racial=True))
        if p:
            racial_choices_essencia[e.slug] = p
    pericias = sorted(({'slug': sl, 'nome': info[0]} for sl, info in _SKILL_INFO.items()),
                      key=lambda x: x['nome'])
    return {
        'racas': racas,
        'essencias': [{'slug': e.slug, 'nome': e.nome} for e in TbEssencia.objects.all().order_by('nome')],
        'vertentes': [{'slug': 'ifrit', 'nome': 'Ifrit (Fogo)'}, {'slug': 'undine', 'nome': 'Undine (Água)'},
                      {'slug': 'oread', 'nome': 'Oread (Terra)'}, {'slug': 'sylph', 'nome': 'Sylph (Ar)'}],
        'classes': classes,
        'antecedentes': [{'slug': a.slug, 'nome': a.nome} for a in TbAntecedente.objects.all().order_by('nome')],
        'talentos_origem': [{'id': t.id_talento, 'nome': t.nome, 'pre': (t.pre_requisito or '').strip(),
                             'descricao': (t.descricao or '').strip()}
                            for t in TbTalento.objects.filter(tipo__iexact='origem').order_by('nome')],
        'talentos_raca': talentos_raca,
        'talentos_linhagem': talentos_linhagem,
        'talentos_essencia': talentos_essencia,
        'racial_choices_raca': racial_choices_raca,
        'racial_choices_linhagem': racial_choices_linhagem,
        'racial_choices_essencia': racial_choices_essencia,
        'pericias': pericias,
        'idiomas': [{'nome': i.nome, 'desc': (i.categoria or '').strip()}
                    for i in TbIdioma.objects.exclude(nome__iexact='Comum').order_by('categoria', 'ordem', 'nome')],
        'ferramentas': [{'nome': f.nome, 'desc': (f.descricao_markdown or '').strip()}
                        for f in TbItemMundano.objects.filter(categoria='ferramenta').order_by('subcategoria', 'nome')],
        'armas': _criador_armas(),
        'armaduras': _criador_armaduras(),
        'estilos_luta': [{'slug': o.slug, 'nome': o.nome}
                         for o in TbOpcaojogo.objects.filter(tipo='Estilo de Luta').order_by('nome')],
    }


def condicoes_view(request):
    """Página de referência das condições do sistema (TbCondicao). Staff edita inline."""
    from .models import TbCondicao
    from . import permissions as perms
    return render(request, 'home/pages/condicoes.html', {
        'page_title': 'Condições',
        'condicoes': list(TbCondicao.objects.all().order_by('ordem', 'nome')),
        'is_staff': perms.is_staff_user(request.user),
        'msg': request.GET.get('m'),
    })


def _parse_efeitos(texto):
    """Textarea 'Título | texto' por linha → [{titulo, texto}] dos sub-efeitos."""
    out = []
    for linha in (texto or '').splitlines():
        if not linha.strip():
            continue
        partes = [p.strip() for p in linha.split('|', 1)]
        if len(partes) == 2 and partes[0]:
            out.append({'titulo': partes[0], 'texto': partes[1]})
        elif partes[0]:
            out.append({'titulo': '', 'texto': partes[0]})
    return out


def _efeitos_para_texto(efeitos):
    linhas = []
    for e in (efeitos or []):
        if isinstance(e, dict):
            t, x = e.get('titulo', ''), e.get('texto', '')
            linhas.append(('%s | %s' % (t, x)) if t else x)
    return '\n'.join(linhas)


def _condicao_apply(c, g):
    c.nome = (g('nome') or '').strip()
    c.nome_en = (g('nome_en') or '').strip() or None
    c.categoria = g('categoria') or '5e'
    c.resumo = (g('resumo') or '').strip() or None
    c.definicao = (g('definicao') or '').strip() or None
    c.efeitos_json = _parse_efeitos(g('efeitos'))
    try:
        c.ordem = int(g('ordem'))
    except (TypeError, ValueError):
        c.ordem = 0


@login_required(login_url='/login/')
def condicao_criar(request):
    """Staff cria uma condição pelo site."""
    from .models import TbCondicao
    from . import permissions as perms
    if not perms.is_staff_user(request.user):
        raise Http404
    if request.method == 'POST':
        g = request.POST.get
        nome = (g('nome') or '').strip()
        if not nome:
            return redirect(reverse('condicao_criar') + '?e=nome')
        base = (g('slug') or '').strip() or slugify(nome) or 'condicao'
        slug, i = base, 1
        while TbCondicao.objects.filter(slug=slug).exists():
            i += 1
            slug = '%s-%d' % (base, i)
        c = TbCondicao(slug=slug)
        _condicao_apply(c, g)
        c.save()
        return redirect(reverse('mestre_condicoes') + '?m=criada')
    return render(request, 'home/pages/condicao_form.html', {'page_title': 'Nova Condição'})


@login_required(login_url='/login/')
def condicao_editar(request, pk):
    """Staff edita uma condição pelo site."""
    from .models import TbCondicao
    from . import permissions as perms
    if not perms.is_staff_user(request.user):
        raise Http404
    c = TbCondicao.objects.filter(id_condicao=pk).first()
    if not c:
        raise Http404
    if request.method == 'POST':
        g = request.POST.get
        if not (g('nome') or '').strip():
            return redirect(reverse('condicao_editar', args=[pk]) + '?e=nome')
        _condicao_apply(c, g)
        c.save()
        return redirect(reverse('mestre_condicoes') + '?m=editada')
    return render(request, 'home/pages/condicao_form.html', {
        'page_title': 'Editar Condição', 'editar': True, 'condicao_id': c.id_condicao,
        'pf': c, 'efeitos_texto': _efeitos_para_texto(c.efeitos_json)})


@login_required(login_url='/login/')
@require_POST
def condicao_excluir(request, pk):
    """Staff exclui uma condição."""
    from .models import TbCondicao
    from . import permissions as perms
    if perms.is_staff_user(request.user):
        TbCondicao.objects.filter(id_condicao=pk).delete()
    return redirect(reverse('mestre_condicoes') + '?m=excluida')


def glossario_view(request):
    """Glossário de regras gerais (TbRegra) + condições — consultável."""
    from .models import TbRegra, TbCondicao
    return render(request, 'home/pages/glossario.html', {
        'page_title': 'Glossário do Sistema',
        'regras': list(TbRegra.objects.all().order_by('nome')),
        'condicoes': list(TbCondicao.objects.all().order_by('nome')),
    })


def criacao_ficha_view(request):
    """Criação de Ficha — point-buy + identidade + classe + antecedente + talentos."""
    from . import point_buy
    atributos = [('FOR', 'Força'), ('DES', 'Destreza'), ('CON', 'Constituição'),
                 ('INT', 'Inteligência'), ('SAB', 'Sabedoria'), ('CAR', 'Carisma')]
    return render(request, 'home/pages/criacao_ficha.html', {
        'page_title': 'Criação de Ficha',
        'atributos': atributos,
        'pb_custo': json.dumps(point_buy.CUSTO),
        'pb_max_pontos': point_buy.MAX_PONTOS,
        'pb_min': point_buy.MIN_SCORE,
        'pb_max': point_buy.MAX_SCORE,
        'catalogos': _criador_catalogos(),
        'logado': request.user.is_authenticated,
    })


def _personagem_card(p, com_dono=False):
    cl = p.classes.all()
    principal = next((c for c in cl if c.principal), (cl[0] if cl else None))
    card = {
        'obj': p,
        'classe': principal.id_classe.nome if principal else '—',
        'nivel': p.nivel,
        'raca': p.id_raca.nome if p.id_raca_id else '—',
    }
    if com_dono:
        card['dono'] = p.dono.username
    return card


@login_required(login_url='/login/')
def personagens_list_view(request):
    """Página de personagens: fichas ativas + cofre (do usuário); staff vê todas."""
    from .models import TbPersonagem
    from . import permissions as perms

    minhas = list(request.user.personagens.select_related('id_raca')
                  .prefetch_related('classes__id_classe').order_by('-atualizado_em'))
    ativos = [_personagem_card(p) for p in minhas if not p.arquivado]
    cofre = [_personagem_card(p) for p in minhas if p.arquivado]

    ctx = {
        'page_title': 'Meus Personagens',
        'ativos': ativos,
        'cofre': cofre,
        'limite': perms.get_character_limit(request.user),
        'limite_detalhe': perms.limite_detalhe(request.user),
        'slots_usados': len(ativos),
        'pode_criar': perms.pode_criar(request.user),
        'is_staff': perms.is_staff_user(request.user),
    }
    if perms.is_staff_user(request.user):
        outras = (TbPersonagem.objects.exclude(dono=request.user)
                  .select_related('dono', 'id_raca').prefetch_related('classes__id_classe')
                  .order_by('dono__username', '-atualizado_em'))
        ctx['todas'] = [_personagem_card(p, com_dono=True) for p in outras]
    return render(request, 'home/pages/personagens_list.html', ctx)


@login_required(login_url='/login/')
@require_POST
def personagem_arquivar(request, pk):
    from .models import TbPersonagem
    p = get_object_or_404(TbPersonagem, pk=pk, dono=request.user)
    p.arquivado = True
    p.save(update_fields=['arquivado', 'atualizado_em'])
    return redirect('personagens')


@login_required(login_url='/login/')
@require_POST
def personagem_restaurar(request, pk):
    from .models import TbPersonagem
    from . import permissions as perms
    p = get_object_or_404(TbPersonagem, pk=pk, dono=request.user)
    if not perms.pode_criar(request.user):
        return HttpResponseBadRequest('Limite de fichas ativas atingido — arquive outra antes de restaurar esta.')
    p.arquivado = False
    p.save(update_fields=['arquivado', 'atualizado_em'])
    return redirect('personagens')


@login_required(login_url='/login/')
@require_POST
def personagem_excluir(request, pk):
    from .models import TbPersonagem
    p = get_object_or_404(TbPersonagem, pk=pk, dono=request.user)
    p.delete()
    return redirect('personagens')


def _ficha_editavel(request, pk):
    """Busca o personagem se o usuário pode editá-lo (dono ou staff)."""
    from .models import TbPersonagem
    from . import permissions as perms
    p = get_object_or_404(TbPersonagem, pk=pk)
    if p.dono_id != request.user.id and not perms.is_staff_user(request.user):
        raise Http404('Sem permissão para editar esta ficha.')
    return p


def _pendencias_nivel(personagem):
    """Escolhas que faltam no nível atual: subclasse (N>=nível-da-subclasse) e ASIs."""
    from .models import TbSubclasse
    pend = {'subclasse': False, 'asi_pendentes': 0, 'subclasse_nivel': None, 'subclasses': []}
    pc = personagem.classes.filter(principal=True).first() or personagem.classes.first()
    if not pc:
        return pend
    nivel = pc.nivel or 1
    classe = pc.id_classe
    sub_lv = _tag_levels(classe.tags_json, 'subclass-choices')
    pend['subclasse_nivel'] = min(sub_lv) if sub_lv else 3
    if nivel >= pend['subclasse_nivel'] and not pc.id_subclasse_id:
        pend['subclasse'] = True
        pend['subclasses'] = [{'id': s.id_subclasse, 'nome': s.nome}
                              for s in TbSubclasse.objects.filter(id_classe=classe).order_by('nome')]
    asi_levels = [l for l in _tag_levels(classe.tags_json, 'asi-choices') if l <= nivel]
    aplicados = (personagem.atributo_bonus.filter(origem_tipo='asi-classe').count() // 2
                 + personagem.talentos.filter(categoria='asi-nivel').count())
    pend['asi_pendentes'] = max(0, len(asi_levels) - aplicados)
    return pend


# Tiers de TALENTO RACIAL (raça/linhagem/essência): um talento por nível-marco.
_TIERS_TALENTO_RACIAL = (1, 5, 9, 13, 17)


def _pendencias_talento_racial(personagem):
    """Talentos raciais a escolher por nível-marco (1/5/9/13/17). O de nv1 é pego na
    criação; os demais aqui. Opções = traços `talento_racial=True` com nivel_requisito ==
    tier, vindos da raça, linhagem OU essência do personagem (mesmo pool do criador), menos
    os já escolhidos. Retorna [{nivel, opcoes:[{nome,descricao,pre}]}] só p/ tiers em aberto."""
    from .models import TbTracoracial
    from django.db.models import Q
    total = sum(c.nivel or 0 for c in personagem.classes.all()) or (personagem.nivel or 1)
    cond = Q()
    if personagem.id_raca_id:
        cond |= Q(id_raca=personagem.id_raca_id)
    if getattr(personagem, 'id_linhagem_id', None):
        cond |= Q(id_linhagem=personagem.id_linhagem_id)
    if getattr(personagem, 'id_essencia_id', None):
        cond |= Q(id_essencia=personagem.id_essencia_id)
    if not cond.children:
        return []
    picked = personagem.talentos.filter(categoria='racial')
    picked_nomes = set(picked.values_list('nome', flat=True))
    picked_tiers = set(picked.values_list('nivel', flat=True))
    out = []
    for tier in _TIERS_TALENTO_RACIAL:
        if tier > total or tier in picked_tiers:
            continue
        opcoes = [o for o in TbTracoracial.objects.filter(cond, talento_racial=True,
                                                          nivel_requisito=tier).order_by('nome')
                  if o.nome not in picked_nomes]
        if opcoes:
            out.append({'nivel': tier, 'opcoes': [
                {'nome': o.nome, 'descricao': (o.descricao or '').strip(),
                 'pre': (o.pre_requisito or '').strip()} for o in opcoes]})
    return out


# pick:opcao:<slug>(<mod>):<count>  — count = {progressão} | inteiro | N | +
_PICK_OPCAO_RE = re.compile(r'pick:opcao:([a-z0-9-]+)(?:\([^)]*\))?(?::(\{[^}]*\}|\d+|N|\+))?')


def _pick_count_expr(expr, level):
    """Conta de um pick:opcao. Literal '2'→2; progressão '{classlvl=X:n,...}'→SOMA
    cumulativa dos n com limiar<=level (semântica de 'conhecidas'). 'N'/'+'/vazio→None
    (a conta vem de um recurso de tabela)."""
    expr = (expr or '').strip()
    if expr.startswith('{'):
        return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*(\d+)', expr)
                   if int(lv) <= level)
    if expr.isdigit():
        return int(expr)
    return None


def _opcao_grupos(personagem):
    """Grupos de escolha de OPÇÕES de classe de nível alto (metamagia, manobras, segredos
    místicos/de caçador, infusões, estilos de ki, técnicas de furtividade, estilo de luta):
    lê `pick:opcao:<slug>:N` das habilidades de classe/subclasse até o nível atual, calcula
    o limite (recurso de tabela ou expressão), lista as opções acessíveis (TbAcessoopcao) e
    as já escolhidas. As escolhas vivem em TbPersonagemEscolha (tipo=<slug>)."""
    from .models import TbClassehabilidade, TbOpcaojogo, TbAcessoopcao, TbRecursoclasse
    from .character_engine import _resource_max_at
    from django.utils.text import slugify
    from django.db.models import Q
    grupos = []
    if personagem is None:
        return grupos
    slug2tipo = {slugify(t): t for t in TbOpcaojogo.objects.values_list('tipo', flat=True).distinct() if t}
    escolhidas = {}
    for e in personagem.escolhas.select_related('id_opcao').all():
        escolhidas.setdefault(e.tipo, []).append(e)
    vistos = set()
    for c in personagem.classes.select_related('id_classe', 'id_subclasse'):
        nivel = int(c.nivel or 0)
        classe = c.id_classe
        habs = list(TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido__lte=nivel))
        if c.id_subclasse_id and nivel >= 3:
            habs += list(TbClassehabilidade.objects.filter(
                id_subclasse=c.id_subclasse, niveladquirido__lte=nivel))
        picks = {}
        for h in habs:
            for t in (h.tags_json or []):
                t = str(t)
                for m in _PICK_OPCAO_RE.finditer(t):
                    slug, expr = m.group(1), m.group(2)
                    d = picks.setdefault(slug, {'exprs': set(), 'resource': None})
                    rm = re.search(r'=resource\s+([a-z0-9-]+)', t)
                    if rm:
                        d['resource'] = rm.group(1)
                    if expr and expr not in ('N', '+'):
                        d['exprs'].add(expr)
        for slug, d in picks.items():
            if (classe.id_classe, slug) in vistos:
                continue
            vistos.add((classe.id_classe, slug))
            limite = None
            if d['resource']:
                r = (TbRecursoclasse.objects.filter(id_classe=classe, slug=d['resource']).first()
                     or TbRecursoclasse.objects.filter(id_classe=classe, slug__icontains=d['resource']).first())
                if r:
                    limite = _resource_max_at(r, nivel)
            if limite is None and d['exprs']:
                soma = sum(v for v in (_pick_count_expr(ex, nivel) for ex in d['exprs']) if v is not None)
                limite = soma or None
            if not limite or limite <= 0:
                continue
            tipo_disp = slug2tipo.get(slug)
            if not tipo_disp:
                continue
            acc = TbAcessoopcao.objects.filter(nivel_recebimento__lte=nivel).filter(
                Q(id_classe=classe) | (Q(id_subclasse=c.id_subclasse) if c.id_subclasse_id else Q(pk__in=[])))
            acc_ids = set(acc.values_list('id_opcao_id', flat=True))
            qs = TbOpcaojogo.objects.filter(tipo=tipo_disp)
            if acc_ids:
                qs = qs.filter(id_opcao__in=acc_ids)
            escs = sorted(escolhidas.get(slug, []), key=lambda e: e.slot)
            esc_ids = {e.id_opcao_id for e in escs if e.id_opcao_id}
            esc_slugs = {e.valor for e in escs if e.valor}
            disponiveis = [{'id': o.id_opcao, 'nome': o.nome, 'descricao': o.descricao or '',
                            'pre': o.pre_requisito or ''}
                           for o in qs.order_by('nome')
                           if o.id_opcao not in esc_ids and o.slug not in esc_slugs]
            grupos.append({
                'classe_id': classe.id_classe, 'classe': classe.nome, 'slug': slug,
                'tipo': tipo_disp, 'limite': limite, 'usados': len(escs),
                'pendentes': max(0, limite - len(escs)),
                'prox_slot': max([e.slot for e in escs], default=-1) + 1,
                'escolhidas': [{'id': e.id, 'nome': (e.id_opcao.nome if e.id_opcao_id else e.valor)}
                               for e in escs],
                'disponiveis': disponiveis,
            })
    grupos.sort(key=lambda g: (g['pendentes'] == 0, g['classe'], g['tipo']))
    return grupos


@login_required(login_url='/login/')
def editar_ficha_view(request, pk):
    """Edição/level-up de uma ficha: subir de nível e completar as escolhas pendentes."""
    from .character_engine import derive
    from . import point_buy
    from . import permissions as perms_mod
    p = _ficha_editavel(request, pk)
    pc = p.classes.filter(principal=True).first() or p.classes.first()
    ficha = derive(p)
    pend = _pendencias_nivel(p)
    pendm = _pendencias_magias(p)
    talentos_raciais_pend = _pendencias_talento_racial(p)
    talentos = []
    from .models import TbTalento, TbItemMundano
    for t in TbTalento.objects.filter(tipo__iexact='origem').order_by('nome'):
        talentos.append({'id': t.id_talento, 'nome': t.nome})
    # mercado: itens mundanos compráveis (com preço parseável) agrupados por categoria
    cat_label = dict(TbItemMundano.CATEGORIA_CHOICES)
    grupos = {}
    for it in TbItemMundano.objects.order_by('categoria', 'nome'):
        if _preco_em_pc(it.preco) is None:
            continue
        grupos.setdefault(cat_label.get(it.categoria, it.categoria), []).append(
            {'slug': it.slug, 'nome': it.nome, 'preco': it.preco})
    itens_compra = [{'categoria': k, 'itens': v} for k, v in sorted(grupos.items())]
    # mercado: itens mágicos compráveis (com preço) agrupados por raridade
    from .models import TbItemMagico
    rar_label = dict(TbItemMagico.RARIDADE_CHOICES)
    grupos_mag = {}
    for it in TbItemMagico.objects.exclude(preco__isnull=True).order_by('raridade', 'nome'):
        grupos_mag.setdefault(rar_label.get(it.raridade, it.raridade), []).append(
            {'slug': it.slug, 'nome': it.nome, 'preco': '%g PO' % float(it.preco),
             'requer_sintonizacao': it.requer_sintonizacao})
    itens_magicos_compra = [{'raridade': k, 'itens': v} for k, v in grupos_mag.items()]
    sintonizados_usados = p.inventario.filter(sintonizado=True).count()
    from .character_engine import _recursos_consumiveis
    recursos_consumiveis = _recursos_consumiveis(p, list(p.classes.select_related('id_classe', 'id_subclasse')))
    magias_preparadas = _magias_preparadas_info(p, ficha)
    # preço de venda (80%) dos itens mundanos com custo parseável
    for it in ficha.get('inventario', []):
        if not it.get('magico'):
            v = _preco_venda_mundano_pc(it.get('custo'))
            if v:
                it['venda_pc'], it['venda_display'] = v, _pc_display(v)
    transacoes = list(p.transacoes.all()[:30])
    opcao_grupos = _opcao_grupos(p)
    classes_atuais = [{'id': c.id_classe.id_classe, 'nome': c.id_classe.nome, 'nivel': c.nivel,
                       'principal': c.principal} for c in p.classes.select_related('id_classe').order_by('-principal', 'id')]
    classes_multiclasse = _classes_multiclasse(p, ficha) if (p.nivel or 0) < 20 else []
    return render(request, 'home/pages/editar_ficha.html', {
        'page_title': 'Editar — %s' % p.nome,
        'p': p, 'pc': pc, 'ficha': ficha,
        'nivel': pc.nivel if pc else 1,
        'pend': pend, 'pend_magias': pendm,
        'talentos_raciais_pend': talentos_raciais_pend,
        'opcao_grupos': opcao_grupos,
        'sem_pendencias': not (pend['subclasse'] or pend['asi_pendentes']
                               or (pendm and (pendm['cantrips_pend'] or pendm['known_pend']))
                               or talentos_raciais_pend
                               or any(g['pendentes'] for g in opcao_grupos)),
        'atributos': point_buy.SIGLAS,
        'talentos_normais': talentos,
        'carteira_display': _pc_display(p.carteira_pc),
        'itens_compra': itens_compra,
        'itens_magicos_compra': itens_magicos_compra,
        'sintonizados_usados': sintonizados_usados,
        'recursos_consumiveis': recursos_consumiveis,
        'magias_preparadas': magias_preparadas,
        'transacoes': transacoes,
        'is_staff': perms_mod.is_staff_user(request.user),
        'classes_atuais': classes_atuais,
        'classes_multiclasse': classes_multiclasse,
        'compra_msg': request.GET.get('compra'),
    })


@login_required(login_url='/login/')
@require_POST
def personagem_subir_nivel(request, pk):
    from .character_engine import nivel_por_aventuras
    p = _ficha_editavel(request, pk)
    if (p.nivel or 0) >= 20:
        return redirect('editar_ficha', pk=pk)
    # nº de aventuras define o nível-TETO (não passa do que as aventuras permitem)
    teto = min(nivel_por_aventuras(p.aventuras), 20)
    if (p.nivel or 0) >= teto:
        return redirect(reverse('editar_ficha', args=[pk]) + '?nivel=teto')
    cid = request.POST.get('classe')
    pc = (p.classes.filter(id_classe_id=cid).first() if cid else None) \
        or p.classes.filter(principal=True).first() or p.classes.first()
    if pc and (pc.nivel or 1) < 20:
        pc.nivel = (pc.nivel or 1) + 1
        pc.save(update_fields=['nivel'])
        p.nivel = sum(c.nivel or 0 for c in p.classes.all())
        p.save(update_fields=['nivel', 'atualizado_em'])
        # Novos níveis podem desbloquear ciclos de Magia Elemental (nv 5/9/13).
        _sync_magias_essencia(p)
    return redirect('editar_ficha', pk=pk)


def aplicar_aventuras(personagem, n, evento=False):
    """Aplica `n` aventuras a um personagem (lançado por staff). Regra de SPLIT no rank-up:
    cada aventura é recompensada no rank ANTES de ela contar (a que sobe de rank paga no
    rank antigo; as seguintes no novo). Sempre credita o ouro do rank (PO→PC). BRASEIROS
    (= BP) só em missão de EVENTO (`evento=True`) — jogar evento dá braseiros; aventura
    normal, não. Retorna (ouro_po, braseiros)."""
    from .character_engine import nivel_por_aventuras, ouro_por_aventura, braseiros_por_aventura
    n = max(0, int(n))
    if n == 0:
        return (0, 0)
    base = int(personagem.aventuras or 0)
    ouro = bras = 0
    for k in range(n):
        nivel = nivel_por_aventuras(base + k)
        ouro += ouro_por_aventura(nivel)
        if evento:
            bras += braseiros_por_aventura(nivel)
    personagem.aventuras = base + n
    personagem.braseiros = int(personagem.braseiros or 0) + bras
    personagem.carteira_pc = int(personagem.carteira_pc or 0) + ouro * 100
    personagem.save(update_fields=['aventuras', 'braseiros', 'carteira_pc', 'atualizado_em'])
    desc = '%d aventura(s)%s' % (n, (' de evento — +%d braseiros' % bras) if evento else '')
    _registrar_transacao(personagem, 'aventura', desc, ouro * 100)
    return (ouro, bras)


def _sync_magias_concedidas(personagem):
    """Materializa em TbPersonagemMagia TODAS as magias específicas concedidas por features
    ativas (Essência/vertente, Marcas, Juramento das Três Luas, domínios/juramentos de
    classe etc.) — via `character_engine.magias_concedidas`. As concedidas ficam marcadas
    `sempre_preparada=True` com origem = nome da feature; esse flag é o que identifica os
    registros geridos aqui. Idempotente: cria as que faltam, atualiza nome/origem/nível e
    remove as que deixaram de valer (troca de vertente/talento perdido). Retorna o nº de
    escolhas de magia ainda pendentes (p/ a ficha pedir a seleção)."""
    from .models import TbMagia, TbPersonagemMagia
    from .character_engine import magias_concedidas
    info = magias_concedidas(personagem)
    intended = {c['slug']: c for c in info['concedidas']}
    existing = {}
    for m in (TbPersonagemMagia.objects.filter(id_personagem=personagem, sempre_preparada=True)
              .select_related('id_magia')):
        if m.id_magia_id and m.id_magia.slug:
            existing[m.id_magia.slug] = m
    for slug, c in intended.items():
        m = existing.get(slug)
        if m:
            campos = []
            if m.id_magia and m.nome != m.id_magia.nome:
                m.nome = m.id_magia.nome; campos.append('nome')
            if m.origem != c['fonte']:
                m.origem = c['fonte']; campos.append('origem')
            if m.nivel != c['nivel']:
                m.nivel = c['nivel']; campos.append('nivel')
            if campos:
                m.save(update_fields=campos)
            continue
        mg = TbMagia.objects.filter(slug=slug).first()
        if mg:
            TbPersonagemMagia.objects.create(
                id_personagem=personagem, id_magia=mg, nivel=c['nivel'], nome=mg.nome,
                preparada=True, sempre_preparada=True, origem=c['fonte'])
    for slug, m in existing.items():
        if slug not in intended:
            m.delete()
    return len(info['pendentes'])


# compat: nome antigo
_sync_magias_essencia = _sync_magias_concedidas


@login_required(login_url='/login/')
@require_POST
def personagem_registrar_aventuras(request, pk):
    """Staff lança N aventuras num personagem → ouro (por rank) + nível-teto, e braseiros
    (BP) se for missão de EVENTO."""
    from . import permissions as perms
    if not perms.is_staff_user(request.user):
        raise Http404
    p = _ficha_editavel(request, pk)
    try:
        n = max(1, min(200, int(request.POST.get('aventuras') or 1)))
    except (TypeError, ValueError):
        n = 1
    aplicar_aventuras(p, n, evento=(request.POST.get('evento') == 'on'))
    return redirect(reverse('editar_ficha', args=[pk]) + '?compra=aventuras')


# aceita siglas EN e PT (as tags do banco misturam: 'cha' e 'car', etc.)
_MC_ATTR = {'str': 'FOR', 'for': 'FOR', 'dex': 'DES', 'des': 'DES', 'con': 'CON',
            'int': 'INT', 'wis': 'SAB', 'sab': 'SAB', 'cha': 'CAR', 'car': 'CAR'}


def _multiclass_atende(atributos, req):
    """Pré-requisito de multiclasse: ',' = E (todas), '|' = OU. Atom: attr>=N."""
    if not req:
        return True
    for clausula in req.strip().strip('{}').split(','):     # E
        atoms = re.findall(r'(str|for|dex|des|con|int|wis|sab|cha|car)\s*>=\s*(\d+)', clausula)
        if not atoms:
            continue                                        # cláusula sem atom reconhecível: não bloqueia
        if not any(atributos.get(_MC_ATTR[a], {}).get('valor', 0) >= int(n) for a, n in atoms):
            return False                                    # nenhum atom da cláusula (OU) atendido
    return True


def _classe_req(cl):
    for t in (cl.tags_json or []):
        m = re.search(r'multiclass-req\{([^}]*)\}', str(t))
        if m:
            return m.group(1)
    return None


def _classes_multiclasse(p, ficha):
    """Classes que o personagem pode adicionar por multiclasse (pré-req atendido, não-possuída)."""
    from .models import TbClasse
    atuais = set(p.classes.values_list('id_classe_id', flat=True))
    out = []
    for cl in TbClasse.objects.all().order_by('nome'):
        if cl.id_classe in atuais:
            continue
        req = _classe_req(cl)
        if _multiclass_atende(ficha['atributos'], req):
            out.append({'id': cl.id_classe, 'nome': cl.nome, 'req': (req or '').strip('{}')})
    return out


@login_required(login_url='/login/')
@require_POST
def personagem_adicionar_classe(request, pk):
    """Adiciona uma classe por multiclasse (nível 1), se o pré-requisito for atendido.
    A 1ª classe (principal) permanece a referência de PV/saves/perícias/equipamento iniciais."""
    from .models import TbClasse, TbPersonagemClasse
    from .character_engine import derive
    p = _ficha_editavel(request, pk)
    if (p.nivel or 0) >= 20:
        return redirect(reverse('editar_ficha', args=[pk]) + '?mc=max')
    cl = TbClasse.objects.filter(id_classe=request.POST.get('classe')).first()
    if not cl or p.classes.filter(id_classe=cl).exists():
        return redirect(reverse('editar_ficha', args=[pk]) + '?mc=invalido')
    if not _multiclass_atende(derive(p)['atributos'], _classe_req(cl)):
        return redirect(reverse('editar_ficha', args=[pk]) + '?mc=prereq')
    TbPersonagemClasse.objects.create(id_personagem=p, id_classe=cl, nivel=1, principal=False)
    p.nivel = sum(c.nivel or 0 for c in p.classes.all())
    p.save(update_fields=['nivel', 'atualizado_em'])
    return redirect(reverse('editar_ficha', args=[pk]) + '?mc=ok')


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_subclasse(request, pk):
    from .models import TbSubclasse
    p = _ficha_editavel(request, pk)
    pc = p.classes.filter(principal=True).first() or p.classes.first()
    sub = TbSubclasse.objects.filter(id_subclasse=request.POST.get('subclasse'), id_classe=pc.id_classe).first()
    if pc and sub and not pc.id_subclasse_id:
        pc.id_subclasse = sub
        pc.save(update_fields=['id_subclasse'])
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_aplicar_asi(request, pk):
    from .models import TbPersonagemAtributoBonus, TbPersonagemTalento, TbTalento
    from . import point_buy
    p = _ficha_editavel(request, pk)
    pc = p.classes.filter(principal=True).first() or p.classes.first()
    nivel = pc.nivel if pc else 1
    if _pendencias_nivel(p)['asi_pendentes'] < 1:
        return redirect('editar_ficha', pk=pk)
    if request.POST.get('tipo') == 'talento':
        t = TbTalento.objects.filter(id_talento=request.POST.get('talento')).first()
        if t:
            TbPersonagemTalento.objects.create(id_personagem=p, id_talento=t, categoria='asi-nivel',
                                               nivel=nivel, nome=t.nome)
    else:
        mais2, mais1 = request.POST.get('mais2'), request.POST.get('mais1')
        ok, _e = point_buy.validar_asi(mais2, mais1)
        if ok:
            TbPersonagemAtributoBonus.objects.create(id_personagem=p, atributo=mais2, valor=2,
                                                     origem='ASI N%d' % nivel, origem_tipo='asi-classe')
            TbPersonagemAtributoBonus.objects.create(id_personagem=p, atributo=mais1, valor=1,
                                                     origem='ASI N%d' % nivel, origem_tipo='asi-classe')
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_talento_racial(request, pk):
    """Escolhe um TALENTO RACIAL de nível-marco (5/9/13/17) do pool raça/linhagem/essência.
    Valida contra `_pendencias_talento_racial`, grava TbPersonagemTalento (categoria='racial')
    e ressincroniza as magias da Essência (caso o talento conceda magias, ex.: Magia
    Elemental Aprimorada)."""
    from .models import TbPersonagemTalento
    p = _ficha_editavel(request, pk)
    try:
        nivel = int(request.POST.get('nivel') or 0)
    except (TypeError, ValueError):
        nivel = 0
    nome = (request.POST.get('talento') or '').strip()
    bloco = next((b for b in _pendencias_talento_racial(p) if b['nivel'] == nivel), None)
    if bloco and any(o['nome'] == nome for o in bloco['opcoes']):
        TbPersonagemTalento.objects.create(id_personagem=p, categoria='racial', nivel=nivel, nome=nome)
        _sync_magias_essencia(p)
    return redirect(reverse('editar_ficha', args=[pk]) + '#talentos-raciais')


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_opcoes(request, pk):
    """Adiciona/remove uma OPÇÃO de classe (metamagia, manobra, segredo, estilo de luta…).
    Valida contra os grupos derivados (limite + lista de acessíveis)."""
    from .models import TbPersonagemEscolha, TbOpcaojogo
    p = _ficha_editavel(request, pk)
    destino = reverse('editar_ficha', args=[pk]) + '#opcoes'
    if request.POST.get('acao') == 'remover':
        TbPersonagemEscolha.objects.filter(id=request.POST.get('escolha'), id_personagem=p).delete()
        return redirect(destino)
    slug = (request.POST.get('slug') or '').strip()
    op = TbOpcaojogo.objects.filter(id_opcao=request.POST.get('opcao')).first()
    if not (slug and op):
        return redirect(destino)
    grupo = next((g for g in _opcao_grupos(p)
                  if g['slug'] == slug and str(g['classe_id']) == str(request.POST.get('classe'))), None)
    if not grupo or grupo['pendentes'] < 1:
        return redirect(destino)
    if op.id_opcao not in {d['id'] for d in grupo['disponiveis']}:
        return redirect(destino)
    TbPersonagemEscolha.objects.update_or_create(
        id_personagem=p, origem='%s: %s' % (grupo['classe'], grupo['tipo']),
        tipo=slug, slot=grupo['prox_slot'], defaults={'id_opcao': op, 'valor': op.slug})
    return redirect(destino)


def _pendencias_magias(personagem):
    """Magias a aprender no nível atual: truques (todos casters) e magias conhecidas
    (só known casters, com recurso 'Magias Conhecidas'), até o nível máximo conjurável."""
    from .models import TbMagia, TbRecursoclasse, TbClassehabilidade
    pc = personagem.classes.filter(principal=True).first() or personagem.classes.first()
    if not pc:
        return None
    classe, nivel = pc.id_classe, (pc.nivel or 1)
    if not _classe_conjuracao(classe):
        return None

    def res_at(substrs):
        for r in TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True):
            if any(s in (r.slug or '').lower() for s in substrs):
                vj = r.valores_json or {}
                ks = sorted(int(k) for k in vj if int(k) <= nivel)
                if ks:
                    try:
                        return int(str(vj[str(ks[-1])]).strip())
                    except (ValueError, TypeError):
                        pass
        return None

    frac = 'full'
    for src in [classe] + list(TbClassehabilidade.objects.filter(id_classe=classe, id_subclasse__isnull=True, niveladquirido=1)):
        for t in (getattr(src, 'tags_json', None) or []):
            if 'slots:half' in str(t):
                frac = 'half'
    maxlv = min(5, (nivel + 5) // 4) if frac == 'half' else min(9, (nivel + 1) // 2)
    conhecidos = set(personagem.magias.values_list('id_magia__slug', flat=True))
    truques_exp = res_at(['truque']) or 0
    known_exp = res_at(['magias-conhecidas'])
    cant_pend = max(0, truques_exp - personagem.magias.filter(nivel=0).count())
    known_pend = max(0, (known_exp - personagem.magias.filter(nivel__gte=1).count())) if known_exp is not None else 0
    lt = [{'slug': m.slug, 'nome': m.nome} for m in
          TbMagia.objects.filter(nivel=0, classes__icontains=classe.nome).order_by('nome') if m.slug not in conhecidos]
    lm = [{'slug': m.slug, 'nome': m.nome, 'nivel': m.nivel} for m in
          TbMagia.objects.filter(nivel__gte=1, nivel__lte=maxlv, classes__icontains=classe.nome).order_by('nivel', 'nome') if m.slug not in conhecidos]
    swap_lvl = any('swap:level-up' in str(t) for h in TbClassehabilidade.objects.filter(id_classe=classe, id_subclasse__isnull=True) for t in (h.tags_json or []))
    conhecidas = [{'slug': m.id_magia.slug, 'nome': m.nome, 'nivel': m.nivel}
                  for m in personagem.magias.select_related('id_magia').filter(id_magia__isnull=False).order_by('nivel', 'nome')]
    return {'cantrips_pend': cant_pend, 'known_pend': known_pend, 'max_nivel': maxlv,
            'lista_truques': lt, 'lista_magias': lm, 'swap_level_up': swap_lvl, 'conhecidas': conhecidas}


_ABIL_EN = {'FOR': 'str', 'DES': 'dex', 'CON': 'con', 'INT': 'int', 'SAB': 'wis', 'CAR': 'cha'}


def _magias_preparadas_info(personagem, ficha):
    """Conjuradores PREPARADOS (prepara:preparadas + prep-limite): limite calculado da
    fórmula, lista de magias da classe (nv1..máx) e set preparado atual. None se não-preparado."""
    from .models import TbMagia, TbClassehabilidade
    from .character_engine import _eval_formula
    pc = personagem.classes.filter(principal=True).first() or personagem.classes.first()
    if not pc:
        return None
    classe, nivel = pc.id_classe, (pc.nivel or 1)
    sc = None
    for src in [classe] + list(TbClassehabilidade.objects.filter(id_classe=classe, id_subclasse__isnull=True)):
        for t in (getattr(src, 'tags_json', None) or []):
            mm = re.search(r'spellcasting\{([^}]*)\}', str(t))
            if mm:
                sc = mm.group(1)
    if not sc or 'prepara:preparadas' not in sc:
        return None
    mf = re.search(r'prep-limite:([^,}]+)', sc)
    if not mf:
        return None
    ats = ficha['atributos']
    ctx = {'classlvl': nivel, 'lvl': ficha['nivel_total'], 'pb': ficha['bonus_proficiencia']}
    for sig, en in _ABIL_EN.items():
        ctx[en + '-mod'] = ats[sig]['mod']
    abil = (re.search(r'ability:([\w|]+)', sc) or [None, 'int'])[1]
    ctx['spell-mod'] = (max(ctx[a + '-mod'] for a in abil.split('|')) if '|' in abil
                        else ctx.get(abil + '-mod', 0))
    limite = _eval_formula(mf.group(1).strip(), ctx)
    limite = max(1, limite) if limite is not None else None
    maxlv = min(5, (nivel + 5) // 4) if 'slots:half' in sc else min(9, (nivel + 1) // 2)
    preparadas = set(personagem.magias.filter(nivel__gte=1, preparada=True)
                     .values_list('id_magia__slug', flat=True))
    por_nivel = {}
    for m in TbMagia.objects.filter(nivel__gte=1, nivel__lte=maxlv,
                                    classes__icontains=classe.nome).order_by('nivel', 'nome'):
        por_nivel.setdefault(m.nivel, []).append(
            {'slug': m.slug, 'nome': m.nome, 'marcada': m.slug in preparadas})
    grupos = [{'nivel': nv, 'magias': por_nivel[nv]} for nv in sorted(por_nivel)]
    return {'classe': classe.nome, 'ability': abil, 'limite': limite, 'max_nivel': maxlv,
            'grupos': grupos, 'preparadas_count': len(preparadas)}


@login_required(login_url='/login/')
@require_POST
def personagem_aprender_magias(request, pk):
    from .models import TbMagia, TbPersonagemMagia
    p = _ficha_editavel(request, pk)
    pend = _pendencias_magias(p)
    if not pend:
        return redirect('editar_ficha', pk=pk)
    classe = (p.classes.filter(principal=True).first() or p.classes.first()).id_classe
    tslugs = {m['slug'] for m in pend['lista_truques']}
    mslugs = {m['slug'] for m in pend['lista_magias']}
    novos_t = [s for s in dict.fromkeys(request.POST.getlist('truques')) if s in tslugs][:pend['cantrips_pend']]
    novos_m = [s for s in dict.fromkeys(request.POST.getlist('magias')) if s in mslugs][:pend['known_pend']]
    for slug in novos_t + novos_m:
        mg = TbMagia.objects.filter(slug=slug).first()
        if mg:
            TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=mg.nivel,
                                             nome=mg.nome, preparada=True, origem=classe.nome)
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_trocar_magia(request, pk):
    """Troca 1 magia CONHECIDA por outra ao subir de nível (tag swap:level-up).
    Truque↔truque, conhecida↔conhecida (nível 1..máx conjurável)."""
    from .models import TbMagia, TbPersonagemMagia
    p = _ficha_editavel(request, pk)
    pend = _pendencias_magias(p)
    if not pend or not pend['swap_level_up']:
        return redirect('editar_ficha', pk=pk)
    classe = (p.classes.filter(principal=True).first() or p.classes.first()).id_classe
    conhecidas = {m['slug'] for m in pend['conhecidas']}
    old = p.magias.select_related('id_magia').filter(id_magia__slug=request.POST.get('remover')).first()
    new_mg = TbMagia.objects.filter(slug=request.POST.get('adicionar'), classes__icontains=classe.nome).first()
    if (old and new_mg and new_mg.slug not in conhecidas
            and (old.nivel == 0) == (new_mg.nivel == 0)        # truque↔truque
            and new_mg.nivel <= pend['max_nivel']):
        old.delete()
        TbPersonagemMagia.objects.create(id_personagem=p, id_magia=new_mg, nivel=new_mg.nivel,
                                         nome=new_mg.nome, preparada=True, origem=classe.nome)
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_comprar_item(request, pk):
    """Compra um item mundano: debita a carteira (PC) e adiciona ao inventário."""
    from .models import TbItemMundano, TbPersonagemItem
    p = _ficha_editavel(request, pk)
    item = TbItemMundano.objects.filter(slug=request.POST.get('item')).first()
    try:
        qtd = max(1, min(99, int(request.POST.get('qtd') or 1)))
    except (TypeError, ValueError):
        qtd = 1
    custo_unit = _preco_em_pc(item.preco) if item else None
    if not item or custo_unit is None:
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=invalido')
    total = custo_unit * qtd
    if total > (p.carteira_pc or 0):
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=saldo')
    with transaction.atomic():
        p.carteira_pc = (p.carteira_pc or 0) - total
        p.save(update_fields=['carteira_pc', 'atualizado_em'])
        existente = TbPersonagemItem.objects.filter(id_personagem=p, nome=item.nome, equipado=False).first()
        if existente and not item.tipo_equip:
            existente.qtd = (existente.qtd or 0) + qtd
            existente.save(update_fields=['qtd'])
        else:
            TbPersonagemItem.objects.create(id_personagem=p, qtd=qtd, nome=item.nome, custo=item.preco,
                tipo_equip=item.tipo_equip, ca_base=item.ca_base, ca_limite_des=item.ca_limite_des)
        _registrar_transacao(p, 'compra', 'Compra: %s x%d' % (item.nome, qtd), -total)
    return redirect(reverse('editar_ficha', args=[pk]) + '?compra=ok')


@login_required(login_url='/login/')
@require_POST
def personagem_equipar_item(request, pk):
    """Equipa/desequipa um item. Item possuído mas não equipado NÃO concede benefícios.
    Só 1 armadura e 1 escudo equipados por vez."""
    from .models import TbPersonagemItem
    p = _ficha_editavel(request, pk)
    it = TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p).first()
    if not it:
        return redirect('editar_ficha', pk=pk)
    novo = not it.equipado
    if novo and it.tipo_equip:  # equipar: tira o que ocupa o mesmo "slot"
        if it.tipo_equip == 'escudo':
            TbPersonagemItem.objects.filter(id_personagem=p, tipo_equip='escudo', equipado=True).update(equipado=False)
        elif it.tipo_equip.startswith('armadura'):
            TbPersonagemItem.objects.filter(id_personagem=p, equipado=True,
                                            tipo_equip__startswith='armadura').update(equipado=False)
    it.equipado = novo
    it.save(update_fields=['equipado'])
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_vender_item(request, pk):
    """Vende um item MUNDANO do inventário por 80% do valor. Item mágico vai pro
    Mercado da Comunidade (50%), não por aqui."""
    from .models import TbPersonagemItem
    p = _ficha_editavel(request, pk)
    it = TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p).first()
    if not it:
        return redirect('editar_ficha', pk=pk)
    if it.id_item_magico_id:
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=magico_venda')
    unit = _preco_venda_mundano_pc(it.custo)
    if unit is None:
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=sem_preco')
    try:
        qtd = max(1, min(int(it.qtd or 1), int(request.POST.get('qtd') or 1)))
    except (TypeError, ValueError):
        qtd = 1
    credito = unit * qtd
    with transaction.atomic():
        p.carteira_pc = (p.carteira_pc or 0) + credito
        p.save(update_fields=['carteira_pc', 'atualizado_em'])
        nome = it.nome
        if (it.qtd or 1) > qtd:
            it.qtd = it.qtd - qtd
            it.save(update_fields=['qtd'])
        else:
            it.delete()
        _registrar_transacao(p, 'venda', 'Venda: %s x%d' % (nome, qtd), credito)
    return redirect(reverse('editar_ficha', args=[pk]) + '?compra=vendido')


@login_required(login_url='/login/')
@require_POST
def personagem_comprar_magico(request, pk):
    """Compra um item mágico do catálogo: debita a carteira e adiciona ao inventário
    (guardado e não sintonizado — efeitos só com equipar/sintonizar)."""
    from .models import TbItemMagico, TbPersonagemItem
    p = _ficha_editavel(request, pk)
    item = TbItemMagico.objects.filter(slug=request.POST.get('item')).first()
    if not item or item.preco is None:
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=invalido')
    custo_pc = int(round(float(item.preco) * 100))  # preço em PO -> PC
    if custo_pc > (p.carteira_pc or 0):
        return redirect(reverse('editar_ficha', args=[pk]) + '?compra=saldo')
    with transaction.atomic():
        p.carteira_pc = (p.carteira_pc or 0) - custo_pc
        p.save(update_fields=['carteira_pc', 'atualizado_em'])
        TbPersonagemItem.objects.create(
            id_personagem=p, qtd=1, nome=item.nome, custo=('%g PO' % float(item.preco)),
            id_item_magico=item, equipado=False, sintonizado=False)
        _registrar_transacao(p, 'compra', 'Compra mágica: %s' % item.nome, -custo_pc)
    return redirect(reverse('editar_ficha', args=[pk]) + '?compra=ok')


@login_required(login_url='/login/')
@require_POST
def personagem_sintonizar_item(request, pk):
    """Sintoniza/dessintoniza um item mágico. Só itens que exigem sintonização;
    limite de 3 itens sintonizados por personagem (regra 5e)."""
    from .models import TbPersonagemItem
    p = _ficha_editavel(request, pk)
    it = (TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p)
          .select_related('id_item_magico').first())
    if not it or not it.id_item_magico or not it.id_item_magico.requer_sintonizacao:
        return redirect('editar_ficha', pk=pk)
    if not it.sintonizado:
        usados = TbPersonagemItem.objects.filter(id_personagem=p, sintonizado=True).count()
        if usados >= 3:
            return redirect(reverse('editar_ficha', args=[pk]) + '?sint=limite')
        it.sintonizado = True
        if not it.equipado:          # sintonizar implica portar o item
            it.equipado = True
        it.save(update_fields=['sintonizado', 'equipado'])
    else:
        it.sintonizado = False
        it.save(update_fields=['sintonizado'])
    return redirect('editar_ficha', pk=pk)


# ───────────────────────── Mercado da Comunidade ─────────────────────────────
@login_required(login_url='/login/')
@require_POST
def personagem_anunciar_magico(request, pk):
    """Anuncia um item mágico do inventário no Mercado da Comunidade pelo preço de
    venda do mercado. O item sai do inventário (escrow) até vender ou ser cancelado."""
    from .models import TbPersonagemItem, TbAnuncioItemMagico
    p = _ficha_editavel(request, pk)
    it = (TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p)
          .select_related('id_item_magico').first())
    if not it or not it.id_item_magico:
        return redirect(reverse('editar_ficha', args=[pk]) + '?anuncio=invalido')
    preco_pc = _preco_venda_pc(it.id_item_magico)
    with transaction.atomic():
        TbAnuncioItemMagico.objects.create(
            vendedor=p, id_item_magico=it.id_item_magico, nome=it.nome, custo=it.custo,
            preco_pc=preco_pc, status='ativo')
        if (it.qtd or 1) > 1:        # anuncia 1 unidade
            it.qtd -= 1
            it.save(update_fields=['qtd'])
        else:
            it.delete()
    return redirect(reverse('editar_ficha', args=[pk]) + '?anuncio=ok')


@login_required(login_url='/login/')
def mercado_comunidade_view(request):
    """Vitrine do Mercado da Comunidade: anúncios ativos de itens mágicos entre jogadores."""
    from .models import TbAnuncioItemMagico
    meus = list(request.user.personagens.filter(arquivado=False).only('id_personagem', 'nome', 'carteira_pc'))
    meus_ids = {p.id_personagem for p in meus}
    lista, meus_anuncios = [], []
    for a in (TbAnuncioItemMagico.objects.filter(status='ativo')
              .select_related('vendedor', 'id_item_magico')):
        im = a.id_item_magico
        card = {'id': a.id, 'nome': a.nome,
                'raridade': im.get_raridade_display() if im else '',
                'requer_sintonizacao': bool(im and im.requer_sintonizacao),
                'preco_display': _pc_display(a.preco_pc), 'vendedor': a.vendedor.nome}
        (meus_anuncios if a.vendedor_id in meus_ids else lista).append(card)
    return render(request, 'home/pages/mercado_comunidade.html', {
        'page_title': 'Mercado da Comunidade',
        'anuncios': lista, 'meus_anuncios': meus_anuncios,
        'meus_personagens': [{'id': p.id_personagem, 'nome': p.nome, 'carteira': _pc_display(p.carteira_pc)} for p in meus],
        'msg': request.GET.get('m'),
    })


@login_required(login_url='/login/')
@require_POST
def comprar_anuncio(request, anuncio_id):
    """Compra um anúncio: debita o comprador, credita o vendedor, move o item."""
    from .models import TbAnuncioItemMagico, TbPersonagem, TbPersonagemItem
    comprador = TbPersonagem.objects.filter(id_personagem=request.POST.get('comprador'),
                                            dono=request.user, arquivado=False).first()
    if not comprador:
        return redirect(reverse('mercado_comunidade') + '?m=sem_personagem')
    with transaction.atomic():
        a = (TbAnuncioItemMagico.objects.select_for_update()
             .filter(id=anuncio_id, status='ativo').select_related('vendedor').first())
        if not a:
            return redirect(reverse('mercado_comunidade') + '?m=indisponivel')
        if a.vendedor.dono_id == request.user.id:
            return redirect(reverse('mercado_comunidade') + '?m=proprio')
        if a.preco_pc > (comprador.carteira_pc or 0):
            return redirect(reverse('mercado_comunidade') + '?m=saldo')
        comprador.carteira_pc = (comprador.carteira_pc or 0) - a.preco_pc
        comprador.save(update_fields=['carteira_pc', 'atualizado_em'])
        vend = a.vendedor
        vend.carteira_pc = (vend.carteira_pc or 0) + a.preco_pc
        vend.save(update_fields=['carteira_pc', 'atualizado_em'])
        TbPersonagemItem.objects.create(id_personagem=comprador, qtd=1, nome=a.nome, custo=a.custo,
            id_item_magico=a.id_item_magico, equipado=False, sintonizado=False)
        a.status, a.comprador, a.vendido_em = 'vendido', comprador, timezone.now()
        a.save(update_fields=['status', 'comprador', 'vendido_em'])
        _registrar_transacao(comprador, 'mercado-compra', 'Comprou (comunidade): %s' % a.nome, -a.preco_pc)
        _registrar_transacao(vend, 'mercado-venda', 'Vendeu (comunidade): %s' % a.nome, a.preco_pc)
    return redirect(reverse('mercado_comunidade') + '?m=comprado')


@login_required(login_url='/login/')
@require_POST
def cancelar_anuncio(request, anuncio_id):
    """Cancela um anúncio próprio: devolve o item ao vendedor."""
    from .models import TbAnuncioItemMagico, TbPersonagemItem
    with transaction.atomic():
        a = (TbAnuncioItemMagico.objects.select_for_update()
             .filter(id=anuncio_id, status='ativo').select_related('vendedor').first())
        if not a or a.vendedor.dono_id != request.user.id:
            return redirect(reverse('mercado_comunidade') + '?m=invalido')
        TbPersonagemItem.objects.create(id_personagem=a.vendedor, qtd=1, nome=a.nome, custo=a.custo,
            id_item_magico=a.id_item_magico, equipado=False, sintonizado=False)
        a.status = 'cancelado'
        a.save(update_fields=['status'])
    return redirect(reverse('mercado_comunidade') + '?m=cancelado')


# ───────────────────────── Recursos de classe (usar/descansar) ───────────────
@login_required(login_url='/login/')
@require_POST
def personagem_usar_recurso(request, pk):
    """Gasta (−1) ou desfaz (+1) um uso de um recurso consumível do personagem."""
    from .character_engine import _recursos_consumiveis
    from .models import TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
    cons = {r['slug']: r for r in _recursos_consumiveis(p, classes)}
    r = cons.get(request.POST.get('recurso'))
    if not r:
        return redirect('editar_ficha', pk=pk)
    delta = 1 if request.POST.get('acao') == 'desfazer' else -1
    novo = max(0, min(r['maximo'], r['atual'] + delta))
    pr, _ = TbPersonagemRecurso.objects.get_or_create(
        id_personagem=p, nome=r['nome'], defaults={'maximo': r['maximo'], 'atual': r['maximo']})
    pr.atual, pr.maximo = novo, r['maximo']
    pr.save(update_fields=['atual', 'maximo'])
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_descansar(request, pk):
    """Descanso: recupera recursos. Curto = só os de reset curto; Longo = todos."""
    from .character_engine import _recursos_consumiveis
    from .models import TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    longo = request.POST.get('tipo') == 'longo'
    classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
    for r in _recursos_consumiveis(p, classes):
        if longo or r['reset'] in ('short-rest', 'short-or-long'):
            pr, _ = TbPersonagemRecurso.objects.get_or_create(
                id_personagem=p, nome=r['nome'], defaults={'maximo': r['maximo'], 'atual': r['maximo']})
            pr.atual, pr.maximo = r['maximo'], r['maximo']
            pr.save(update_fields=['atual', 'maximo'])
    return redirect(reverse('editar_ficha', args=[pk]) + ('?rest=longo' if longo else '?rest=curto'))


@login_required(login_url='/login/')
@require_POST
def personagem_preparar_magias(request, pk):
    """Salva o conjunto de magias preparadas de um conjurador preparado (Druida/Caçador/Mago)."""
    from .character_engine import derive
    from .models import TbMagia, TbPersonagemMagia
    p = _ficha_editavel(request, pk)
    info = _magias_preparadas_info(p, derive(p))
    if not info:
        return redirect('editar_ficha', pk=pk)
    validos = {m['slug'] for g in info['grupos'] for m in g['magias']}
    escolhidos = [s for s in dict.fromkeys(request.POST.getlist('magia')) if s in validos]
    if info['limite'] is not None:
        escolhidos = escolhidos[:info['limite']]
    pc = p.classes.filter(principal=True).first() or p.classes.first()
    classe_nome = pc.id_classe.nome
    with transaction.atomic():
        p.magias.filter(nivel__gte=1, preparada=True, sempre_preparada=False).delete()
        for s in escolhidos:
            mg = TbMagia.objects.filter(slug=s).first()
            if mg:
                TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=mg.nivel,
                    nome=mg.nome, preparada=True, origem=classe_nome)
    return redirect(reverse('editar_ficha', args=[pk]) + '?prep=ok')


@login_required(login_url='/login/')
def ficha_detail_view(request, pk):
    """Ficha derivada (character_engine.derive) de um personagem."""
    from .models import TbPersonagem, TbPersonagemEscolha
    from . import permissions as perms
    from .character_engine import derive, aventuras_para_nivel
    p = get_object_or_404(
        TbPersonagem.objects.select_related('id_raca', 'id_linhagem', 'id_essencia', 'id_antecedente'),
        pk=pk)
    if not perms.pode_ver_ficha(request.user, p):
        raise Http404()
    ficha = derive(p)
    # Linha de raça para a ficha: "Anão Elemental Oread" (raça + essência SEM a palavra
    # "Essência" + a vertente escolhida). Linhagem (sub-raça) vira "Raça (Linhagem)".
    _vert = (TbPersonagemEscolha.objects.filter(id_personagem=p, tipo='vertente')
             .values_list('valor', flat=True).first()) or ''
    _vert_disp = {'ifrit': 'Ifrit', 'undine': 'Undine', 'oread': 'Oread', 'sylph': 'Sylph'}.get(_vert, _vert.title())
    _raca = p.id_raca.nome if p.id_raca_id else ''
    if p.id_essencia_id:
        _ess = re.sub(r'^ess[êe]ncia\s+', '', p.id_essencia.nome or '', flags=re.I).strip()
        raca_linha = ' '.join(x for x in [_raca, _ess, _vert_disp] if x)
    elif p.id_linhagem_id:
        raca_linha = '%s (%s)' % (_raca, p.id_linhagem.nome)
    else:
        raca_linha = _raca
    # Aventuras necessárias para o PRÓXIMO nível (Excel: "PRÓXIMO NÍVEL")
    prog = ficha.get('progressao') or {}
    prog['proximo_nivel_aventuras'] = aventuras_para_nivel(min((prog.get('nivel_aventuras') or 0) + 1, 22))
    # Magias da Essência (vertente): sincroniza (idempotente) as fixas do nível atual e
    # levanta as ESCOLHAS pendentes (ex.: 2º ciclo, escolha 2 de 3) p/ a ficha pedir.
    from .models import TbPersonagemMagia, TbTransacao, TbMagia
    _sync_magias_concedidas(p)
    from .character_engine import magias_concedidas
    _pend = magias_concedidas(p)['pendentes']
    essencia_pendentes = []
    if _pend:
        _nomes = dict(TbMagia.objects.filter(
            slug__in=[s for b in _pend for s in b['opcoes']]).values_list('slug', 'nome'))
        for b in _pend:
            essencia_pendentes.append({
                'fonte': b['fonte'], 'slot': b['slot'], 'rotulo': b['rotulo'], 'qtd': b['qtd'],
                'escolhidos': b['escolhidos'],
                'opcoes': [{'slug': s, 'nome': _nomes.get(s, s)} for s in b['opcoes']]})
    # Página de Magias: todas as magias do personagem (preparadas / conhecidas-sempre).
    # As sempre_preparada (raça/outros) NÃO contam no total de preparadas da classe.
    magias_pers = list(TbPersonagemMagia.objects.filter(id_personagem=p).order_by('nivel', 'nome'))
    magias_info = {
        'lista': magias_pers,
        'n_preparadas': sum(1 for m in magias_pers if m.preparada and not m.sempre_preparada),
        'n_sempre': sum(1 for m in magias_pers if m.sempre_preparada),
        'total': len(magias_pers),
        'essencia_pendentes': essencia_pendentes,
    }
    # Página de Histórico: compras/vendas do personagem.
    transacoes = list(TbTransacao.objects.filter(id_personagem=p).order_by('-pk')[:300])
    return render(request, 'home/pages/ficha_detail.html', {
        'page_title': p.nome,
        'p': p,
        'ficha': ficha,
        'raca_linha': raca_linha,
        'magias_info': magias_info,
        'transacoes': transacoes,
        'pode_editar': p.dono_id == request.user.id or perms.is_staff_user(request.user),
    })


@login_required(login_url='/login/')
def personagem_trocar_maestria(request, pk):
    """Troca as armas de Maestria do personagem (a habilidade tem a tag `trocavel`).
    Nº de slots = quantas maestrias o personagem já tem. Reaproveita o catálogo de armas."""
    from .models import TbPersonagem, TbPersonagemEscolha, TbItemMundano
    from . import permissions as perms
    from .character_engine import derive
    p = get_object_or_404(TbPersonagem, pk=pk)
    if not (p.dono_id == request.user.id or perms.is_staff_user(request.user)):
        raise Http404()
    atuais = list(p.escolhas.filter(tipo='maestria').order_by('slot'))
    n_slots = len(atuais)
    ficha = derive(p)
    if n_slots == 0 or not ficha.get('maestria_trocavel'):
        return redirect(reverse('ficha_detail', args=[pk]))
    erro = None
    if request.method == 'POST':
        armas_validas = set(TbItemMundano.objects.filter(categoria='arma').values_list('slug', flat=True))
        escolhidas, vistos = [], set()
        for s in request.POST.getlist('arma'):
            if s in armas_validas and s not in vistos:
                escolhidas.append(s)
                vistos.add(s)
        if len(escolhidas) == n_slots:
            p.escolhas.filter(tipo='maestria').delete()
            for i, slug in enumerate(escolhidas):
                TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', valor=slug, slot=i)
            return redirect(reverse('ficha_detail', args=[pk]))
        erro = 'Escolha exatamente %d arma(s).' % n_slots
    return render(request, 'home/pages/trocar_maestria.html', {
        'page_title': 'Trocar Maestrias — %s' % p.nome,
        'p': p, 'armas': _criador_armas(), 'n_slots': n_slots,
        'atuais': [e.valor for e in atuais], 'erro': erro,
    })


@login_required(login_url='/login/')
@require_POST
def personagem_toggle_magia(request, pk, magia_id):
    """Marca/desmarca uma magia como PREPARADA (clicável na aba Magias da ficha).
    Magias `sempre_preparada` (raça/outros) não são alternáveis."""
    from .models import TbPersonagem, TbPersonagemMagia
    from . import permissions as perms
    p = get_object_or_404(TbPersonagem, pk=pk)
    if not (p.dono_id == request.user.id or perms.is_staff_user(request.user)):
        raise Http404()
    m = get_object_or_404(TbPersonagemMagia, pk=magia_id, id_personagem=p)
    if not m.sempre_preparada:
        m.preparada = not m.preparada
        m.save(update_fields=['preparada'])
    return redirect(reverse('ficha_detail', args=[pk]) + '?aba=magias')


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_magia_essencia(request, pk):
    """Salva a ESCOLHA de magias concedidas por uma feature (ex.: 2º ciclo elemental —
    escolha 2 de 3). Um POST por bloco: `fonte`, `nivel` e `magia` (multi). Valida contra
    as opções do bloco, limita à quantidade e grava TbPersonagemEscolha (tipo=
    'magia-concedida', origem=fonte, slot=nível). Depois ressincroniza TbPersonagemMagia."""
    from .models import TbPersonagem, TbPersonagemEscolha
    from . import permissions as perms
    from .character_engine import magias_concedidas
    p = get_object_or_404(TbPersonagem, pk=pk)
    if not (p.dono_id == request.user.id or perms.is_staff_user(request.user)):
        raise Http404()
    fonte = (request.POST.get('fonte') or '').strip()
    try:
        slot = int(request.POST.get('slot') or 0)
    except (TypeError, ValueError):
        slot = 0
    bloco = next((b for b in magias_concedidas(p)['pendentes']
                  if b['fonte'] == fonte and b['slot'] == slot), None)
    if bloco:
        opcoes = set(bloco['opcoes'])
        sel, vistos = [], set()
        for s in request.POST.getlist('magia'):
            if s in opcoes and s not in vistos:
                sel.append(s); vistos.add(s)
            if len(sel) >= bloco['qtd']:
                break
        if len(sel) == bloco['qtd']:
            TbPersonagemEscolha.objects.filter(id_personagem=p, tipo='magia-concedida',
                                               origem=fonte, slot=slot).delete()
            TbPersonagemEscolha.objects.create(id_personagem=p, tipo='magia-concedida',
                                               origem=fonte, slot=slot, valor=','.join(sel))
    _sync_magias_concedidas(p)
    return redirect(reverse('ficha_detail', args=[pk]) + '?aba=magias')


@login_required(login_url='/login/')
@require_POST
def personagem_info_salvar(request, pk):
    """Salva os campos da aba 'Informações' da ficha (lore, aparência, fotos via link, etc.)."""
    from .models import TbPersonagem
    from . import permissions as perms
    p = get_object_or_404(TbPersonagem, pk=pk)
    if not (p.dono_id == request.user.id or perms.is_staff_user(request.user)):
        raise Http404()
    campos = ['jogador', 'idade', 'altura', 'peso', 'tamanho', 'genero', 'olhos', 'cabelo',
              'pele', 'aparencia', 'historia', 'anotacoes', 'foto_url', 'token_url']
    for c in campos:
        if c in request.POST:
            setattr(p, c, (request.POST.get(c) or '').strip()[:5000] or None)
    p.save(update_fields=campos)
    return redirect(reverse('ficha_detail', args=[pk]) + '?aba=info')


@login_required(login_url='/login/')
@require_POST
def criar_personagem_view(request):
    """Persiste a ficha criada (point-buy + escolhas) -> TbPersonagem + relacionados."""
    from .models import (TbPersonagem, TbPersonagemClasse, TbPersonagemPericia,
                         TbPersonagemProficiencia, TbPersonagemItem, TbPersonagemTalento,
                         TbPersonagemAtributoBonus, TbPersonagemEscolha, TbItemMundano, TbOpcaojogo,
                         TbPersonagemMagia, TbMagia,
                         TbRaca, TbLinhagem, TbEssencia, TbClasse, TbAntecedente, TbTalento)
    from .character_engine import _SKILL_INFO
    from . import point_buy, permissions as perms

    data = _json_body(request)
    erros = []
    SIG = point_buy.SIGLAS

    if not perms.pode_criar(request.user):
        return JsonResponse({'ok': False, 'erros': ['Limite de fichas ativas atingido — guarde uma no cofre.']}, status=400)

    nome = (data.get('nome') or '').strip()
    if not nome:
        erros.append('Dê um nome ao personagem.')

    scores = data.get('scores') or {}
    base = {s: int(scores.get(s, 8) or 8) for s in SIG}
    _, e = point_buy.validar([base[s] for s in SIG]); erros += e
    asi = data.get('asi') or {}
    mais2, mais1 = asi.get('mais2'), asi.get('mais1')
    _, e2 = point_buy.validar_asi(mais2, mais1); erros += e2

    raca = TbRaca.objects.filter(slug=data.get('raca')).first()
    classe = TbClasse.objects.filter(slug=data.get('classe')).first()
    antec = TbAntecedente.objects.filter(slug=data.get('antecedente')).first()
    if not raca:
        erros.append('Escolha uma raça.')
    if not classe:
        erros.append('Escolha uma classe.')
    if not antec:
        erros.append('Escolha um antecedente.')

    # Maestria de Arma: escolha de ARMAS (não de maestrias). Conhece todas as maestrias de cada arma.
    mn = _classe_maestria_n(classe, 1) if classe else 0
    armas_sel = list(dict.fromkeys(data.get('maestrias') or []))  # dedup, preserva ordem
    if mn:
        validas = set(TbItemMundano.objects.filter(categoria='arma', slug__in=armas_sel)
                      .values_list('slug', flat=True))
        armas_sel = [s for s in armas_sel if s in validas]
        if len(armas_sel) != mn:
            erros.append('Escolha %d arma(s) para Maestria de Arma.' % mn)

    # Perícias: validar quantidade e pertinência no SERVIDOR (não confiar só no cliente)
    pc = list(dict.fromkeys(data.get('pericias_classe') or []))
    pa = list(dict.fromkeys(data.get('pericias_antecedente') or []))
    if classe:
        pn, plista = _parse_skills_lvl1(classe.tags_json)
        pool = set(plista) if plista else set(_SKILL_INFO.keys())
        if len(pc) != pn or any(s not in pool for s in pc):
            erros.append('Escolha exatamente %d perícia(s) de classe válida(s).' % pn)
    if len(pa) != 2 or any(s not in _SKILL_INFO for s in pa):
        erros.append('Escolha exatamente 2 perícias de antecedente válidas.')

    # Escolhas de classe nv1: estilo de luta (Guerreiro) e expertise (Ladino)
    esc1 = _classe_escolhas_nv1(classe) if classe else {'estilo_n': 0, 'expertise_n': 0, 'expertise_fixa': []}
    if esc1['estilo_n'] and not TbOpcaojogo.objects.filter(tipo='Estilo de Luta', slug=data.get('estilo_luta')).exists():
        erros.append('Escolha um Estilo de Luta.')
    exp_sel = [s for s in dict.fromkeys(data.get('expertise') or []) if s in set(pc + pa)]
    if esc1['expertise_n'] and len(exp_sel) != esc1['expertise_n']:
        erros.append('Escolha %d perícia(s) para Especialização (entre as proficientes).' % esc1['expertise_n'])

    # Conjuração nv1: truques + magias de 1º nível
    conj = _classe_conjuracao(classe) if classe else None
    truques_sel, magias_sel = [], []
    if conj:
        tslugs = {t['slug'] for t in conj['truques']}
        nslugs = {m['slug'] for m in conj['magias_nv1']}
        truques_sel = [s for s in dict.fromkeys(data.get('truques') or []) if s in tslugs]
        magias_sel = [s for s in dict.fromkeys(data.get('magias') or []) if s in nslugs]
        n_mag = _spell_count_nv1(conj, base, mais2, mais1)
        if conj['truques_n'] and len(truques_sel) != conj['truques_n']:
            erros.append('Escolha %d truque(s).' % conj['truques_n'])
        if len(magias_sel) != n_mag:
            erros.append('Escolha %d magia(s) de 1º nível.' % n_mag)

    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)

    linhagem = TbLinhagem.objects.filter(slug=data.get('linhagem'), id_raca=raca).first() if data.get('linhagem') else None
    essencia = TbEssencia.objects.filter(slug=data.get('essencia')).first() if data.get('essencia') else None
    campo = {'FOR': 'forca', 'DES': 'destreza', 'CON': 'constituicao',
             'INT': 'inteligencia', 'SAB': 'sabedoria', 'CAR': 'carisma'}

    with transaction.atomic():
        p = TbPersonagem.objects.create(
            dono=request.user, nome=nome[:150], nivel=1,
            id_raca=raca, id_linhagem=linhagem, id_essencia=essencia, id_antecedente=antec,
            **{campo[s]: base[s] for s in SIG})
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=classe, nivel=1, principal=True)
        TbPersonagemAtributoBonus.objects.create(id_personagem=p, atributo=mais2, valor=2,
                                                 origem='Antecedente %s' % antec.nome, origem_tipo='antecedente')
        TbPersonagemAtributoBonus.objects.create(id_personagem=p, atributo=mais1, valor=1,
                                                 origem='Antecedente %s' % antec.nome, origem_tipo='antecedente')
        if essencia and data.get('vertente'):
            TbPersonagemEscolha.objects.create(id_personagem=p, origem='Essência %s' % essencia.nome,
                                               tipo='vertente', valor=data['vertente'])
        for i, wslug in enumerate(armas_sel[:mn]):
            TbPersonagemEscolha.objects.create(id_personagem=p, origem='Maestria de Arma (%s)' % classe.nome,
                                               tipo='maestria', slot=i, valor=wslug)
        for sl in set(pc + pa):
            info = _SKILL_INFO.get(sl)
            if info:
                TbPersonagemPericia.objects.get_or_create(
                    id_personagem=p, nome=info[0], defaults={'atributo': info[1], 'proficiente': True})
        TbPersonagemProficiencia.objects.create(id_personagem=p, tipo='idioma', nome='Comum', origem='regra')
        ferr_nomes = set(TbItemMundano.objects.filter(categoria='ferramenta').values_list('nome', flat=True))
        for esc in (data.get('idiomas_ferramentas') or [])[:2]:
            tipo = 'ferramenta' if esc in ferr_nomes else 'idioma'
            TbPersonagemProficiencia.objects.create(id_personagem=p, tipo=tipo, nome=esc, origem='antecedente')
        # Escolhas de RAÇA (perícias/idiomas/ferramentas extras da raça/linhagem/essência)
        esc_raca = data.get('escolhas_raca') or {}
        for sl in (esc_raca.get('pericias') or []):
            info = _SKILL_INFO.get(sl)
            if info:
                TbPersonagemPericia.objects.get_or_create(
                    id_personagem=p, nome=info[0], defaults={'atributo': info[1], 'proficiente': True})
        for nm in (esc_raca.get('idiomas') or []):
            TbPersonagemProficiencia.objects.get_or_create(
                id_personagem=p, tipo='idioma', nome=nm, defaults={'origem': 'racial'})
        for nm in (esc_raca.get('ferramentas') or []):
            TbPersonagemProficiencia.objects.get_or_create(
                id_personagem=p, tipo='ferramenta', nome=nm, defaults={'origem': 'racial'})
        # Dinheiro inicial vai para a CARTEIRA (PC): antecedente 100 PO + (opção da classe 150 PO OU equipamento texto)
        carteira = 100 * 100
        if data.get('equip_classe') == 'inicial' and (classe.equipamento or '').strip():
            TbPersonagemItem.objects.create(id_personagem=p, qtd=1,
                                            nome='Equipamento inicial da classe: %s' % classe.equipamento.strip()[:170])
        else:
            carteira += 150 * 100
        # Sem armadura inicial: o jogador compra e equipa a armadura na própria ficha,
        # e a CA é derivada do equipamento equipado (não se pré-equipa nada no criador).
        p.carteira_pc = carteira
        p.save(update_fields=['carteira_pc'])
        to = (TbTalento.objects.filter(id_talento=data.get('talento_origem'), tipo__iexact='origem').first()
              if data.get('talento_origem') else None)
        if to:
            TbPersonagemTalento.objects.create(id_personagem=p, id_talento=to, categoria='origem', nivel=1, nome=to.nome)
        if data.get('talento_raca'):
            TbPersonagemTalento.objects.create(id_personagem=p, categoria='racial', nivel=1, nome=data['talento_raca'])
        # Estilo de Luta (Guerreiro)
        if esc1['estilo_n']:
            est = TbOpcaojogo.objects.filter(tipo='Estilo de Luta', slug=data.get('estilo_luta')).first()
            if est:
                TbPersonagemEscolha.objects.create(id_personagem=p, origem='Estilo de Luta (%s)' % classe.nome,
                                                   tipo='estilo-de-luta', valor=est.slug)
        # Perícia-Especializada (expertise) escolhida — marca nas perícias proficientes
        for sl in exp_sel[:esc1['expertise_n']]:
            info = _SKILL_INFO.get(sl)
            if info:
                TbPersonagemPericia.objects.filter(id_personagem=p, nome=info[0]).update(expertise=True)
        # Expertise FIXA (Mago: Arcanismo) — proficiência + expertise automáticas
        for sl in esc1['expertise_fixa']:
            info = _SKILL_INFO.get(sl)
            if info:
                TbPersonagemPericia.objects.update_or_create(
                    id_personagem=p, nome=info[0],
                    defaults={'atributo': info[1], 'proficiente': True, 'expertise': True})
        # Magias conhecidas/preparadas no nível 1 (truques + 1º nível)
        if conj:
            for nivel, sel in ((0, truques_sel), (1, magias_sel)):
                for slug in sel:
                    mg = TbMagia.objects.filter(slug=slug).first()
                    if mg:
                        TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mg, nivel=nivel,
                            nome=mg.nome, preparada=True, origem=classe.nome)
        # Magias da Essência (vertente): concede as fixas do nível atual (cantrips + 1º
        # ciclo no nível 1). As de escolha (2º ciclo) ficam pendentes até o nível 5.
        _sync_magias_essencia(p)

    return JsonResponse({'ok': True, 'id': p.id_personagem,
                         'redirect': reverse('ficha_detail', args=[p.id_personagem])})


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _talent_payload(talent):
    atributos = []
    if talent.atrib_forca:
        atributos.append('Forca')
    if talent.atrib_destreza:
        atributos.append('Destreza')
    if talent.atrib_constituicao:
        atributos.append('Constituicao')
    if talent.atrib_inteligencia:
        atributos.append('Inteligencia')
    if talent.atrib_sabedoria:
        atributos.append('Sabedoria')
    if talent.atrib_carisma:
        atributos.append('Carisma')

    return {
        'id': talent.id_talento,
        'nome': talent.nome,
        'slug': talent.slug,
        'tipo': talent.get_tipo_display(),
        'tipo_key': talent.tipo,
        'etiqueta': talent.get_etiqueta_display(),
        'etiqueta_key': talent.etiqueta,
        'etiquetas_adicionais': talent.etiquetas_adicionais or '',
        'tags_json': talent.tags_json or [],
        'pre_requisito': talent.pre_requisito or 'Nenhum',
        'atributos_str': ', '.join(atributos) if atributos else 'Nenhum',
        'atrib_forca': talent.atrib_forca,
        'atrib_destreza': talent.atrib_destreza,
        'atrib_constituicao': talent.atrib_constituicao,
        'atrib_inteligencia': talent.atrib_inteligencia,
        'atrib_sabedoria': talent.atrib_sabedoria,
        'atrib_carisma': talent.atrib_carisma,
        'descricao': talent.descricao,
    }


@staff_member_required
@require_POST
def wiki_update_talent(request, talent_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'talento')
    talent = get_object_or_404(TbTalento, pk=talent_id)

    talent.nome = (data.get('nome') or talent.nome).strip()
    talent.tipo = data.get('tipo') if data.get('tipo') in dict(TbTalento.TIPO_CHOICES) else talent.tipo
    talent.etiqueta = data.get('etiqueta') if data.get('etiqueta') in dict(TbTalento.ETIQUETA_CHOICES) else talent.etiqueta
    talent.etiquetas_adicionais = (data.get('etiquetas_adicionais') or '').strip() or None
    if 'tags_json' in data or 'TagsJSON' in data:
        talent.tags_json = _tags_json_value(data)
    talent.pre_requisito = (data.get('pre_requisito') or '').strip() or None
    talent.descricao = data.get('descricao') or ''
    for attr in ('atrib_forca', 'atrib_destreza', 'atrib_constituicao', 'atrib_inteligencia', 'atrib_sabedoria', 'atrib_carisma'):
        setattr(talent, attr, bool(data.get(attr)))
    talent.save()
    _log_wiki_edit(request, talent, f"Edição inline de talento: {talent.nome}")
    return JsonResponse({'ok': True, 'talent': _talent_payload(talent)})


@staff_member_required
@require_POST
def wiki_update_option(request, id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'opcao')
    opcao = get_object_or_404(TbOpcaojogo, pk=id)

    opcao.nome = (data.get('nome') or opcao.nome).strip()
    opcao.tipo = (data.get('tipo') or opcao.tipo).strip()
    opcao.etiquetas_adicionais = (data.get('etiquetas_adicionais') or '').strip() or None
    if 'tags_json' in data or 'TagsJSON' in data:
        opcao.tags_json = _tags_json_value(data)
    opcao.pre_requisito = (data.get('pre_requisito') or '').strip() or None
    opcao.descricao = data.get('descricao') or ''
    opcao.save()
    _log_wiki_edit(request, opcao, f"Edição inline de opção de jogo: {opcao.nome}")
    return JsonResponse({'ok': True, 'opcao': _option_payload(opcao)})


def _option_payload(o):
    return {
        'id': o.id_opcao,
        'nome': o.nome,
        'slug': o.slug,
        'tipo': o.tipo,
        'descricao': o.descricao,
        'pre_requisito': o.pre_requisito or '',
        'etiquetas_adicionais': o.etiquetas_adicionais or '',
        'tags_json': o.tags_json or [],
    }


@staff_member_required
@require_POST
def wiki_update_class_feature(request, feature_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'habilidade')
    feature = get_object_or_404(TbClassehabilidade, pk=feature_id)
    feature.nome = (data.get('nome') or feature.nome).strip()
    try:
        feature.niveladquirido = max(int(data.get('niveladquirido', feature.niveladquirido)), 0)
    except (TypeError, ValueError):
        pass
    feature.descricao = data.get('descricao') or ''
    if 'tags_json' in data or 'TagsJSON' in data:
        feature.tags_json = _tags_json_value(data)
    feature.save()
    _log_wiki_edit(request, feature, f"Edição inline de recurso de classe: {feature.nome}")
    return JsonResponse({
        'ok': True,
        'feature': {
            'id': feature.id_habilidade,
            'nome': feature.nome,
            'niveladquirido': feature.niveladquirido,
            'descricao': feature.descricao,
            'tags_json': feature.tags_json or [],
        },
    })


@staff_member_required
@require_POST
def wiki_update_racial_trait(request, trait_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'traco')
    trait = get_object_or_404(TbTracoracial, pk=trait_id)
    trait.nome = (data.get('nome') or trait.nome).strip()
    try:
        trait.nivel_requisito = max(int(data.get('nivel_requisito', trait.nivel_requisito)), 0)
    except (TypeError, ValueError):
        pass
    trait.talento_racial = bool(data.get('talento_racial'))
    trait.pre_requisito = (data.get('pre_requisito') or '').strip() or None
    trait.descricao = data.get('descricao') or ''
    if 'tags_json' in data or 'TagsJSON' in data:
        trait.tags_json = _tags_json_value(data)
    trait.save()
    _log_wiki_edit(request, trait, f"Edição inline de traço racial: {trait.nome}")
    return JsonResponse({
        'ok': True,
        'trait': {
            'id': trait.id_traco,
            'nome': trait.nome,
            'nivel_requisito': trait.nivel_requisito,
            'talento_racial': trait.talento_racial,
            'pre_requisito': trait.pre_requisito or '',
            'descricao': trait.descricao,
            'tags_json': trait.tags_json or [],
        },
    })


@staff_member_required
@require_POST
def wiki_update_race(request, race_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'raca')
    race = get_object_or_404(TbRaca, pk=race_id)
    race.nome = (data.get('nome') or race.nome).strip()
    race.tagline = (data.get('tagline') or '').strip() or None
    race.lore_presentation = data.get('lore_presentation') or ''
    race.lore_roleplay = data.get('lore_roleplay') or ''
    race.lore_society = data.get('lore_society') or ''
    race.save()
    _log_wiki_edit(request, race, f"Edição inline de raça: {race.nome}")
    return JsonResponse({
        'ok': True,
        'race': {
            'id': race.id_raca,
            'nome': race.nome,
            'tagline': race.tagline or '',
            'lore_presentation': race.lore_presentation or '',
            'lore_roleplay': race.lore_roleplay or '',
            'lore_society': race.lore_society or '',
        },
    })


def _marker_lore_url(nome, lore_url_raw):
    
    if lore_url_raw:
        return lore_url_raw
    slug = slugify(nome)
    return f'/mundo/regioes/{slug}/' if slug else ''

def _sync_markers_from_regions():
    
    regioes = TbRegiao.objects.all()
    marcadores_dict = {m.nome: m for m in TbMapMarker.objects.all()}
    
    for r in regioes:
        if r.nome not in marcadores_dict:
            TbMapMarker.objects.create(
                nome=r.nome,
                lat=0,
                lng=0,
                categoria=r.categoria or 'cidade',
                territorio=r.territorio,
            )
        else:
            m = marcadores_dict[r.nome]
            if m.territorio != r.territorio or m.categoria != r.categoria:
                m.territorio = r.territorio
                m.categoria = r.categoria
                m.save()

def _extract_brief(lore_markdown):
    
    if not lore_markdown:
        return ''
    started = False
    parts = []
    for line in lore_markdown.replace('\r\n', '\n').split('\n'):
        stripped = line.strip()
        if not started:
            if re.match(r'^#(?!#)\s+', stripped):
                started = True
            continue
        if re.match(r'^##\s+', stripped):
            break
        if stripped and not stripped.startswith('#'):
            parts.append(stripped)
    return ' '.join(parts).strip()


def mapa_view(request):
    def region_payload(region):
        if isinstance(region, dict):
            return {
                'id': region.get('Id_Regiao'),
                'nome': region.get('Nome') or '',
                'slug': region.get('Slug') or slugify(region.get('Nome') or ''),
                'descricao_breve': _extract_brief(region.get('LoreMarkdown')),
                'territorio': region.get('Territorio') or 'Sem território',
                'categoria': region.get('Categoria') or 'cidade',
                'camada': region.get('Camada') or 0,
                'lore_url': _marker_lore_url(region.get('Nome') or '', ''),
                'stats': {
                    'movimentacoes_economicas': region.get('MovimentacoesEconomicas', 0),
                    'poder_militar': region.get('PoderMilitar', 0),
                    'desenvolvimento_tecnologico': region.get('DesenvolvimentoTecnologico', 0),
                    'estabilidade_politica_interna': region.get('EstabilidadePoliticaInterna', 0),
                    'ameacas_externas': region.get('AmeacasExternas', 0),
                    'densidade_populacional': region.get('DensidadePopulacional', 0),
                    'tolerancia_estrangeiros': region.get('ToleranciaEstrangeiros', 0),
                    'manipulacao_trama': region.get('ManipulacaoTrama', 0),
                    'ameacas_internas': region.get('AmeacasInternas', 0),
                    'nivel_periculosidade': region.get('NivelPericulosidade', 0),
                    'recursos_naturais': region.get('RecursosNaturais', 0),
                    'recursos_magicos': region.get('RecursosMagicos', 0),
                    'diversidade_criaturas': region.get('DiversidadeCriaturas', 0),
                }
            }
        return {
            'id': region.id_regiao,
            'nome': region.nome,
            'slug': region.slug,
            'descricao_breve': _extract_brief(region.lore_markdown),
            'territorio': region.territorio or 'Sem território',
            'categoria': region.categoria or 'cidade',
            'camada': region.camada,
            'lore_url': _marker_lore_url(region.nome, ''),
            'stats': {
                'movimentacoes_economicas': region.movimentacoes_economicas,
                'poder_militar': region.poder_militar,
                'desenvolvimento_tecnologico': region.desenvolvimento_tecnologico,
                'estabilidade_politica_interna': region.estabilidade_politica_interna,
                'ameacas_externas': region.ameacas_externas,
                'densidade_populacional': region.densidade_populacional,
                'tolerancia_estrangeiros': region.tolerancia_estrangeiros,
                'manipulacao_trama': region.manipulacao_trama,
                'ameacas_internas': region.ameacas_internas,
                'nivel_periculosidade': region.nivel_periculosidade,
                'recursos_naturais': region.recursos_naturais,
                'recursos_magicos': region.recursos_magicos,
                'diversidade_criaturas': region.diversidade_criaturas,
            }
        }

    def territory_payload(territory):
        if isinstance(territory, dict):
            return {
                'id': territory.get('Id_Territorio'),
                'nome': territory.get('Nome') or '',
                'slug': territory.get('Slug') or slugify(territory.get('Nome') or ''),
                'descricao_breve': territory.get('DescricaoBreve') or '',
                'imagem_url': _asset_url(territory.get('ImagemUrl')),
                'coordenadas_poligono': territory.get('CoordenadasPoligono'),
                'cor_hex': territory.get('CorHex', '#ffffff'),
                'camada': territory.get('Camada') or 0,
                'stats': {
                    'riqueza_natural': territory.get('RiquezaNatural', 0),
                    'riqueza_monetaria': territory.get('RiquezaMonetaria', 0),
                    'poder_militar': territory.get('PoderMilitar', 0),
                    'desenvolvimento_tecnologico': territory.get('DesenvolvimentoTecnologico', 0),
                    'estabilidade_politica_interna': territory.get('EstabilidadePoliticaInterna', 0),
                    'ameacas_externas': territory.get('AmeacasExternas', 0),
                    'diplomacia': territory.get('Diplomacia', 0),
                    'manipulacao_trama': territory.get('ManipulacaoTrama', 0),
                }
            }
        return {
            'id': territory.id_territorio,
            'nome': territory.nome,
            'slug': territory.slug,
            'descricao_breve': territory.descricao_breve or '',
            'imagem_url': _asset_url(territory.imagem_url),
            'coordenadas_poligono': territory.coordenadas_poligono,
            'cor_hex': territory.cor_hex or '#ffffff',
            'camada': territory.camada,
            'stats': {
                'riqueza_natural': territory.riqueza_natural,
                'riqueza_monetaria': territory.riqueza_monetaria,
                'poder_militar': territory.poder_militar,
                'desenvolvimento_tecnologico': territory.desenvolvimento_tecnologico,
                'estabilidade_politica_interna': territory.estabilidade_politica_interna,
                'ameacas_externas': territory.ameacas_externas,
                'diplomacia': territory.diplomacia,
                'manipulacao_trama': territory.manipulacao_trama,
            }
        }

    try:
        marcadores_docs = _mongo_docs('map_markers', [('Nome', 1)])
        regioes_docs = _mongo_docs('regions', [('Territorio', 1), ('Nome', 1)])
        territorios_docs = _mongo_docs('territories', [('Nome', 1)])
        regioes_lista = [region_payload(region) for region in regioes_docs]
        territorios_lista = [territory_payload(territory) for territory in territorios_docs]

        marcadores_lista = [
            {
                'id': marker.get('Id_Marker'),
                'nome': marker.get('Nome') or '',
                'lat': marker.get('Latitude'),
                'lng': marker.get('Longitude'),
                'categoria': marker.get('Categoria') or 'cidade',
                'territorio': marker.get('Territorio') or '',
                'camada': marker.get('Camada') or 0,
                'lore_url': _marker_lore_url(marker.get('Nome') or '', ''),
            }
            for marker in marcadores_docs
        ]

        if not request.user.is_staff:
            marcadores_lista = [m for m in marcadores_lista if m.get('camada', 0) == 0]
            regioes_lista = [r for r in regioes_lista if r.get('camada', 0) == 0]
            territorios_lista = [t for t in territorios_lista if t.get('camada', 0) == 0]

        return render(request, 'home/pages/mapa.html', {
            'json_markers': marcadores_lista,
            'json_regions': regioes_lista,
            'json_territories': territorios_lista,
            'can_edit_wiki': request.user.is_staff,
        })
    except BotMongoUnavailable:
        pass

    marcadores_db = TbMapMarker.objects.all()
    regioes_lista = [region_payload(region) for region in TbRegiao.objects.all().order_by('territorio', 'nome')]
    territorios_lista = [territory_payload(territory) for territory in TbTerritorio.objects.all().order_by('nome')]

    marcadores_lista = []

    for m in marcadores_db:
        marcadores_lista.append({
            'id': m.id_marker,
            'nome': m.nome,
            'lat': m.lat,
            'lng': m.lng,
            'categoria': m.categoria,
            'territorio': m.territorio or '',
            'camada': m.camada,
            'lore_url': _marker_lore_url(m.nome, ''),
        })

    if not request.user.is_staff:
        marcadores_lista = [m for m in marcadores_lista if m.get('camada', 0) == 0]
        regioes_lista = [r for r in regioes_lista if r.get('camada', 0) == 0]
        territorios_lista = [t for t in territorios_lista if t.get('camada', 0) == 0]

    context = {
        'json_markers': marcadores_lista,
        'json_regions': regioes_lista,
        'json_territories': territorios_lista,
        'can_edit_wiki': request.user.is_staff,
    }
    return render(request, 'home/pages/mapa.html', context)


def mundo_regioes_view(request):
    territory_slug = request.GET.get('territory')
    if territory_slug:
        territory_obj = TbTerritorio.objects.filter(slug=territory_slug).first()
        if territory_obj:
            first_region = TbRegiao.objects.filter(territorio=territory_obj.nome).first()
            if first_region:
                return regiao_detail_view(request, slug=first_region.slug)

    if not request.user.is_staff:
        regioes = TbRegiao.objects.filter(camada=0).order_by('territorio', 'nome')
        territorios_qs = TbTerritorio.objects.filter(camada=0)
    else:
        regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
        territorios_qs = TbTerritorio.objects.all()

    regioes_lista = []
    markers = {m.nome: m for m in TbMapMarker.objects.all()}
    for r in regioes:
        m = markers.get(r.nome)
        regioes_lista.append({
            'id': r.id_regiao,
            'nome': r.nome,
            'slug': r.slug,
            'territorio': r.territorio or 'Sem território',
            'categoria': r.categoria or 'cidade',
            'etiquetas_adicionais': r.etiquetas_adicionais or '',
        })

    territories_by_name = {t.nome: t for t in territorios_qs}
    grouped = {}
    for region in regioes_lista:
        key = region['territorio'] or 'Sem território'
        grouped.setdefault(key, []).append(region)

    territorios_cards = []
    for territory_name, regions in sorted(grouped.items(), key=lambda item: item[0]):
        territory = territories_by_name.get(territory_name) or next((t for t in territories_by_name.values() if _normalize_text(t.nome) == _normalize_text(territory_name)), None)
        image_url = _asset_url(territory.imagem_url) if territory and territory.imagem_url else _asset_url(None)
        description = (territory.descricao_breve if territory and territory.descricao_breve else '') or f"{len(regions)} locais conhecidos em {_display_territory(territory_name)}."
        tags = sorted({
            tag.strip()
            for r in regions
            for tag in (r.get('etiquetas_adicionais') or '').split(',')
            if tag.strip()
        })[:6]
        
        color = territory.cor_hex if territory and territory.cor_hex else _territory_color(territory_name)
        display_color = _get_display_color(color)
        display_nome = _display_territory(territory_name)
        if territory and territory.camada > 0:
            display_nome += f" (Subterrâneo Lvl {territory.camada})"
        territorios_cards.append({
            'nome': territory_name,
            'display_nome': display_nome,
            'slug': territory.slug if territory else slugify(territory_name),
            'imagem_url': image_url,
            'descricao_breve': description,
            'color': color,
            'display_color': display_color,
            'contrast': _get_contrast_color(color),
            'locais_count': len(regions),
            'regioes': regions,
            'tags': tags,
        })

    return render(request, 'home/pages/regioes.html', {
        'regioes': regioes_lista,
        'territorios_cards': territorios_cards,
        'total_territorios': len(territorios_cards),
        'total_locais': len(regioes_lista),
        'can_edit_wiki': request.user.is_staff,
        'categoria_choices': TbMapMarker.PIN_ICON_CHOICES,
    })


def _parse_lore_topics(markdown_text):
    
    if not markdown_text:
        return []

    lines = markdown_text.splitlines()
    topics = []
    
    
    current_topic = {
        'slug': 'base',
        'title': 'Visão Geral',
        'content': [], 
    }
    
    current_h1_group = None 
    
    def finalize_h1_group():
        nonlocal current_h1_group
        if current_h1_group:
            
            if current_h1_group['current_h3']:
                current_h1_group['subtopics'].append(current_h1_group['current_h3'])
            current_topic['content'].append(current_h1_group)
            current_h1_group = None

    for line in lines:
        if line.startswith('## '):
            finalize_h1_group()
            
            topics.append(current_topic)
            
            title = line.lstrip('#').strip()
            current_topic = {
                'slug': slugify(title),
                'title': title,
                'content': [],
            }
        elif line.startswith('# '):
            finalize_h1_group()
            title = line.lstrip('#').strip()
            current_h1_group = {
                'type': 'h1_group',
                'title': title,
                'intro': [],
                'subtopics': [],
                'current_h3': None
            }
        elif line.startswith('### ') and current_h1_group:
            
            if current_h1_group['current_h3']:
                current_h1_group['subtopics'].append(current_h1_group['current_h3'])
            
            title = line.lstrip('#').strip()
            current_h1_group['current_h3'] = {
                'slug': slugify(title),
                'title': title,
                'content': []
            }
        elif line.startswith('### ') and not current_h1_group:
            
            current_topic['content'].append(line)
        else:
            
            if current_h1_group:
                if current_h1_group['current_h3']:
                    current_h1_group['current_h3']['content'].append(line)
                else:
                    current_h1_group['intro'].append(line)
            else:
                current_topic['content'].append(line)

    finalize_h1_group()
    topics.append(current_topic)
    
    
    for t in topics:
        final_content = []
        for part in t['content']:
            if isinstance(part, dict):
                
                part['intro'] = '\n'.join(part['intro']).strip()
                for st in part['subtopics']:
                    st['content'] = '\n'.join(st['content']).strip()
                final_content.append(part)
            else:
                
                if final_content and isinstance(final_content[-1], str):
                    final_content[-1] += '\n' + part
                else:
                    final_content.append(part)
        t['content'] = final_content

    return topics


def _organization_payload(document):
    name = _doc_value(document, ['Nome', 'nome', 'Name', 'name'])
    return {
        'id': str(_doc_value(document, ['_id', 'Id', 'Id_Organizacao', 'id'])),
        'nome': name,
        'slug': _doc_value(document, ['Slug', 'slug'], slugify(name)),
        'tipo': _doc_value(document, ['Tipo', 'tipo'], 'Organizacao'),
        'sede': _doc_value(document, ['Sede', 'sede']),
        'regioes': _split_catalog_list(_doc_value(document, ['Regioes', 'Regiões', 'regioes', 'regions'])),
        'territorios': _split_catalog_list(_doc_value(document, ['Territorios', 'Territórios', 'territorios', 'territories'])),
        'lideranca': _doc_value(document, ['Lideranca', 'Liderança', 'lideranca', 'leadership']),
        'aliados': _split_catalog_list(_doc_value(document, ['Aliados', 'aliados', 'allies'])),
        'inimigos': _split_catalog_list(_doc_value(document, ['Inimigos', 'inimigos', 'enemies'])),
        'tags': _split_catalog_list(_doc_value(document, ['Tags', 'tags', 'EtiquetasAdicionais'])),
        'descricao': _doc_value(document, ['Descricao', 'Descrição', 'descricao', 'description']),
    }


def _organizations_for_location(region_name, territory_name):
    region_keys = {slugify(region_name), _normalize_text(region_name)}
    territory_keys = {slugify(territory_name), _normalize_text(territory_name)}
    organizations = []
    try:
        for document in _mongo_docs('organizations', [('Nome', 1)]):
            payload = _organization_payload(document)
            region_matches = _slug_match_values(payload['regioes'])
            territory_matches = _slug_match_values(payload['territorios'])
            if region_keys.intersection(region_matches) or territory_keys.intersection(territory_matches):
                organizations.append(payload)
    except BotMongoUnavailable:
        return []
    return organizations


@ensure_csrf_cookie  # edição inline (wiki) lê o csrftoken do cookie
def regiao_detail_view(request, slug):
    regiao = get_object_or_404(TbRegiao, slug=slug)
    if regiao.camada > 0 and not request.user.is_staff:
        raise Http404("Região não encontrada")

    
    marker = TbMapMarker.objects.filter(nome=regiao.nome).first()

    
    if not request.user.is_staff:
        all_regioes = TbRegiao.objects.filter(camada=0).order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.filter(camada=0)}
    else:
        all_regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.all()}
    territorios = {}
    for r in all_regioes:
        terr = r.territorio or 'Sem território'
        territorios.setdefault(terr, []).append(r)
    territory_groups = []
    client_regions = []
    client_territories = {}

    for name, items in territorios.items():
        territory_obj = territory_objects.get(name) or next((t for t in territory_objects.values() if _normalize_text(t.nome) == _normalize_text(name)), None)
        display_name = _display_territory(name)
        color = territory_obj.cor_hex if territory_obj and territory_obj.cor_hex else _territory_color(name)
        display_color = _get_display_color(color)
        contrast = _get_contrast_color(color)
        image_url = _asset_url(territory_obj.imagem_url) if territory_obj and territory_obj.imagem_url else _asset_url(getattr(items[0], 'brasao_url', None) if items else None)
        territory_topics = _parse_lore_topics(territory_obj.lore_markdown or '') if territory_obj else []
        client_territories[name] = {
            'type': 'territory',
            'nome': name,
            'display_nome': display_name,
            'slug': territory_obj.slug if territory_obj else slugify(name),
            'id': territory_obj.id_territorio if territory_obj else None,
            'color': color,
            'display_color': display_color,
            'contrast': contrast,
            'imagem_url': image_url,
            'raw_imagem_url': territory_obj.imagem_url if territory_obj else '',
            'descricao_breve': territory_obj.descricao_breve if territory_obj else '',
            'lore_markdown': territory_obj.lore_markdown if territory_obj else '',
            'topics': territory_topics,
            'fallback_text': f'A lore de {display_name} ainda não foi escrita.',
            'stats': {
                'riqueza_natural': territory_obj.riqueza_natural if territory_obj else 0,
                'riqueza_monetaria': territory_obj.riqueza_monetaria if territory_obj else 0,
                'poder_militar': territory_obj.poder_militar if territory_obj else 0,
                'desenvolvimento_tecnologico': territory_obj.desenvolvimento_tecnologico if territory_obj else 0,
                'estabilidade_politica_interna': territory_obj.estabilidade_politica_interna if territory_obj else 0,
                'ameacas_externas': territory_obj.ameacas_externas if territory_obj else 0,
                'diplomacia': territory_obj.diplomacia if territory_obj else 0,
                'manipulacao_trama': territory_obj.manipulacao_trama if territory_obj else 0,
            }
        }
        territory_groups.append({
            'nome': name,
            'display_nome': display_name,
            'color': color,
            'display_color': display_color,
            'contrast': contrast,
            'regioes': items,
            'is_current': name == (regiao.territorio or 'Sem território'),
        })
        for item in items:
            client_regions.append({
                'type': 'region',
                'id': item.id_regiao,
                'nome': item.nome,
                'slug': item.slug,
                'territorio': item.territorio or 'Sem território',
                'display_territory': _display_territory(item.territorio),
                'color': color,
                'contrast': contrast,
                'imagem_url': _asset_url(item.brasao_url) if getattr(item, 'brasao_url', None) else image_url,
                'raw_imagem_url': getattr(item, 'brasao_url', '') or '',
                'mapa_url': _asset_url(item.mapa_url) if getattr(item, 'mapa_url', None) else '',
                'raw_mapa_url': getattr(item, 'mapa_url', '') or '',
                'side_image_url': _asset_url(item.mapa_url) if getattr(item, 'mapa_url', None) else image_url,
                'territory_image_url': image_url,
                'etiquetas_adicionais': item.etiquetas_adicionais or '',
                'descricao_breve': '',
                'lore_markdown': item.lore_markdown or '',
                'categoria': item.categoria or 'cidade',
                'topics': _parse_lore_topics(item.lore_markdown or ''),
                'fallback_text': 'Use "Editar região" para adicionar a lore desta região.' if request.user.is_staff else 'A lore desta região ainda não foi escrita.',
                'url': reverse('regiao_detail', kwargs={'slug': item.slug}),
                'stats': {
                    'movimentacoes_economicas': item.movimentacoes_economicas,
                    'poder_militar': item.poder_militar,
                    'desenvolvimento_tecnologico': item.desenvolvimento_tecnologico,
                    'estabilidade_politica_interna': item.estabilidade_politica_interna,
                    'ameacas_externas': item.ameacas_externas,
                    'densidade_populacional': item.densidade_populacional,
                    'tolerancia_estrangeiros': item.tolerancia_estrangeiros,
                    'manipulacao_trama': item.manipulacao_trama,
                    'ameacas_internas': item.ameacas_internas,
                    'nivel_periculosidade': item.nivel_periculosidade,
                    'recursos_naturais': item.recursos_naturais,
                    'recursos_magicos': item.recursos_magicos,
                    'diversidade_criaturas': item.diversidade_criaturas,
                }
            })

    
    lore_topics = _parse_lore_topics(regiao.lore_markdown or '')
    territorio_obj = TbTerritorio.objects.filter(nome__iexact=regiao.territorio).first()

    t_color = territorio_obj.cor_hex if territorio_obj and territorio_obj.cor_hex else _territory_color(regiao.territorio)
    t_display_color = _get_display_color(t_color)
    t_contrast = _get_contrast_color(t_color)

    context = {
        'regiao': regiao,
        'imagem_url': _asset_url(regiao.brasao_url) if getattr(regiao, 'brasao_url', None) else _asset_url(territorio_obj.imagem_url if territorio_obj else None),
        'brasao_url': _asset_url(regiao.brasao_url) if regiao.brasao_url else None,
        'side_image_url': _asset_url(regiao.mapa_url) if regiao.mapa_url else (_asset_url(territorio_obj.imagem_url) if territorio_obj and territorio_obj.imagem_url else _asset_url(None)),
        'territory_image_url': _asset_url(territorio_obj.imagem_url) if territorio_obj and territorio_obj.imagem_url else _asset_url(None),
        'display_territory': _display_territory(regiao.territorio),
        'territory_color': t_color,
        'territory_display_color': t_display_color,
        'territory_contrast': t_contrast,
        'marker': marker,
        'territorios': territorios,
        'territory_groups': territory_groups,
        'lore_topics': lore_topics,
        'client_regions': client_regions,
        'client_territories': client_territories,
        'current_region_slug': regiao.slug,
        'current_territory_name': regiao.territorio or 'Sem território',
        'organizations': _organizations_for_location(regiao.nome, regiao.territorio or ''),
        'can_edit_wiki': request.user.is_staff,
        'categoria_choices': TbMapMarker.PIN_ICON_CHOICES,
    }
    return render(request, 'home/pages/regiao_detail.html', context)


def _region_payload(region):
    return {
        'id': region.id_regiao,
        'nome': region.nome,
        'slug': region.slug,
        'lore_markdown': region.lore_markdown or '',
        'territorio': region.territorio or '',
        'categoria': region.categoria or 'cidade',
        'brasao_url': region.brasao_url or '',
        'mapa_url': region.mapa_url or '',
        'etiquetas_adicionais': region.etiquetas_adicionais or '',
        'type': 'region',
        'stats': {
            'movimentacoes_economicas': region.movimentacoes_economicas,
            'poder_militar': region.poder_militar,
            'desenvolvimento_tecnologico': region.desenvolvimento_tecnologico,
            'estabilidade_politica_interna': region.estabilidade_politica_interna,
            'ameacas_externas': region.ameacas_externas,
            'densidade_populacional': region.densidade_populacional,
            'tolerancia_estrangeiros': region.tolerancia_estrangeiros,
            'manipulacao_trama': region.manipulacao_trama,
            'ameacas_internas': region.ameacas_internas,
            'nivel_periculosidade': region.nivel_periculosidade,
        }
    }


@staff_member_required
@require_POST
def wiki_create_region(request):
    data = _json_body(request)
    validate_no_sql_danger(data, 'regiao')

    nome = (data.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'error': 'Nome é obrigatório.'}, status=400)

    slug = slugify(nome)
    if not slug:
        return JsonResponse({'ok': False, 'error': 'Não foi possível gerar slug do nome.'}, status=400)

    
    candidate = slug
    counter = 2
    while TbRegiao.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    slug = candidate

    valid_categorias = dict(TbMapMarker.PIN_ICON_CHOICES)

    region = TbRegiao.objects.create(
        nome=nome,
        slug=slug,
        lore_markdown=(data.get('lore_markdown') or '').strip() or None,
        territorio=(data.get('territorio') or '').strip() or None,
        categoria=data.get('categoria') if data.get('categoria') in valid_categorias else 'cidade',
        brasao_url=(data.get('brasao_url') or '').strip() or None,
        mapa_url=(data.get('mapa_url') or '').strip() or None,
        etiquetas_adicionais=(data.get('etiquetas_adicionais') or '').strip() or None,
    )
    _log_wiki_creation(request, region, f"Criação inline de região: {region.nome}")
    return JsonResponse({'ok': True, 'region': _region_payload(region), 'redirect': f'/mundo/regioes/{region.slug}/'})


@staff_member_required
@require_POST
def wiki_update_region(request, region_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'regiao')
    region = get_object_or_404(TbRegiao, pk=region_id)

    valid_categorias = dict(TbMapMarker.PIN_ICON_CHOICES)

    region.nome = (data.get('nome') or region.nome).strip()


    region.lore_markdown = data.get('lore_markdown') if 'lore_markdown' in data else region.lore_markdown
    region.territorio = (data.get('territorio') or '').strip() or None
    region.categoria = data.get('categoria') if data.get('categoria') in valid_categorias else region.categoria
    region.brasao_url = (data.get('brasao_url') or '').strip() or None
    region.mapa_url = (data.get('mapa_url') or '').strip() or None
    region.etiquetas_adicionais = (data.get('etiquetas_adicionais') or '').strip() or None

    region.movimentacoes_economicas = int(data.get('movimentacoes_economicas') or region.movimentacoes_economicas)
    region.poder_militar = int(data.get('poder_militar') or region.poder_militar)
    region.desenvolvimento_tecnologico = int(data.get('desenvolvimento_tecnologico') or region.desenvolvimento_tecnologico)
    region.estabilidade_politica_interna = int(data.get('estabilidade_politica_interna') or region.estabilidade_politica_interna)
    region.ameacas_externas = int(data.get('ameacas_externas') or region.ameacas_externas)
    region.densidade_populacional = int(data.get('densidade_populacional') or region.densidade_populacional)
    region.tolerancia_estrangeiros = int(data.get('tolerancia_estrangeiros') or region.tolerancia_estrangeiros)
    region.manipulacao_trama = int(data.get('manipulacao_trama') or region.manipulacao_trama)
    region.ameacas_internas = int(data.get('ameacas_internas') or region.ameacas_internas)
    region.nivel_periculosidade = int(data.get('nivel_periculosidade') or region.nivel_periculosidade)

    region.save()
    _log_wiki_edit(request, region, f"Edição inline de região: {region.nome}")
    return JsonResponse({'ok': True, 'region': _region_payload(region)})

@staff_member_required
@require_POST
def wiki_update_territory(request, territory_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'territorio')
    territory = get_object_or_404(TbTerritorio, pk=territory_id)

    territory.nome = (data.get('nome') or territory.nome).strip()
    territory.imagem_url = (data.get('imagem_url') or '').strip() or None
    territory.descricao_breve = (data.get('descricao_breve') or '').strip() or None
    territory.lore_markdown = (data.get('lore_markdown') or '').strip() or None
    
    if 'coordenadas_poligono' in data:
        territory.coordenadas_poligono = data.get('coordenadas_poligono')

    territory.riqueza_natural = int(data.get('riqueza_natural') or 0)
    territory.riqueza_monetaria = int(data.get('riqueza_monetaria') or 0)
    territory.poder_militar = int(data.get('poder_militar') or 0)
    territory.desenvolvimento_tecnologico = int(data.get('desenvolvimento_tecnologico') or 0)
    territory.estabilidade_politica_interna = int(data.get('estabilidade_politica_interna') or 0)
    territory.ameacas_externas = int(data.get('ameacas_externas') or 0)
    territory.diplomacia = int(data.get('diplomacia') or 0)
    territory.manipulacao_trama = int(data.get('manipulacao_trama') or 0)

    territory.save()
    _log_wiki_edit(request, territory, f"Edição inline de território: {territory.nome}")
    return JsonResponse({'ok': True, 'redirect': f'/mundo/regioes/?territory={territory.slug}'})


@staff_member_required
@require_POST
def wiki_update_marker_position(request, marker_id):
    
    data = _json_body(request)
    marker = get_object_or_404(TbMapMarker, pk=marker_id)

    try:
        marker.lat = float(data.get('lat', marker.lat))
        marker.lng = float(data.get('lng', marker.lng))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'lat/lng inválidos.'}, status=400)

    marker.save()
    _log_wiki_edit(request, marker, f"Edição inline de posição de marcador: {marker.nome}")
    return JsonResponse({'ok': True, 'marker': {'id': marker.id_marker, 'lat': marker.lat, 'lng': marker.lng}})


@staff_member_required
@require_POST
def wiki_batch_save_map(request):
    
    data = _json_body(request)
    validate_no_sql_danger(data, 'batch_save')
    
    import traceback
    try:
        with transaction.atomic():
            
            for m_data in data.get('markers', []):
                m_id = m_data.get('id')
                if m_id in ['undefined', 'null', '']:
                    m_id = None
                nome = m_data.get('nome', '').strip()
                if not nome: continue
                
                lat = float(m_data.get('lat', 0))
                lng = float(m_data.get('lng', 0))
                categoria = m_data.get('categoria', 'cidade')
                territorio = m_data.get('territorio')
                camada = int(m_data.get('camada', 0))
                
                marker = None
                original_name = None
                if m_id:
                    marker = TbMapMarker.objects.filter(pk=m_id).first()
                    if marker:
                        original_name = marker.nome
                
                
                if not marker:
                    marker = TbMapMarker.objects.filter(nome=nome).first()

                if not marker:
                    
                    
                    existing = TbMapMarker.objects.filter(nome=nome).first()
                    if existing:
                        marker = existing
                    else:
                        marker = TbMapMarker.objects.create(nome=nome, lat=lat, lng=lng, categoria=categoria, territorio=territorio, camada=camada)
                        
                        r_obj = TbRegiao.objects.filter(nome=nome).first()
                        if not r_obj:
                            new_slug = slugify(nome) or 'unnamed'
                            if TbRegiao.objects.filter(slug=new_slug).exists():
                                import uuid
                                new_slug += f"-{uuid.uuid4().hex[:6]}"
                            TbRegiao.objects.create(
                                nome=nome,
                                slug=new_slug,
                                categoria=categoria,
                                territorio=territorio,
                                camada=camada
                            )
                
                
                marker.nome = nome 
                marker.lat = lat
                marker.lng = lng
                marker.categoria = categoria
                marker.territorio = territorio
                marker.camada = camada
                marker.save()
                _log_wiki_edit(request, marker, f"Marcador de mapa salvo via lote: {marker.nome}")
                _mongo_upsert_site_document('map_markers', 'Id_Marker', marker.id_marker, {
                    'Nome': marker.nome,
                    'Latitude': marker.lat,
                    'Longitude': marker.lng,
                    'Categoria': marker.categoria,
                    'Territorio': marker.territorio,
                    'Camada': marker.camada,
                })
                
                
                search_name = original_name if original_name else nome
                region = TbRegiao.objects.filter(nome=search_name).first()
                if region:
                    region.nome = nome
                    new_slug = slugify(nome) or 'unnamed'
                    if TbRegiao.objects.filter(slug=new_slug).exclude(pk=region.pk).exists():
                        import uuid
                        new_slug += f"-{uuid.uuid4().hex[:6]}"
                    region.slug = new_slug
                    region.categoria = categoria
                    region.territorio = territorio
                    region.camada = camada
                    region.save()
                    _log_wiki_edit(request, region, f"Região de mapa salva via lote: {region.nome}")
                    _mongo_upsert_site_document('regions', 'Id_Regiao', region.id_regiao, {
                        'Nome': region.nome,
                        'Slug': region.slug,
                        'Categoria': region.categoria,
                        'Territorio': region.territorio,
                        'LoreMarkdown': region.lore_markdown,
                        'BrasaoUrl': region.brasao_url,
                        'MapaUrl': region.mapa_url,
                        'EtiquetasAdicionais': region.etiquetas_adicionais,
                        'Camada': region.camada,
                    })
                else:
                    
                    r_obj = TbRegiao.objects.filter(nome=nome).first()
                    if not r_obj:
                        new_slug = slugify(nome) or 'unnamed'
                        if TbRegiao.objects.filter(slug=new_slug).exists():
                            import uuid
                            new_slug += f"-{uuid.uuid4().hex[:6]}"
                        r_obj = TbRegiao.objects.create(nome=nome, slug=new_slug, camada=camada)
                    r_obj.categoria = categoria
                    r_obj.territorio = territorio
                    r_obj.camada = camada
                    r_obj.save()
                    _log_wiki_edit(request, r_obj, f"Região de mapa criada/salva via lote: {r_obj.nome}")
                    _mongo_upsert_site_document('regions', 'Id_Regiao', r_obj.id_regiao, {
                        'Nome': r_obj.nome,
                        'Slug': r_obj.slug,
                        'Categoria': r_obj.categoria,
                        'Territorio': r_obj.territorio,
                        'LoreMarkdown': r_obj.lore_markdown,
                        'BrasaoUrl': r_obj.brasao_url,
                        'MapaUrl': r_obj.mapa_url,
                        'EtiquetasAdicionais': r_obj.etiquetas_adicionais,
                        'Camada': r_obj.camada,
                    })
                    
            
            for t_data in data.get('territories', []):
                t_id = t_data.get('id')
                if not t_id or t_id in ['undefined', 'null', '']: continue
                territory = get_object_or_404(TbTerritorio, pk=t_id)
                modified = False
                if 'coordenadas_poligono' in t_data:
                    territory.coordenadas_poligono = t_data.get('coordenadas_poligono')
                    modified = True
                if 'camada' in t_data:
                    territory.camada = int(t_data.get('camada', 0))
                    modified = True
                if modified:
                    territory.save()
                    _log_wiki_edit(request, territory, f"Território de mapa salvo via lote: {territory.nome}")
                    _mongo_upsert_site_document('territories', 'Id_Territorio', territory.id_territorio, {
                        'Nome': territory.nome,
                        'Slug': territory.slug,
                        'DescricaoBreve': territory.descricao_breve,
                        'ImagemUrl': territory.imagem_url,
                        'CoordenadasPoligono': territory.coordenadas_poligono,
                        'CorHex': territory.cor_hex,
                        'LoreMarkdown': territory.lore_markdown,
                        'Camada': territory.camada,
                    })
                    
        return JsonResponse({'ok': True})
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open('batch_save_error.log', 'w') as f:
            f.write(error_msg)
        print("ERROR IN BATCH SAVE:", error_msg)
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)




@ensure_csrf_cookie  # edição inline (wiki) lê o csrftoken do cookie
def talentos_view(request):



    try:
        talentos_docs = _mongo_docs('talents', [('Nome', 1)])
        tipo_display = dict(TbTalento.TIPO_CHOICES)
        etiqueta_display = dict(TbTalento.ETIQUETA_CHOICES)
        talentos_lista = []
        for t in talentos_docs:
            atributos = []
            if t.get('Atrib_Forca'):
                atributos.append('Forca')
            if t.get('Atrib_Destreza'):
                atributos.append('Destreza')
            if t.get('Atrib_Constituicao'):
                atributos.append('Constituicao')
            if t.get('Atrib_Inteligencia'):
                atributos.append('Inteligencia')
            if t.get('Atrib_Sabedoria'):
                atributos.append('Sabedoria')
            if t.get('Atrib_Carisma'):
                atributos.append('Carisma')

            tipo = t.get('Tipo') or 'geral'
            etiqueta = t.get('Etiqueta') or 'combate'
            talentos_lista.append({
                'id': t.get('Id_Talento'),
                'nome': t.get('Nome') or '',
                'slug': t.get('Slug') or '',
                'tipo': tipo_display.get(tipo, tipo),
                'tipo_key': tipo,
                'etiqueta': etiqueta_display.get(etiqueta, etiqueta),
                'etiqueta_key': etiqueta,
                'etiquetas_adicionais': t.get('EtiquetasAdicionais') or '',
                'tags_json': t.get('TagsJSON') or [],
                'pre_requisito': t.get('PreRequisito') or 'Nenhum',
                'atributos_str': ', '.join(atributos) if atributos else 'Nenhum',
                'atrib_forca': bool(t.get('Atrib_Forca')),
                'atrib_destreza': bool(t.get('Atrib_Destreza')),
                'atrib_constituicao': bool(t.get('Atrib_Constituicao')),
                'atrib_inteligencia': bool(t.get('Atrib_Inteligencia')),
                'atrib_sabedoria': bool(t.get('Atrib_Sabedoria')),
                'atrib_carisma': bool(t.get('Atrib_Carisma')),
                'descricao': t.get('Descricao') or '',
            })
        return render(request, 'home/pages/talentos.html', {
            'json_talentos': talentos_lista,
            'can_edit_wiki': request.user.is_staff,
            'talent_tipo_choices': TbTalento.TIPO_CHOICES,
            'talent_etiqueta_choices': TbTalento.ETIQUETA_CHOICES,
        })
    except BotMongoUnavailable:
        pass

    talentos_db = TbTalento.objects.all().order_by('nome')
    talentos_lista = []

    for t in talentos_db:
        atributos = []
        if t.atrib_forca:
            atributos.append('Forca')
        if t.atrib_destreza:
            atributos.append('Destreza')
        if t.atrib_constituicao:
            atributos.append('Constituicao')
        if t.atrib_inteligencia:
            atributos.append('Inteligencia')
        if t.atrib_sabedoria:
            atributos.append('Sabedoria')
        if t.atrib_carisma:
            atributos.append('Carisma')

        talentos_lista.append(_talent_payload(t))

    context = {
        'json_talentos': talentos_lista,
        'can_edit_wiki': request.user.is_staff,
        'talent_tipo_choices': TbTalento.TIPO_CHOICES,
        'talent_etiqueta_choices': TbTalento.ETIQUETA_CHOICES,
    }
    return render(request, 'home/pages/talentos.html', context)


@ensure_csrf_cookie  # edição inline (wiki) lê o csrftoken do cookie
def opcoes_view(request):
    try:
        opcoes_docs = _mongo_docs('options', [('Nome', 1)])
        opcoes_lista = []
        for op in opcoes_docs:
            opcoes_lista.append({
                'id': op.get('Id_Opcao'),
                'nome': op.get('Nome') or '',
                'slug': op.get('Slug') or '',
                'tipo': op.get('Tipo') or '',
                'descricao': op.get('Descricao') or '',
                'pre_requisito': op.get('PreRequisito') or '',
                'etiquetas_adicionais': op.get('EtiquetasAdicionais') or '',
                'tags_json': op.get('TagsJSON') or [],
            })
        return render(request, 'home/pages/opcoes.html', {
            'json_opcoes': opcoes_lista,
            'can_edit_wiki': request.user.is_staff,
        })
    except BotMongoUnavailable:
        pass

    opcoes_docs = TbOpcaojogo.objects.all().order_by('nome')
    opcoes_lista = []
    for op in opcoes_docs:
        opcoes_lista.append({
            'id': op.id_opcao,
            'nome': op.nome,
            'slug': op.slug,
            'tipo': op.tipo,
            'descricao': op.descricao or '',
            'pre_requisito': op.pre_requisito or '',
            'etiquetas_adicionais': op.etiquetas_adicionais or '',
            'tags_json': op.tags_json or [],
        })

    context = {
        'json_opcoes': opcoes_lista,
        'can_edit_wiki': request.user.is_staff,
    }
    return render(request, 'home/pages/opcoes.html', context)


def _catalog_list(key, mapper, sort_field='Nome'):
    try:
        documents = _mongo_docs(key, [(sort_field, 1)])
    except BotMongoUnavailable as exc:
        return [], str(exc)
    return [mapper(document) for document in documents], ''


def _background_payload(document):
    name = _doc_value(document, ['Nome', 'nome', 'Name', 'name'])
    return {
        'nome': name,
        'slug': _doc_value(document, ['Slug', 'slug'], slugify(name)),
        'tipo': _doc_value(document, ['Tipo', 'tipo'], 'Antecedente'),
        'tags': _split_catalog_list(_doc_value(document, ['Tags', 'tags', 'EtiquetasAdicionais'])),
        'resumo': _doc_value(document, ['Resumo', 'resumo', 'summary']),
        'pre_requisito': _doc_value(document, ['PreRequisito', 'Prerequisito', 'PréRequisito', 'pre_requisito']),
        'proficiencias': _split_catalog_list(_doc_value(document, ['Proficiencias', 'Proficiências', 'proficiencias'])),
        'idiomas': _split_catalog_list(_doc_value(document, ['Idiomas', 'idiomas'])),
        'equipamento': _doc_value(document, ['Equipamento', 'equipamento']),
        'descricao': _doc_value(document, ['Descricao', 'Descrição', 'descricao', 'description']),
        'meta': {},
    }


def _spell_payload(document):
    name = _doc_value(document, ['Nome', 'nome', 'Name', 'name'])
    level = _doc_value(document, ['Nivel', 'Nível', 'level'], 0)
    level_label = 'Truque' if str(level) == '0' else f'Nivel {level}'
    return {
        'nome': name,
        'slug': _doc_value(document, ['Slug', 'slug'], slugify(name)),
        'tipo': _doc_value(document, ['Escola', 'escola', 'school'], 'Magia'),
        'tags': (
            [level_label]
            + _split_catalog_list(_doc_value(document, ['Classes', 'classes']))
            + _split_catalog_list(_doc_value(document, ['Subclasses', 'subclasses']))
            + _split_catalog_list(_doc_value(document, ['TagsJSON', 'Tags', 'tags']))
        ),
        'resumo': _doc_value(document, ['Resumo', 'resumo']),
        'descricao': _doc_value(document, ['Descricao', 'Descrição', 'descricao', 'description']),
        'meta': {
            'Nivel': level_label,
            'Tempo de Conjuração': _doc_value(document, ['CastingTime', 'casting_time']),
            'Ritual': 'Sim' if _doc_value(document, ['Ritual', 'ritual'], False) else 'Nao',
            'Concentração': 'Sim' if _doc_value(document, ['Concentracao', 'Concentração', 'concentration'], False) else 'Nao',
            'Duração': _doc_value(document, ['Duracao', 'Duração', 'duration']),
            'Alcance': _doc_value(document, ['Alcance', 'range']),
            'Componentes': ', '.join(_split_catalog_list(_doc_value(document, ['Componentes', 'components']))),
            'Em níveis superiores': _doc_value(document, ['EmNiveisSuperiores', 'higher_levels']),
        },
    }


def _bestiary_payload(document):
    name = _doc_value(document, ['Nome', 'nome', 'Name', 'name'])
    return {
        'nome': name,
        'slug': _doc_value(document, ['Slug', 'slug'], slugify(name)),
        'tipo': _doc_value(document, ['Tipo', 'tipo', 'CreatureType'], 'Criatura'),
        'tags': [
            _doc_value(document, ['Tamanho', 'tamanho', 'Size']),
            _doc_value(document, ['Dificuldade', 'ND', 'CR', 'cr']),
            _doc_value(document, ['Tendencia', 'Tendência', 'alignment']),
        ] + _split_catalog_list(_doc_value(document, ['Tags', 'tags'])),
        'resumo': _doc_value(document, ['Resumo', 'resumo']),
        'descricao': _doc_value(document, ['Descricao', 'Descrição', 'descricao', 'description']),
        'meta': {
            'CA': _doc_value(document, ['CA', 'ClasseArmadura', 'armor_class']),
            'PV': _doc_value(document, ['PV', 'PontosVida', 'hit_points']),
            'Deslocamento': _doc_value(document, ['Deslocamento', 'speed']),
            'Atributos': _doc_value(document, ['Atributos', 'attributes']),
            'Salvaguardas': _doc_value(document, ['Salvaguardas', 'saving_throws']),
            'Perícias': _doc_value(document, ['Pericias', 'Perícias', 'skills']),
            'Resistências': _doc_value(document, ['Resistencias', 'Resistências', 'resistances']),
            'Imunidades': _doc_value(document, ['Imunidades', 'immunities']),
            'Sentidos': _doc_value(document, ['Sentidos', 'senses']),
            'Idiomas': _doc_value(document, ['Idiomas', 'languages']),
            'XP': _doc_value(document, ['XP', 'xp']),
        },
    }


def _organization_catalog_payload(document):
    payload = _organization_payload(document)
    return {
        'nome': payload['nome'],
        'slug': payload['slug'],
        'tipo': payload['tipo'],
        'tags': payload['tags'] + payload['regioes'] + payload['territorios'],
        'resumo': payload['sede'],
        'descricao': payload['descricao'],
        'meta': {
            'Sede': payload['sede'],
            'Regiões': ', '.join(payload['regioes']),
            'Territórios': ', '.join(payload['territorios']),
            'Liderança': payload['lideranca'],
            'Aliados': ', '.join(payload['aliados']),
            'Inimigos': ', '.join(payload['inimigos']),
        },
    }


def _render_catalog(request, title, subtitle, kind, key, mapper):
    items, mongo_error = _catalog_list(key, mapper)
    return render(request, 'home/pages/catalogo_mongo.html', {
        'title': title,
        'subtitle': subtitle,
        'kind': kind,
        'items': items,
        'mongo_error': mongo_error,
        'can_edit_wiki': request.user.is_staff,
    })


def antecedentes_view(request):
    from .models import TbAntecedente
    
    backgrounds = TbAntecedente.objects.all().order_by('nome')
    items = []
    for bg in backgrounds:
        tags = [t.strip() for t in (bg.etiquetas_adicionais or '').split(',') if t.strip()]
        profs = [p.strip() for p in (bg.proficiencias or '').split(',') if p.strip()]
        langs = [l.strip() for l in (bg.idiomas or '').split(',') if l.strip()]
        
        items.append({
            'nome': bg.nome,
            'slug': bg.slug,
            'tipo': bg.tipo,
            'tags': tags,
            'resumo': bg.resumo,
            'pre_requisito': bg.pre_requisito,
            'proficiencias': profs,
            'idiomas': langs,
            'equipamento': bg.equipamento,
            'descricao': bg.descricao,
            'meta': {
                'Pré-requisito': bg.pre_requisito or '',
                'Proficiências': ', '.join(profs) if profs else '',
                'Idiomas': ', '.join(langs) if langs else '',
                'Equipamento': bg.equipamento or '',
            },
        })
        
    return render(request, 'home/pages/catalogo_mongo.html', {
        'title': 'Antecedentes',
        'subtitle': 'Origens, ofícios, vínculos e escolhas de história para personagens.',
        'kind': 'antecedentes',
        'items': items,
        'mongo_error': None,
        'can_edit_wiki': request.user.is_staff,
    })


def magias_view(request):
    """Catálogo de magias com filtros avançados (escola, nível, concentração, ritual) e
    modal de detalhe. Página dedicada (não usa o catálogo genérico)."""
    escolas = set()
    magias = []
    for m in TbMagia.objects.all().order_by('nivel', 'nome'):
        if m.escola:
            escolas.add(m.escola)
        magias.append({
            'id': m.id_magia, 'nome': m.nome, 'slug': m.slug, 'nivel': m.nivel,
            'nivel_label': 'Truque' if m.nivel == 0 else 'Nível %d' % m.nivel,
            'escola': m.escola or '', 'casting_time': m.casting_time or '',
            'alcance': m.alcance or '', 'componentes': m.componentes or '',
            'duracao': m.duracao or '', 'concentracao': bool(m.concentracao),
            'ritual': bool(m.ritual), 'classes': m.classes or '',
            'descricao': m.descricao or '', 'em_niveis': m.em_niveis_superiores or '',
            'tags': [t for t in _split_catalog_list(m.tags_json) if t],
        })
    return render(request, 'home/pages/magias.html', {
        'page_title': 'Magias', 'magias': magias,
        'escolas': sorted(escolas), 'niveis': list(range(0, 10)),
        'can_edit': request.user.is_staff,
        'magia_inicial': (request.GET.get('magia') or '').strip(),
    })


def idiomas_view(request):
    """Catálogo de Idiomas do mundo (TbIdioma)."""
    from .models import TbIdioma
    CAT = {'basal': 'Basal', 'derivado': 'Derivado', 'exotico': 'Exótico'}
    items = []
    for i in TbIdioma.objects.all().order_by('categoria', 'ordem', 'nome'):
        cat = CAT.get(i.categoria, (i.categoria or 'Basal').title())
        tags = [cat]
        if i.idioma_caracteristico:
            tags.append(i.idioma_caracteristico)
        if i.transcricao:
            tags.append(i.transcricao)
        items.append({
            'nome': i.nome,
            'slug': i.slug or slugify(i.nome),
            'tipo': cat,
            'tags': tags,
            'resumo': (f'Conhecido no mundo como "{i.nome_mundo}".' if i.nome_mundo else ''),
            'descricao': '',
            'meta': {
                'Nome no mundo': i.nome_mundo or '',
                'Categoria': cat,
                'Idioma análogo': i.idioma_caracteristico or '',
                'Sistema de escrita': i.transcricao or '',
            },
        })
    return render(request, 'home/pages/catalogo_mongo.html', {
        'title': 'Idiomas',
        'subtitle': 'Línguas de Bonfire Tales — basais, derivadas e exóticas.',
        'kind': 'idiomas',
        'items': items,
        'mongo_error': '',
        'can_edit_wiki': False,
    })


_ESCOLAS_MAGIA = {
    'Abjuração': 'Magias de proteção: barreiras, dissipação e banimento. Bloqueiam dano, anulam efeitos e selam ameaças.',
    'Adivinhação': 'Magias que revelam informação: enxergar à distância, descobrir segredos, prever o futuro e localizar o oculto.',
    'Conjuração': 'Magias que transportam e criam: invocar criaturas e objetos, teletransportar e materializar matéria de outros planos.',
    'Encantamento': 'Magias que afetam a mente: enfeitiçar, dominar, acalmar ou enlouquecer alvos, manipulando vontade e emoção.',
    'Evocação': 'Magias que manipulam energia bruta: dano elemental, luz e força — o arquétipo da magia ofensiva.',
    'Ilusão': 'Magias que enganam os sentidos e a mente: imagens falsas, invisibilidade, sons e disfarces.',
    'Necromancia': 'Magias que manipulam a vida e a morte: drenar vitalidade, comandar mortos-vivos e desafiar o fim.',
    'Transmutação': 'Magias que alteram propriedades: transformar criaturas, objetos e o ambiente, mudar forma, tamanho e matéria.',
}


def magias_escolas_view(request):
    """Catálogo das Escolas de Magia (agrupa TbMagia por escola)."""
    from collections import defaultdict
    por_escola = defaultdict(list)
    for m in TbMagia.objects.all().order_by('nivel', 'nome'):
        por_escola[(m.escola or 'Outras').strip()].append(m)
    items = []
    for esc in sorted(por_escola, key=lambda e: (e == 'Outras', e)):
        magias = por_escola[esc]
        por_nivel = defaultdict(list)
        for m in magias:
            por_nivel[m.nivel].append(m.nome)
        linhas = []
        for nv in sorted(por_nivel):
            rotulo = 'Truques' if nv == 0 else f'{nv}º Círculo'
            linhas.append(f'- **{rotulo}:** ' + ', '.join(sorted(por_nivel[nv])))
        blurb = _ESCOLAS_MAGIA.get(esc, '')
        descricao = ((blurb + '\n\n') if blurb else '') + '\n'.join(linhas)
        items.append({
            'nome': esc,
            'slug': slugify(esc),
            'tipo': 'Escola',
            'tags': [f'{len(magias)} magias'],
            'resumo': blurb,
            'descricao': descricao,
            'meta': {'Total de magias': str(len(magias))},
        })
    return render(request, 'home/pages/catalogo_mongo.html', {
        'title': 'Escolas de Magia',
        'subtitle': 'As oito escolas de magia e as magias que pertencem a cada uma.',
        'kind': 'escolas',
        'items': items,
        'mongo_error': '',
        'can_edit_wiki': False,
    })


def atualizacoes_view(request):
    """Notas de Atualização (changelog do sistema)."""
    notas = [
        {
            'versao': 'Junho/2026 — Essências & Talentos',
            'data': '2026-06-23',
            'itens': [
                'Essência Elemental, Dracônica, Nephilim e Vampirismo atualizadas para a versão final (mecânicas e descrições revisadas).',
                'Aferição completa dos talentos contra a fonte oficial; descrições e tags alinhadas.',
                'Bárbaro: a Fúria agora funciona com armas de arremesso; Adaptação Fisiológica (Coração Selvagem) concede Vantagem em vez do modificador de Constituição.',
                'Talentos Luchador e Brigão de Taverna: escalonamento do Golpe Desarmado Aprimorado (+1 quando o dano já é igual ou maior).',
            ],
        },
        {
            'versao': 'Junho/2026 — Ajustes de Magias',
            'data': '2026-06-23',
            'itens': [
                'Foco Arcano: Estrela Negra, Bosque Druídico, Selo do Portal, Globo de Invulnerabilidade, Proteção contra o Bem e o Mal e Laço dispensam o componente material.',
                'Fios Prateados (Silvery Barbs): a criatura afetada fica imune à magia até o início do próximo turno dela.',
                'Aliado Planar: custo material de 1.000 PO (consumível); invoca 1 Erínia, Deva ou Djinn por 1 dia.',
                'Lâmina de Chama Verde e Lâmina Trovejante passam a usar a versão do SCAG (combo com Lâmina das Sombras).',
                'Santuário do Pastor adicionado à lista de Druida. Magias vetadas removidas do catálogo.',
            ],
        },
    ]
    return render(request, 'home/pages/atualizacoes.html', {
        'page_title': 'Notas de Atualização',
        'notas': notas,
    })


_SB_TAM = {'T': 'Minúsculo', 'S': 'Pequeno', 'M': 'Médio', 'L': 'Grande', 'H': 'Enorme', 'G': 'Descomunal'}
_SB_ALIN = {'L': 'Leal', 'N': 'Neutro', 'C': 'Caótico', 'G': 'Bom', 'E': 'Mau',
            'U': 'sem alinhamento', 'A': 'qualquer alinhamento'}
_SB_AB = [('str', 'FOR'), ('dex', 'DES'), ('con', 'CON'), ('int', 'INT'), ('wis', 'SAB'), ('cha', 'CAR')]
_SB_TIPO = {'beast': 'besta', 'construct': 'construto', 'undead': 'morto-vivo', 'fiend': 'corruptor',
            'celestial': 'celestial', 'dragon': 'dragão', 'elemental': 'elemental', 'fey': 'feérico',
            'giant': 'gigante', 'humanoid': 'humanoide', 'monstrosity': 'aberração natural',
            'ooze': 'limo', 'plant': 'planta', 'aberration': 'aberração'}


def _sb_tipo_pt(t):
    return _SB_TIPO.get((t or '').strip().lower(), t or '')


def _sb_mod(score):
    try:
        return (int(score) - 10) // 2
    except (TypeError, ValueError):
        return 0


def _sb_sgn(n):
    return ('+%d' % n) if n >= 0 else ('%d' % n)


def _sb_entries(entries):
    """Achata 'entries' (5etools) em texto. Strings diretas; objetos/listas viram texto simples."""
    out = []
    for e in (entries or []):
        if isinstance(e, str):
            out.append(_clean_statblock_text(e))  # tokens 5etools + refs Bonfire
        elif isinstance(e, dict):
            if e.get('name') and e.get('entries'):
                out.append('**%s** %s' % (e['name'], _sb_entries(e['entries'])))
            elif e.get('entries'):
                out.append(_sb_entries(e['entries']))
            elif e.get('items'):
                out.append(' '.join(_sb_entries(e['items']).split('\n')))
        elif isinstance(e, list):
            out.append(_sb_entries(e))
    return '\n'.join(x for x in out if x)


def _sb_bloco(lista):
    """Cada habilidade (trait/action) vira um item ESTRUTURADO {nome, texto, tags}.
    `tags` = tags_json mecânicas DAQUELA habilidade, guardadas no próprio JSON da
    criatura (statblock entry) — NUNCA viram linha de habilidade no banco."""
    out = []
    for x in (lista or []):
        if not isinstance(x, dict):
            continue
        tags = x.get('tags') or x.get('tags_json') or []
        out.append({'nome': _clean_statblock_text(x.get('name', '')),
                    'texto': _sb_entries(x.get('entries')),
                    'tags': [t for t in tags if isinstance(t, str)]})
    return out


def _statblock_display(sb, criatura=None):
    """Normaliza o statblock 5etools num dict pronto p/ o card. Degrada com graça."""
    sb = sb or {}
    tam = sb.get('size')
    tam = _SB_TAM.get(tam[0] if isinstance(tam, list) and tam else tam, '') if tam else ''
    tp = sb.get('type')
    tipo = _sb_tipo_pt(tp.get('type') if isinstance(tp, dict) else (tp or ''))
    alin = sb.get('alignment') or []
    alin_txt = ', '.join(_SB_ALIN.get(a, str(a)) for a in alin) if isinstance(alin, list) else str(alin)
    # CA
    ac = sb.get('ac')
    if isinstance(ac, list) and ac:
        a0 = ac[0]
        ca = ('%s%s' % (a0.get('ac'), ' (%s)' % ', '.join(_clean_5et(x) for x in a0.get('from', [])) if a0.get('from') else '')
              if isinstance(a0, dict) else str(a0))
    else:
        ca = str(ac) if ac else (getattr(criatura, 'ca', '') or '')
    # PV
    hp = sb.get('hp')
    pv = ('%s%s' % (hp.get('average', ''), ' (%s)' % hp['formula'] if hp.get('formula') else '')
          if isinstance(hp, dict) else (str(hp) if hp else (getattr(criatura, 'pv', '') or '')))
    # deslocamento
    spd = sb.get('speed')
    if isinstance(spd, dict):
        partes = []
        for k, lbl in [('walk', ''), ('fly', 'voo'), ('swim', 'nado'), ('climb', 'escalada'), ('burrow', 'escavação')]:
            v = spd.get(k)
            if isinstance(v, dict):
                v = v.get('number')
            if v is not None:
                m = round(int(v) * 0.3, 1)
                partes.append(('%s %g m' % (lbl, m)).strip())
        desloc = ', '.join(partes)
    else:
        desloc = str(spd) if spd else ''
    # atributos + saves
    saves = sb.get('save') or {}
    abilities = []
    for en, sig in _SB_AB:
        sc = sb.get(en)
        if sc is None:
            continue
        mod = _sb_mod(sc)
        sv = saves.get(en)
        abilities.append({'sig': sig, 'score': sc, 'mod': _sb_sgn(mod),
                          'save': (sv if isinstance(sv, str) else _sb_sgn(mod))})
    skill = sb.get('skill') or {}
    skills = ', '.join('%s %s' % (k.capitalize(), v) for k, v in skill.items()) if isinstance(skill, dict) else ''

    def _join(v):
        if isinstance(v, list):
            return _clean_5et(', '.join(x if isinstance(x, str) else str(x.get('immune') or x.get('resist') or x) for x in v))
        return _clean_5et(str(v)) if v else ''
    return {
        'cabecalho': ('%s %s%s' % (tam, tipo, (', ' + alin_txt) if alin_txt else '')).strip(),
        'ca': ca, 'pv': pv, 'desloc': desloc, 'abilities': abilities,
        'saves': ', '.join('%s %s' % (k.upper(), v) for k, v in saves.items()) if isinstance(saves, dict) else '',
        'skills': skills, 'sentidos': _join(sb.get('senses')), 'passivo': sb.get('passive'),
        'idiomas': _join(sb.get('languages')), 'resist': _join(sb.get('resist')),
        'immune': _join(sb.get('immune')), 'vuln': _join(sb.get('vulnerable')),
        'cond_immune': _join(sb.get('conditionImmune')),
        'cr': str(sb.get('cr')) if sb.get('cr') else (getattr(criatura, 'nd', '') or ''),
        'traits': _sb_bloco(sb.get('trait')), 'actions': _sb_bloco(sb.get('action')),
        'bonus': _sb_bloco(sb.get('bonus')), 'reactions': _sb_bloco(sb.get('reaction')),
        'legendary': _sb_bloco(sb.get('legendary')),
    }


def _nd_valor(nd):
    """ND -> número p/ ordenar por dificuldade ('1/4'->0.25, '5'->5)."""
    nd = (nd or '').strip()
    if '/' in nd:
        try:
            a, b = nd.split('/', 1)
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return 999.0
    try:
        return float(nd)
    except ValueError:
        return 999.0


def bestiario_view(request):
    """Bestiário: criaturas oficiais + da comunidade, com statblock 5e renderizado.
    Filtros: origem (todas/oficial/comunidade), ND, e ordenação alfabética A→Z/Z→A."""
    from .models import TbBestiario
    from . import permissions as perms
    filtro = request.GET.get('f', '')
    nd_sel = request.GET.get('nd', '')
    ordem = request.GET.get('ord', 'az')
    is_staff = perms.is_staff_user(request.user)
    qs = TbBestiario.objects.select_related('autor')
    if filtro == 'oficial':
        qs = qs.filter(comunidade=False)
    elif filtro == 'comunidade':
        qs = qs.filter(comunidade=True)
    if nd_sel:
        qs = qs.filter(nd=nd_sel)
    criaturas = []
    for b in qs:
        criaturas.append({
            'id': b.id_criatura, 'nome': b.nome, 'slug': b.slug,
            'tipo': _sb_tipo_pt(b.tipo), 'nd': b.nd or '', 'tamanho': _SB_TAM.get(b.tamanho, b.tamanho or ''),
            'comunidade': b.comunidade, 'autor': b.autor.username if b.autor_id else None,
            'imagem': b.imagem_url or '',
            'sb': _statblock_display(b.statblock_json if isinstance(b.statblock_json, dict) else {}, b),
            'descricao': _clean_5et(b.descricao_markdown or ''),
            'pode_editar': is_staff or (b.comunidade and b.autor_id == request.user.id),
        })
    criaturas.sort(key=lambda c: c['nome'].lower(), reverse=(ordem == 'za'))
    nds_all = sorted({(x.nd or '').strip() for x in TbBestiario.objects.all() if (x.nd or '').strip()},
                     key=_nd_valor)
    return render(request, 'home/pages/bestiario.html', {
        'page_title': 'Bestiário',
        'criaturas': criaturas, 'filtro': filtro, 'nd_sel': nd_sel, 'ordem': ordem, 'nds': nds_all,
        'pode_criar': perms.is_mestre(request.user), 'is_staff': is_staff,
        'msg': request.GET.get('m'),
    })


def _parse_blocos(texto):
    """Textarea 'Nome | descrição | tag1, tag2' por linha → [{name, entries, tags}].
    O 3º campo são as tags_json MECÂNICAS daquela habilidade (guardadas no JSON da criatura)."""
    out = []
    for linha in (texto or '').splitlines():
        if not linha.strip():
            continue
        partes = [p.strip() for p in linha.split('|')]
        item = {'name': partes[0], 'entries': [partes[1]] if len(partes) > 1 and partes[1] else []}
        if len(partes) > 2 and partes[2]:
            tags = [t.strip() for t in partes[2].split(',') if t.strip()]
            if tags:
                item['tags'] = tags
        out.append(item)
    return out


def _blocos_para_texto(lista):
    """[{name, entries, tags}] → texto 'Nome | desc | tags' p/ preencher o textarea na edição."""
    linhas = []
    for x in (lista or []):
        if not isinstance(x, dict):
            continue
        nome = _clean_statblock_text(x.get('name', ''))
        desc = ' '.join(e for e in (x.get('entries') or []) if isinstance(e, str))
        tags = ', '.join(x.get('tags') or x.get('tags_json') or [])
        linha = nome
        if desc or tags:
            linha += ' | ' + desc
        if tags:
            linha += ' | ' + tags
        linhas.append(linha)
    return '\n'.join(linhas)


def _build_statblock(g):
    """Monta o statblock_json (schema 5etools + tags por habilidade) a partir do POST."""
    def num(k, default=10):
        try:
            return int(g(k))
        except (TypeError, ValueError):
            return default
    sb = {'name': (g('nome') or '').strip(), 'size': [g('tamanho') or 'M'],
          'type': {'type': g('tipo') or 'humanoid'}, 'alignment': [g('alinhamento') or 'N'],
          'ac': [{'ac': num('ca', 10)}], 'hp': {'average': num('pv', 1)},
          'speed': {'walk': num('desloc_ft', 30)}, 'cr': (g('nd') or '0').strip()}
    for en, _sig in _SB_AB:
        sb[en] = num(en, 10)
    if (g('idiomas') or '').strip():
        sb['languages'] = [s.strip() for s in g('idiomas').split(',') if s.strip()]
    if (g('sentidos') or '').strip():
        sb['senses'] = [s.strip() for s in g('sentidos').split(',') if s.strip()]
    if (g('passivo') or '').strip().isdigit():
        sb['passive'] = int(g('passivo'))
    tr, ac = _parse_blocos(g('tracos')), _parse_blocos(g('acoes'))
    if tr:
        sb['trait'] = tr
    if ac:
        sb['action'] = ac
    return sb


def _criatura_prefill(b):
    """Dados do form prontos p/ a edição (reverte o statblock_json em campos)."""
    sb = b.statblock_json if isinstance(b.statblock_json, dict) else {}
    spd = sb.get('speed', {})
    al = sb.get('alignment')
    return {
        'nome': b.nome, 'tipo': b.tipo or '', 'tamanho': b.tamanho or 'M', 'nd': b.nd or '',
        'alinhamento': (al[0] if isinstance(al, list) and al else (b.alinhamento or '')),
        'ca': b.ca or '', 'pv': b.pv or '', 'desloc_ft': spd.get('walk', '') if isinstance(spd, dict) else '',
        'abil': {en: sb.get(en, 10) for en, _ in _SB_AB},
        'idiomas': ', '.join(sb.get('languages') or []), 'sentidos': ', '.join(sb.get('senses') or []),
        'passivo': sb.get('passive') or '', 'tracos': _blocos_para_texto(sb.get('trait')),
        'acoes': _blocos_para_texto(sb.get('action')), 'descricao': b.descricao_markdown or '',
        'imagem_url': b.imagem_url or '',
    }


@login_required(login_url='/login/')
def bestiario_criar(request):
    """Mestres criam criaturas da COMUNIDADE; admins (staff) podem marcar OFICIAL."""
    from .models import TbBestiario
    from . import permissions as perms
    if not perms.is_mestre(request.user):
        raise Http404
    is_staff = perms.is_staff_user(request.user)
    if request.method == 'POST':
        g = request.POST.get
        nome = (g('nome') or '').strip()
        if not nome:
            return redirect(reverse('bestiario_criar') + '?e=nome')
        base = slugify(nome) or 'criatura'
        slug, i = base, 1
        while TbBestiario.objects.filter(slug=slug).exists():
            i += 1
            slug = '%s-%d' % (base, i)
        oficial = is_staff and g('oficial') == 'on'

        def num(k, d=10):
            try:
                return int(g(k))
            except (TypeError, ValueError):
                return d
        TbBestiario.objects.create(
            nome=nome, slug=slug, tipo=g('tipo') or None, tamanho=g('tamanho') or None,
            nd=(g('nd') or '').strip() or None, alinhamento=g('alinhamento') or None,
            source='BonfireTales' if oficial else 'Comunidade', ca=str(num('ca', 10)), pv=str(num('pv', 1)),
            statblock_json=_build_statblock(g), descricao_markdown=(g('descricao') or '').strip() or None,
            imagem_url=(g('imagem_url') or '').strip() or None,
            comunidade=not oficial, autor=request.user)
        return redirect(reverse('bestiario') + ('?m=criada&f=oficial' if oficial else '?m=criada&f=comunidade'))
    return render(request, 'home/pages/bestiario_criar.html', {'page_title': 'Nova Criatura', 'is_staff': is_staff})


@login_required(login_url='/login/')
def bestiario_editar(request, pk):
    """Edita uma criatura. Admin (staff) edita qualquer uma e alterna oficial/comunidade;
    mestre edita só as próprias da comunidade."""
    from .models import TbBestiario
    from . import permissions as perms
    b = TbBestiario.objects.filter(id_criatura=pk).first()
    if not b:
        raise Http404
    is_staff = perms.is_staff_user(request.user)
    if not (is_staff or (b.comunidade and b.autor_id == request.user.id)):
        raise Http404
    if request.method == 'POST':
        g = request.POST.get
        nome = (g('nome') or '').strip()
        if not nome:
            return redirect(reverse('bestiario_editar', args=[pk]) + '?e=nome')

        def num(k, d=10):
            try:
                return int(g(k))
            except (TypeError, ValueError):
                return d
        b.nome, b.tipo, b.tamanho = nome, g('tipo') or None, g('tamanho') or None
        b.nd, b.alinhamento = (g('nd') or '').strip() or None, g('alinhamento') or None
        b.ca, b.pv = str(num('ca', 10)), str(num('pv', 1))
        b.statblock_json = _build_statblock(g)
        b.descricao_markdown = (g('descricao') or '').strip() or None
        b.imagem_url = (g('imagem_url') or '').strip() or None
        if is_staff:
            b.comunidade = (g('oficial') != 'on')
            b.source = 'Comunidade' if b.comunidade else 'BonfireTales'
        b.save()
        return redirect(reverse('bestiario') + '?m=editada')
    return render(request, 'home/pages/bestiario_criar.html', {
        'page_title': 'Editar Criatura', 'is_staff': is_staff, 'editar': True,
        'criatura_id': b.id_criatura, 'oficial': not b.comunidade, 'pf': _criatura_prefill(b),
    })


@login_required(login_url='/login/')
@require_POST
def bestiario_excluir(request, pk):
    """Exclui uma criatura (autor da comunidade, ou staff em qualquer uma)."""
    from .models import TbBestiario
    from . import permissions as perms
    b = TbBestiario.objects.filter(id_criatura=pk).first()
    if b and (perms.is_staff_user(request.user) or (b.comunidade and b.autor_id == request.user.id)):
        b.delete()
    return redirect(reverse('bestiario') + '?m=excluida')


# ───────────────────────── Armadilhas e Perigos ─────────────────────────
def armadilhas_view(request):
    """Armadilhas/Perigos: oficiais (staff) + da comunidade (mestres). Filtro origem/ND + ordenação."""
    from .models import TbArmadilha
    from . import permissions as perms
    filtro = request.GET.get('f', '')
    nd_sel = request.GET.get('nd', '')
    ordem = request.GET.get('ord', 'az')
    is_staff = perms.is_staff_user(request.user)
    qs = TbArmadilha.objects.select_related('autor')
    if filtro == 'oficial':
        qs = qs.filter(comunidade=False)
    elif filtro == 'comunidade':
        qs = qs.filter(comunidade=True)
    if nd_sel:
        qs = qs.filter(nd=nd_sel)
    armadilhas = []
    for a in qs:
        armadilhas.append({
            'id': a.id_armadilha, 'nome': a.nome, 'tipo': a.tipo or '', 'nd': a.nd or '',
            'gatilho': a.gatilho or '', 'deteccao': a.deteccao or '', 'desarme': a.desarme or '',
            'save': ('%s CD %s' % (a.save_atributo, a.save_cd)) if (a.save_atributo and a.save_cd)
                    else (a.save_atributo or ''),
            'dano': a.dano or '', 'efeito': a.efeito or '', 'descricao': a.descricao_markdown or '',
            'comunidade': a.comunidade, 'autor': a.autor.username if a.autor_id else None,
            'pode_editar': is_staff or (a.comunidade and a.autor_id == request.user.id),
        })
    armadilhas.sort(key=lambda x: x['nome'].lower(), reverse=(ordem == 'za'))
    nds = sorted({(x.nd or '').strip() for x in TbArmadilha.objects.all() if (x.nd or '').strip()},
                 key=_nd_valor)
    return render(request, 'home/pages/armadilhas.html', {
        'page_title': 'Armadilhas e Perigos', 'armadilhas': armadilhas,
        'filtro': filtro, 'nd_sel': nd_sel, 'ordem': ordem, 'nds': nds,
        'pode_criar': perms.is_mestre(request.user), 'is_staff': is_staff,
        'msg': request.GET.get('m'),
    })


def _armadilha_apply(a, g, is_staff):
    """Preenche um TbArmadilha a partir do POST. Staff alterna oficial↔comunidade."""
    a.nome = (g('nome') or '').strip()
    a.tipo = (g('tipo') or '').strip() or None
    a.nd = (g('nd') or '').strip() or None
    a.gatilho = (g('gatilho') or '').strip() or None
    a.deteccao = (g('deteccao') or '').strip() or None
    a.desarme = (g('desarme') or '').strip() or None
    a.save_atributo = (g('save_atributo') or '').strip().upper() or None
    a.save_cd = (g('save_cd') or '').strip() or None
    a.dano = (g('dano') or '').strip() or None
    a.efeito = (g('efeito') or '').strip() or None
    a.descricao_markdown = (g('descricao') or '').strip() or None
    oficial = bool(is_staff and g('oficial') == 'on')
    a.comunidade = not oficial
    a.source = 'BonfireTales' if oficial else 'Comunidade'


@login_required(login_url='/login/')
def armadilha_criar(request):
    """Mestres criam armadilhas da COMUNIDADE; admins (staff) podem marcar OFICIAL."""
    from .models import TbArmadilha
    from . import permissions as perms
    if not perms.is_mestre(request.user):
        raise Http404
    is_staff = perms.is_staff_user(request.user)
    if request.method == 'POST':
        g = request.POST.get
        if not (g('nome') or '').strip():
            return redirect(reverse('armadilha_criar') + '?e=nome')
        base = slugify((g('nome') or '').strip()) or 'armadilha'
        slug, i = base, 1
        while TbArmadilha.objects.filter(slug=slug).exists():
            i += 1
            slug = '%s-%d' % (base, i)
        a = TbArmadilha(slug=slug, autor=request.user)
        _armadilha_apply(a, g, is_staff)
        a.save()
        oficial = not a.comunidade
        return redirect(reverse('mestre_armadilhas') + ('?m=criada&f=oficial' if oficial else '?m=criada&f=comunidade'))
    return render(request, 'home/pages/armadilha_criar.html', {'page_title': 'Nova Armadilha', 'is_staff': is_staff})


@login_required(login_url='/login/')
def armadilha_editar(request, pk):
    """Staff edita qualquer uma e alterna oficial↔comunidade; mestre edita só as próprias da comunidade."""
    from .models import TbArmadilha
    from . import permissions as perms
    a = TbArmadilha.objects.filter(id_armadilha=pk).first()
    if not a:
        raise Http404
    is_staff = perms.is_staff_user(request.user)
    if not (is_staff or (a.comunidade and a.autor_id == request.user.id)):
        raise Http404
    if request.method == 'POST':
        g = request.POST.get
        if not (g('nome') or '').strip():
            return redirect(reverse('armadilha_editar', args=[pk]) + '?e=nome')
        _armadilha_apply(a, g, is_staff)
        a.save()
        return redirect(reverse('mestre_armadilhas') + '?m=editada')
    return render(request, 'home/pages/armadilha_criar.html', {
        'page_title': 'Editar Armadilha', 'is_staff': is_staff, 'editar': True,
        'armadilha_id': a.id_armadilha, 'oficial': not a.comunidade, 'pf': a})


@login_required(login_url='/login/')
@require_POST
def armadilha_excluir(request, pk):
    """Exclui uma armadilha (autor da comunidade, ou staff em qualquer uma)."""
    from .models import TbArmadilha
    from . import permissions as perms
    a = TbArmadilha.objects.filter(id_armadilha=pk).first()
    if a and (perms.is_staff_user(request.user) or (a.comunidade and a.autor_id == request.user.id)):
        a.delete()
    return redirect(reverse('mestre_armadilhas') + '?m=excluida')


# ───────────────────────── Mercado de Mestre (Moedas de Mestragem) ─────────────────────────
def _perfil_mestre(user):
    from .models import UserProfile
    perfil = getattr(user, 'profile', None)
    if perfil is None:
        perfil, _ = UserProfile.objects.get_or_create(user=user)
    return perfil


def _creditar_mm(user, tipo, descricao, delta):
    """Credita/debita MM no perfil do mestre + registra no ledger. Em GANHO (delta>0)
    acumula `mm_ganhas_total` e concede 1 Moeda de Evento a cada 100 MM ganhas. Retorna o saldo."""
    from .models import TbTransacaoMestre
    perfil = _perfil_mestre(user)
    delta = int(delta)
    perfil.moedas_mestragem = int(perfil.moedas_mestragem or 0) + delta
    fields = ['moedas_mestragem']
    if delta > 0:
        antes = int(perfil.mm_ganhas_total or 0)
        perfil.mm_ganhas_total = antes + delta
        novas = (perfil.mm_ganhas_total // 100) - (antes // 100)
        if novas > 0:
            perfil.moedas_evento = int(perfil.moedas_evento or 0) + novas
            fields.append('moedas_evento')
        fields.append('mm_ganhas_total')
    perfil.save(update_fields=fields)
    TbTransacaoMestre.objects.create(mestre=user, tipo=tipo, descricao=(descricao or '')[:255],
                                     valor_mm=delta, saldo_mm=perfil.moedas_mestragem)
    return perfil.moedas_mestragem


@login_required(login_url='/login/')
def mercado_mestre_view(request):
    """Mercado de Mestre: saldo de MM, catálogo de recompensas, registro de aventuras,
    histórico, Rei da Colina e Mestre Ouro. Gated por is_mestre."""
    from .models import TbRecompensaMestre, TbReiDaColina
    from . import permissions as perms
    if not perms.is_mestre(request.user):
        raise Http404
    perfil = _perfil_mestre(request.user)
    rdc = TbReiDaColina.objects.select_related('holder').first()
    meus = [{'id': p.id_personagem, 'nome': p.nome}
            for p in request.user.personagens.filter(arquivado=False).only('id_personagem', 'nome')]
    return render(request, 'home/pages/mercado_mestre.html', {
        'page_title': 'Mercado de Mestre',
        'saldo': perfil.moedas_mestragem or 0,
        'moedas_evento': perfil.moedas_evento or 0,
        'recompensas': list(TbRecompensaMestre.objects.filter(ativo=True)),
        'aventuras': list(request.user.aventuras_mestradas.all()[:20]),
        'transacoes': list(request.user.transacoes_mm.all()[:30]),
        'rei_colina': rdc,
        'sou_rei': bool(rdc and rdc.holder_id == request.user.id),
        'mestre_ouro_ativo': perfil.mestre_ouro_ativo,
        'mestre_ouro_proximo': perfil.mestre_ouro_proximo_pgto,
        'meus_personagens': meus,
        'msg': request.GET.get('m'),
    })


@login_required(login_url='/login/')
@require_POST
def mestre_resgatar_braseiros(request):
    """Mestre gasta Moedas de Evento → braseiros (= BP do personagem) p/ um personagem seu."""
    from .models import TbPersonagem
    from . import permissions as perms
    from .character_engine import derive
    if not perms.is_mestre(request.user):
        raise Http404
    dest = reverse('mestre_mercado')
    perfil = _perfil_mestre(request.user)
    p = TbPersonagem.objects.filter(id_personagem=request.POST.get('personagem'), dono=request.user).first()
    if not p:
        return redirect(dest + '?m=sem_personagem')
    try:
        coins = max(1, int(request.POST.get('moedas') or 1))
    except (TypeError, ValueError):
        coins = 1
    coins = min(coins, int(perfil.moedas_evento or 0))
    if coins < 1:
        return redirect(dest + '?m=sem_evento')
    bp = derive(p)['bonus_proficiencia']
    bras = coins * bp
    perfil.moedas_evento = int(perfil.moedas_evento or 0) - coins
    perfil.save(update_fields=['moedas_evento'])
    p.braseiros = int(p.braseiros or 0) + bras
    p.save(update_fields=['braseiros', 'atualizado_em'])
    return redirect(dest + '?m=braseiros')


@login_required(login_url='/login/')
@require_POST
def mestre_registrar_aventura(request):
    """Registra uma mesa conduzida → credita recompensa_mm MM automaticamente."""
    from .models import TbAventuraMestre
    from . import permissions as perms
    if not perms.is_mestre(request.user):
        raise Http404
    g = request.POST.get
    nome = (g('nome') or '').strip()
    if not nome:
        return redirect(reverse('mestre_mercado') + '?m=nome')

    def _int(k):
        try:
            return max(0, int(g(k) or 0))
        except (TypeError, ValueError):
            return 0
    recompensa = _int('recompensa_mm')
    av = TbAventuraMestre.objects.create(
        mestre=request.user, nome=nome, data=(g('data') or None), jogadores=_int('jogadores'),
        recompensa_mm=recompensa, observacao=(g('observacao') or '').strip() or None)
    if recompensa > 0:
        _creditar_mm(request.user, 'aventura', 'Aventura: %s' % nome, recompensa)
    return redirect(reverse('mestre_mercado') + '?m=aventura')


@login_required(login_url='/login/')
@require_POST
def mestre_resgatar(request):
    """Resgata uma recompensa do catálogo. Dispatch por tipo: normal (debita+log),
    leilao (Rei da Colina), assinatura (Mestre Ouro: assina ou paga mensalidade)."""
    from .models import TbRecompensaMestre, TbReiDaColina
    from . import permissions as perms
    from datetime import timedelta
    if not perms.is_mestre(request.user):
        raise Http404
    r = TbRecompensaMestre.objects.filter(id_recompensa=request.POST.get('recompensa'), ativo=True).first()
    dest = reverse('mestre_mercado')
    if not r:
        return redirect(dest + '?m=invalido')
    perfil = _perfil_mestre(request.user)
    saldo = perfil.moedas_mestragem or 0

    if r.tipo == 'leilao':
        rdc = TbReiDaColina.objects.first() or TbReiDaColina.objects.create(id=1)
        if rdc.holder_id == request.user.id:
            return redirect(dest + '?m=ja_rei')
        if saldo < rdc.preco_atual:
            return redirect(dest + '?m=saldo')
        with transaction.atomic():
            preco = rdc.preco_atual
            _creditar_mm(request.user, 'leilao', 'Rei da Colina (lance %d MM)' % preco, -preco)
            rdc.holder, rdc.preco_atual, rdc.desde = request.user, preco + 100, timezone.now()
            rdc.save(update_fields=['holder', 'preco_atual', 'desde'])
        return redirect(dest + '?m=rei')

    if r.tipo == 'assinatura':
        if not perfil.mestre_ouro_ativo:
            if saldo < r.preco_mm:
                return redirect(dest + '?m=saldo')
            with transaction.atomic():
                _creditar_mm(request.user, 'assinatura', 'Mestre Ouro (assinatura)', -r.preco_mm)
                perfil.mestre_ouro_ativo = True
                perfil.mestre_ouro_proximo_pgto = timezone.now().date() + timedelta(days=30)
                perfil.save(update_fields=['mestre_ouro_ativo', 'mestre_ouro_proximo_pgto'])
            return redirect(dest + '?m=ouro')
        if saldo < r.mensalidade_mm:
            return redirect(dest + '?m=saldo')
        with transaction.atomic():
            _creditar_mm(request.user, 'mensalidade', 'Mestre Ouro (mensalidade)', -r.mensalidade_mm)
            base = perfil.mestre_ouro_proximo_pgto or timezone.now().date()
            perfil.mestre_ouro_proximo_pgto = base + timedelta(days=30)
            perfil.save(update_fields=['mestre_ouro_proximo_pgto'])
        return redirect(dest + '?m=mensalidade')

    # normal: resgate simples (debita MM; a staff cumpre o efeito pelo histórico)
    if saldo < r.preco_mm:
        return redirect(dest + '?m=saldo')
    _creditar_mm(request.user, 'resgate', 'Resgate: %s' % r.nome, -r.preco_mm)
    return redirect(dest + '?m=resgatado')


def organizacoes_view(request):
    if request.method == 'POST':
        if not request.user.is_staff:
            raise Http404
        data = _json_body(request) if request.content_type == 'application/json' else request.POST.dict()
        validate_no_sql_danger(data, 'organizacao')
        nome = (data.get('nome') or data.get('Nome') or '').strip()
        if not nome:
            return JsonResponse({'ok': False, 'error': 'Nome e obrigatorio.'}, status=400)
        document = {
            'Nome': nome,
            'Slug': slugify(data.get('slug') or nome),
            'Tipo': (data.get('tipo') or data.get('Tipo') or 'Organizacao').strip(),
            'Sede': (data.get('sede') or data.get('Sede') or '').strip(),
            'Regioes': _split_catalog_list(data.get('regioes') or data.get('Regioes')),
            'Territorios': _split_catalog_list(data.get('territorios') or data.get('Territorios')),
            'Lideranca': (data.get('lideranca') or data.get('Lideranca') or '').strip(),
            'Aliados': _split_catalog_list(data.get('aliados') or data.get('Aliados')),
            'Inimigos': _split_catalog_list(data.get('inimigos') or data.get('Inimigos')),
            'Tags': _split_catalog_list(data.get('tags') or data.get('Tags')),
            'Descricao': (data.get('descricao') or data.get('Descricao') or '').strip(),
            'UpdatedAt': datetime.now(datetime_timezone.utc),
        }
        try:
            collection = _mongo_collection('organizations')
            collection.update_one({'Slug': document['Slug']}, {'$set': document, '$setOnInsert': {'CreatedAt': datetime.now(datetime_timezone.utc)}}, upsert=True)
        except BotMongoUnavailable as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=503)
        return JsonResponse({'ok': True, 'organization': serialize_document(document)})

    return _render_catalog(
        request,
        'Organizacoes',
        'Faccoes, guildas, ordens e grupos vinculados a regioes e territorios.',
        'organizacoes',
        'organizations',
        _organization_catalog_payload,
    )


def api_opcoes(request):
    
    tipo_filter = request.GET.get('tipo', '').strip()
    subclasse_filter = request.GET.get('subclasse', '').strip()

    try:
        query = {} if not tipo_filter else {'Tipo': tipo_filter}
        opcoes_docs = _mongo_docs('options', [('Nome', 1)], query=query if tipo_filter else None)
        opcoes_lista = []
        for op in opcoes_docs:
            opcoes_lista.append({
                'id': op.get('Id_Opcao'),
                'nome': op.get('Nome') or '',
                'slug': op.get('Slug') or '',
                'tipo': op.get('Tipo') or '',
                'descricao': op.get('Descricao') or '',
                'pre_requisito': op.get('PreRequisito') or '',
                'etiquetas_adicionais': op.get('EtiquetasAdicionais') or '',
            })
        return JsonResponse({'opcoes': opcoes_lista})
    except BotMongoUnavailable:
        pass

    qs = TbOpcaojogo.objects.all().order_by('nome')
    if tipo_filter:
        qs = qs.filter(tipo__iexact=tipo_filter)
    if subclasse_filter:
        if subclasse_filter.lower() == 'null':
            qs = qs.filter(tbacessoopcao__id_subclasse__isnull=True)
        else:
            qs = qs.filter(tbacessoopcao__id_subclasse__slug=subclasse_filter)
        qs = qs.distinct()
    opcoes_lista = [
        {
            'id': op.id_opcao,
            'nome': op.nome,
            'slug': op.slug,
            'tipo': op.tipo,
            'descricao': op.descricao or '',
            'pre_requisito': op.pre_requisito or '',
            'etiquetas_adicionais': op.etiquetas_adicionais or '',
        }
        for op in qs
    ]
    return JsonResponse({'opcoes': opcoes_lista})


def api_card_preview(request):
    import re
    from django.http import JsonResponse
    from home.models import (
        TbClasse, TbSubclasse, TbClassehabilidade, TbTalento, TbRaca, TbRegiao, TbMagia
    )

    table = request.GET.get('table', '').strip().lower()
    args_str = request.GET.get('args', '').strip()
    args = [arg.strip() for arg in args_str.split(',') if arg.strip()]

    title = ""
    description = ""
    read_more_url = ""

    def slugify_py(text):
        import unicodedata
        if not text:
            return ""
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        return re.sub(r'[-\s]+', '-', text)

    if not table or not args:
        return JsonResponse({'success': False, 'error': 'Tabela ou parâmetros inválidos'}, status=400)

    # 1. Habilidade de classe
    if table in ['tbhabilidade de classe', 'tbhabilidade', 'tbhabilidadeclasse', 'tbclassehabilidade']:
        p1 = args[0]  # class or subclass slug
        p2 = args[1] if len(args) > 1 else ""  # ability slug
        
        ability = None
        
        # Check if p1 is subclass slug
        sub = TbSubclasse.objects.filter(slug=p1).first()
        if sub:
            for hab in TbClassehabilidade.objects.filter(id_subclasse=sub):
                if slugify_py(hab.nome) == p2:
                    ability = hab
                    break
        else:
            # Check if p1 is class slug
            classe = TbClasse.objects.filter(slug=p1).first()
            if classe:
                for hab in TbClassehabilidade.objects.filter(id_classe=classe):
                    if slugify_py(hab.nome) == p2:
                        ability = hab
                        break

        # Global search fallback
        if not ability:
            for hab in TbClassehabilidade.objects.all():
                if slugify_py(hab.nome) == p2 or slugify_py(hab.nome) == p1:
                    ability = hab
                    break

        if ability:
            title = ability.nome
            description = ability.descricao or ""
            if ability.id_subclasse:
                read_more_url = f"/jogador/classes/{ability.id_classe.slug}/?subclasse={ability.id_subclasse.slug}#{slugify_py(ability.nome)}"
            else:
                read_more_url = f"/jogador/classes/{ability.id_classe.slug}/#{slugify_py(ability.nome)}"

    # 2. Classe
    elif table in ['tbclasse', 'classes', 'classe']:
        p1 = args[0]
        classe = TbClasse.objects.filter(slug=p1).first()
        if classe:
            title = classe.nome
            description = classe.tagline or ""
            read_more_url = f"/jogador/classes/{classe.slug}/"

    # 3. Subclasse
    elif table in ['tbsubclasse', 'subclasses', 'subclasse']:
        p1 = args[0]
        sub = TbSubclasse.objects.filter(slug=p1).first()
        if sub:
            title = sub.nome
            description = sub.descricao or ""
            read_more_url = f"/jogador/classes/{sub.id_classe.slug}/?subclasse={sub.slug}"

    # 4. Talento
    elif table in ['tbtalento', 'talento', 'talentos']:
        p1 = args[0]
        tal = None
        for t in TbTalento.objects.all():
            if slugify_py(t.nome) == p1 or t.slug == p1:
                tal = t
                break
        if tal:
            title = tal.nome
            description = tal.descricao or ""
            read_more_url = f"/jogador/talentos/#{slugify_py(tal.nome)}"

    # 5. Raça
    elif table in ['tbraca', 'raca', 'racas']:
        p1 = args[0]
        raca = TbRaca.objects.filter(slug=p1).first()
        if raca:
            title = raca.nome
            description = raca.tagline or ""
            read_more_url = f"/jogador/raca/{raca.slug}/"

    # 6. Região
    elif table in ['tbregiao', 'regiao', 'regioes']:
        p1 = args[0]
        reg = TbRegiao.objects.filter(slug=p1).first()
        if reg:
            title = reg.nome
            description = reg.descricao or ""
            read_more_url = f"/mundo/regioes/{reg.slug}/"

    # 7. Magia
    elif table in ['tbmagia', 'magia', 'magias']:
        p1 = args[0]
        mag = None
        for m in TbMagia.objects.all():
            if slugify_py(m.nome) == p1 or m.slug == p1:
                mag = m
                break
        if mag:
            title = mag.nome
            description = mag.descricao or ""
            read_more_url = f"/magias/listas/#{slugify_py(mag.nome)}"

    if title:
        return JsonResponse({
            'success': True,
            'title': title,
            'description': description,
            'url': read_more_url
        })
    
    return JsonResponse({'success': False, 'error': 'Item não encontrado'}, status=404)


# ---------------------------------------------------------------------------
# Bestiário: widget de ficha de criatura (creature:slug). Renderiza o
# statblock_json (schema 5etools) do TbBestiario. Ver bestiario-e-summon.md.
# ---------------------------------------------------------------------------
# Tradução PT das condições 5e (para {@condition ...}).
_COND_5ET_PT = {
    'prone': 'caído', 'unconscious': 'inconsciente', 'poisoned': 'envenenado',
    'dazed': 'atordoado', 'stunned': 'atordoado', 'blinded': 'cego', 'deafened': 'surdo',
    'charmed': 'enfeitiçado', 'frightened': 'amedrontado', 'grappled': 'agarrado',
    'incapacitated': 'incapacitado', 'invisible': 'invisível', 'paralyzed': 'paralisado',
    'petrified': 'petrificado', 'restrained': 'impedido', 'exhaustion': 'exaustão',
    'exhausted': 'exausto', 'frightened|xphb': 'amedrontado',
}


def _clean_5et(text):
    """Converte o markup {@tag display|src} do 5etools (inclusive a forma {{@...}}) em
    texto legível em PT. Cobre todos os verbos achados no bestiário + catch-all defensivo."""
    if not isinstance(text, str):
        text = str(text or '')
    if not text:
        return ''
    # chaves duplas {{@item ...|xphb}} -> {@item ...|xphb}
    text = text.replace('{{@', '{@').replace('}}', '}')

    def _cond(m):
        nome = m.group(1).strip()
        return _COND_5ET_PT.get(nome.lower(), nome)
    text = re.sub(r'\{@condition ([^}|]+)(?:\|[^}]*)?\}', _cond, text)
    # recarga
    text = re.sub(r'\{@recharge (\d+)\}', r'(Recarga \1-6)', text)
    text = re.sub(r'\{@recharge\}', '(Recarga 5-6)', text)
    # marcadores de ataque / acerto / CD / salvaguarda (sem argumento ou de tipo)
    text = re.sub(r'\{@atk[^}]*\}', '', text)          # tipo de ataque fica implícito
    text = re.sub(r'\{@hit (\d+)\}', r'+\1', text)
    text = re.sub(r'\{@h\}', 'Acerto: ', text)
    text = re.sub(r'\{@dc (\d+)\}', r'CD \1', text)
    text = re.sub(r'\{@actSaveFail\}', 'Falha: ', text)
    text = re.sub(r'\{@actSaveSuccess\}', 'Sucesso: ', text)
    # dano / dados: preserva a expressão (pode conter '+')
    text = re.sub(r'\{@(?:damage|dice|scaledamage|scaledice) ([^}|]+)(?:\|[^}]*)?\}', r'\1', text)
    # ênfase: mantém só o texto interno
    text = re.sub(r'\{@(?:b|bold|i|italic|note) ([^}|]+)(?:\|[^}]*)?\}', r'\1', text)
    # genérico: qualquer {@verbo display|fonte} -> display (1º segmento antes do '|')
    text = re.sub(r'\{@\w+ ([^}|]+)(?:\|[^}]*)?\}', r'\1', text)
    # qualquer {@verbo} restante (sem argumento) -> remove
    text = re.sub(r'\{@\w+\}', '', text)
    # normaliza espaços resultantes
    text = re.sub(r'  +', ' ', text)
    return text


def _resolve_refs(text):
    """Resolve refs de markdown Bonfire [Texto](tbMagia, slug) / [Texto](tbClassehabilidade,
    dono, slug) para o texto legível (group 1). Usado onde NÃO há render de markdown no cliente."""
    if not isinstance(text, str) or not text:
        return text or ''
    return re.sub(r'\[([^\]]+)\]\(\s*tb[A-Za-z]+\s*,[^)]*\)', r'\1', text)


def _clean_statblock_text(text):
    """Pipeline completo p/ texto de statblock impresso como TEXTO (entries/nomes):
    limpa tokens 5etools e resolve refs Bonfire para texto legível."""
    return _resolve_refs(_clean_5et(text))


def _creature_entries_html(entries):
    from django.utils.html import escape as esc
    out = []
    for e in (entries or []):
        if isinstance(e, str):
            out.append('<p>%s</p>' % _clean_statblock_text(e))
        elif isinstance(e, dict):
            if e.get('items'):
                lis = ''.join('<li>%s</li>' % _clean_statblock_text(it if isinstance(it, str) else (it.get('entry') or it.get('name') or ''))
                              for it in e['items'])
                out.append('<ul>%s</ul>' % lis)
            else:
                nm = e.get('name')
                out.append((('<p><strong>%s.</strong></p>' % esc(nm)) if nm else '') + _creature_entries_html(e.get('entries', [])))
    return ''.join(out)


def _creature_section(title, blocks):
    from django.utils.html import escape as esc
    if not blocks:
        return ''
    rows = ''.join('<div class="bonfire-creature-trait"><strong>%s.</strong> %s</div>' % (esc(b.get('name', '')), _creature_entries_html(b.get('entries', [])))
                   for b in blocks)
    return '<div class="bonfire-creature-section"><h4>%s</h4>%s</div>' % (title, rows)


def _render_creature_statblock(cr):
    from django.utils.html import escape as esc
    sb = cr.statblock_json or {}
    if not sb:
        return ''
    parts = []
    ac = sb.get('ac')
    ca = (ac[0].get('ac') if isinstance(ac[0], dict) else ac[0]) if isinstance(ac, list) and ac else ac
    hp = sb.get('hp') or {}
    hp_txt = hp.get('formula') or hp.get('average') or ''
    speed = sb.get('speed') or {}
    sp_txt = ', '.join('%s %sft' % (k, v) for k, v in speed.items() if isinstance(v, (int, float)))
    meta = []
    if ca is not None:
        meta.append('<span><b>CA</b> %s</span>' % esc(str(ca)))
    if hp_txt:
        meta.append('<span><b>PV</b> %s</span>' % esc(str(hp_txt)))
    if sp_txt:
        meta.append('<span><b>Deslocamento</b> %s</span>' % esc(sp_txt))
    if meta:
        parts.append('<div class="bonfire-creature-meta">%s</div>' % ''.join(meta))
    cells = []
    for label, key in [('FOR', 'str'), ('DES', 'dex'), ('CON', 'con'), ('INT', 'int'), ('SAB', 'wis'), ('CAR', 'cha')]:
        if key in sb:
            try:
                mod = (int(sb[key]) - 10) // 2
                cells.append('<div><span class="ab">%s</span><span class="sc">%s (%+d)</span></div>' % (label, sb[key], mod))
            except (ValueError, TypeError):
                pass
    if cells:
        parts.append('<div class="bonfire-creature-attrs">%s</div>' % ''.join(cells))

    def line(label, val):
        return ('<div class="bonfire-creature-line"><b>%s</b> %s</div>' % (label, val)) if val else ''

    if sb.get('save'):
        parts.append(line('Resistências (testes)', ', '.join('%s %s' % (k.upper(), v) for k, v in sb['save'].items())))
    if sb.get('skill'):
        parts.append(line('Perícias', ', '.join('%s %s' % (k, v) for k, v in sb['skill'].items())))
    for key, label in [('resist', 'Resistências'), ('immune', 'Imunidades'), ('vulnerable', 'Vulnerabilidades'), ('conditionImmune', 'Imunidades a Condição')]:
        v = sb.get(key)
        if v:
            parts.append(line(label, ', '.join(str(x) for x in v) if isinstance(v, list) else str(v)))
    if sb.get('senses'):
        s = ', '.join(sb['senses'])
        if sb.get('passive'):
            s += ', Percepção passiva %s' % sb['passive']
        parts.append(line('Sentidos', s))
    if sb.get('languages'):
        parts.append(line('Idiomas', ', '.join(sb['languages'])))
    parts.append(_creature_section('Traços', sb.get('trait')))
    parts.append(_creature_section('Ações', sb.get('action')))
    parts.append(_creature_section('Ações Bônus', sb.get('bonus')))
    parts.append(_creature_section('Reações', sb.get('reaction')))
    parts.append(_creature_section('Ações Lendárias', sb.get('legendary')))
    return ''.join(parts)


def api_creature_preview(request):
    from django.http import JsonResponse
    from home.models import TbBestiario
    slug = (request.GET.get('slug') or '').strip().lower()
    if not slug:
        return JsonResponse({'success': False, 'error': 'slug ausente'}, status=400)
    cr = TbBestiario.objects.filter(slug=slug).first()
    if not cr:
        return JsonResponse({'success': False, 'error': 'Criatura não encontrada'}, status=404)
    return JsonResponse({
        'success': True,
        'nome': cr.nome,
        'tipo': cr.tipo or '',
        'tamanho': cr.tamanho or '',
        'nd': cr.nd or '',
        'ca': cr.ca or '',
        'pv': cr.pv or '',
        'statblock_html': _render_creature_statblock(cr),
        'descricao': cr.descricao_markdown or '',
    })




def jornal_list_view(request):
    artigos = TbJornal.objects.select_related('autor').all()
    return render(request, 'home/pages/jornal_list.html', {
        'artigos': artigos,
        'can_edit_wiki': request.user.is_staff,
    })


def jornal_detail_view(request, slug):
    artigo = get_object_or_404(TbJornal, slug=slug)
    return render(request, 'home/pages/jornal_detail.html', {
        'artigo': artigo,
        'can_edit_wiki': request.user.is_staff,
    })


@staff_member_required
def jornal_create_view(request):
    if request.method == 'POST':
        data = _json_body(request)
        titulo = data.get('titulo', '').strip()
        if not titulo:
            return JsonResponse({'error': 'Título é obrigatório.'}, status=400)
        slug = slugify(titulo)
        
        base_slug = slug
        counter = 1
        while TbJornal.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        kwargs = {
            'titulo': titulo,
            'slug': slug,
            'conteudo_markdown': data.get('conteudo_markdown', ''),
            'resumo': data.get('resumo', ''),
            'imagem_url': data.get('imagem_url', ''),
            'autor': request.user,
            'destaque': data.get('destaque', False),
            'layout': data.get('layout', 'padrao'),
        }
        
        data_publicacao_str = data.get('data_publicacao')
        if data_publicacao_str:
            try:
                from django.utils.dateparse import parse_datetime
                parsed = parse_datetime(data_publicacao_str)
                if parsed:
                    kwargs['data_publicacao'] = parsed
            except Exception:
                pass
                
        artigo = TbJornal.objects.create(**kwargs)
        return JsonResponse({'ok': True, 'slug': artigo.slug})
    
    return render(request, 'home/pages/jornal_form.html', {
        'artigo': None,
        'is_new': True,
    })


@staff_member_required
@require_POST
def jornal_update_view(request, slug):
    artigo = get_object_or_404(TbJornal, slug=slug)
    data = _json_body(request)
    artigo.titulo = data.get('titulo', artigo.titulo)
    artigo.conteudo_markdown = data.get('conteudo_markdown', artigo.conteudo_markdown)
    artigo.resumo = data.get('resumo', artigo.resumo)
    artigo.imagem_url = data.get('imagem_url', artigo.imagem_url)
    artigo.destaque = data.get('destaque', artigo.destaque)
    artigo.layout = data.get('layout', artigo.layout)
    
    data_publicacao_str = data.get('data_publicacao')
    if data_publicacao_str:
        try:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(data_publicacao_str)
            if parsed:
                artigo.data_publicacao = parsed
        except Exception:
            pass
            
    artigo.save()
    return JsonResponse({'ok': True})







def _cronicas_location_choices():
    
    territorios = list(TbTerritorio.objects.values_list('nome', flat=True).order_by('nome'))
    regioes = list(TbRegiao.objects.values_list('nome', 'territorio').order_by('nome'))
    return territorios, regioes


def _coerce_multi_value(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = (value or '').strip()
    if not value:
        return []
    try:
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    except (TypeError, ValueError):
        pass
    return [value]


def _store_multi_value(value):
    items = _coerce_multi_value(value)
    if not items:
        return ''
    return items[0] if len(items) == 1 else json.dumps(items, ensure_ascii=False)


def cronicas_list_view(request):
    qs = TbCronica.objects.filter(status='aprovada').select_related('autor')
    
    territorio_filter = request.GET.get('territorio', '')
    regiao_filter = request.GET.get('regiao', '')
    if territorio_filter:
        qs = qs.filter(territorio__icontains=territorio_filter)
    if regiao_filter:
        qs = qs.filter(regiao__icontains=regiao_filter)

    territorios = TbTerritorio.objects.values_list('nome', flat=True).order_by('nome')
    regioes = TbRegiao.objects.values_list('nome', flat=True).order_by('nome')

    pendente_count = TbCronica.objects.filter(status='pendente').count() if request.user.is_staff else 0

    
    minhas = []
    if request.user.is_authenticated:
        minhas = TbCronica.objects.filter(autor=request.user).order_by('-data_submissao')[:10]

    return render(request, 'home/pages/cronicas_list.html', {
        'cronicas': qs,
        'territorios': territorios,
        'regioes': regioes,
        'territorio_filter': territorio_filter,
        'regiao_filter': regiao_filter,
        'pendente_count': pendente_count,
        'minhas_cronicas': minhas,
        'can_edit_wiki': request.user.is_staff,
        'is_authenticated': request.user.is_authenticated,
    })


def cronica_detail_view(request, slug):
    cronica = get_object_or_404(TbCronica, slug=slug)
    
    if cronica.status != 'aprovada':
        if not (request.user.is_staff or (request.user.is_authenticated and cronica.autor == request.user)):
            raise Http404
    return render(request, 'home/pages/cronica_detail.html', {
        'cronica': cronica,
        'can_edit_wiki': request.user.is_staff,
    })


@login_required
def cronica_create_view(request):
    territorios, regioes = _cronicas_location_choices()
    if request.method == 'POST':
        data = _json_body(request)
        titulo = data.get('titulo', '').strip()
        if not titulo:
            return JsonResponse({'error': 'Título é obrigatório.'}, status=400)
        conteudo = data.get('conteudo_markdown', '').strip()
        if not conteudo:
            return JsonResponse({'error': 'Conteúdo é obrigatório.'}, status=400)
        slug = slugify(titulo)
        base_slug = slug or 'cronica'
        slug = base_slug
        counter = 1
        while TbCronica.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        cronica = TbCronica.objects.create(
            titulo=titulo,
            slug=slug,
            conteudo_markdown=conteudo,
            resumo=data.get('resumo', ''),
            imagem_url=data.get('imagem_url', ''),
            autor=request.user,
            personagem_nome=data.get('personagem_nome', ''),
            territorio=_store_multi_value(data.get('territorio', [])),
            regiao=_store_multi_value(data.get('regiao', [])),
            status='pendente',
        )
        return JsonResponse({'ok': True, 'slug': cronica.slug})
    return render(request, 'home/pages/cronica_form.html', {
        'cronica': None,
        'is_new': True,
        'territorios': territorios,
        'regioes': regioes,
        'selected_territorios': [],
        'selected_regioes': [],
    })


@login_required
def cronica_edit_view(request, slug):
    cronica = get_object_or_404(TbCronica, slug=slug)
    
    if cronica.autor != request.user:
        raise Http404
    territorios, regioes = _cronicas_location_choices()
    if request.method == 'POST':
        data = _json_body(request)
        cronica.titulo = data.get('titulo', cronica.titulo)
        cronica.conteudo_markdown = data.get('conteudo_markdown', cronica.conteudo_markdown)
        cronica.resumo = data.get('resumo', cronica.resumo)
        cronica.imagem_url = data.get('imagem_url', cronica.imagem_url)
        cronica.personagem_nome = data.get('personagem_nome', cronica.personagem_nome)
        cronica.territorio = _store_multi_value(data.get('territorio', cronica.territorio))
        cronica.regiao = _store_multi_value(data.get('regiao', cronica.regiao))
        
        if cronica.status == 'reprovada':
            cronica.status = 'pendente'
            cronica.feedback_staff = ''
            cronica.revisado_por = None
            cronica.data_revisao = None
        cronica.save()
        return JsonResponse({'ok': True})
    return render(request, 'home/pages/cronica_form.html', {
        'cronica': cronica,
        'is_new': False,
        'territorios': territorios,
        'regioes': regioes,
        'selected_territorios': _coerce_multi_value(cronica.territorio),
        'selected_regioes': _coerce_multi_value(cronica.regiao),
    })


@staff_member_required
def cronicas_review_view(request):
    pendentes = TbCronica.objects.filter(status='pendente').select_related('autor').order_by('data_submissao')
    return render(request, 'home/pages/cronicas_review.html', {
        'pendentes': pendentes,
    })


@staff_member_required
@require_POST
def cronica_review_action(request, cronica_id):
    cronica = get_object_or_404(TbCronica, pk=cronica_id)
    data = _json_body(request)
    action = data.get('action', '')
    if action == 'aprovar':
        cronica.status = 'aprovada'
        cronica.revisado_por = request.user
        cronica.data_revisao = timezone.now()
        cronica.feedback_staff = ''
        cronica.save()
        return JsonResponse({'ok': True, 'status': 'aprovada'})
    elif action == 'reprovar':
        cronica.status = 'reprovada'
        cronica.revisado_por = request.user
        cronica.data_revisao = timezone.now()
        cronica.feedback_staff = data.get('feedback', '')
        cronica.save()
        return JsonResponse({'ok': True, 'status': 'reprovada'})
    return JsonResponse({'error': 'Ação inválida.'}, status=400)


def itens_mundanos_view(request):
    itens = TbItemMundano.objects.all().order_by('nome')
    by = {}
    for i in itens:
        by.setdefault(i.categoria, []).append(i)
    EXTRA = [('municao', 'Munição'), ('foco', 'Focos de Conjuração'), ('comida', 'Comida e Bebida'),
             ('montaria', 'Montarias'), ('veiculo', 'Veículos'), ('mercadoria', 'Mercadorias'),
             ('veneno', 'Venenos'), ('explosivo', 'Explosivos')]
    grupos_extra = [{'id': cat, 'label': label, 'itens': by.get(cat, [])}
                    for cat, label in EXTRA if by.get(cat)]
    context = {
        'title': 'Itens Mundanos',
        'armas': by.get('arma', []),
        'armaduras': by.get('armadura', []),
        'ferramentas': by.get('ferramenta', []),
        'pacotes': by.get('pacote', []),
        'equipamentos': by.get('equipamento_aventura', []),
        'grupos_extra': grupos_extra,
    }
    
    if is_ajax(request):
        return render(request, 'home/partials/itens_mundanos_content.html', context)
    return render(request, 'home/pages/itens_mundanos.html', context)


def itens_magicos_view(request):
    itens = TbItemMagico.objects.all().order_by('raridade', 'nome')

    # Botões de filtro = as raridades COMPLETAS realmente presentes (com _menor/_maior),
    # ordenadas por base e tier (ex.: "Raro Menor" antes de "Raro Maior"). Rótulo vem das choices.
    _rar_labels = dict(TbItemMagico._meta.get_field('raridade').choices)
    _base_order = ['comum', 'incomum', 'raro', 'muito_raro', 'lendario', 'artefato']

    def _rar_key(r):
        base = re.sub(r'_(menor|maior)$', '', r)
        tier = 1 if r.endswith('_maior') else 0
        return (_base_order.index(base) if base in _base_order else 99, tier, r)
    _present = [r for r in TbItemMagico.objects.values_list('raridade', flat=True).distinct() if r]
    raridades_filtro = [{'value': r, 'label': _rar_labels.get(r, r.replace('_', ' ').title())}
                        for r in sorted(_present, key=_rar_key)]

    context = {
        'title': 'Itens Mágicos',
        'itens': itens,
        'raridades_filtro': raridades_filtro,
    }

    if is_ajax(request):
        return render(request, 'home/partials/itens_magicos_content.html', context)
    return render(request, 'home/pages/itens_magicos.html', context)


# ════════════════════════ Webhook Asaas (pagamentos) ════════════════════════
# Recebe os eventos do Asaas e cria a transação (idempotente) na MESMA tabela
# `transactions` que o bot lê (BotTransaction, managed=False / Postgres). O fluxo de
# claim/produtos do bot concede os tokens — nada muda no bot. Config no painel do
# Asaas: webhook URL = https://bonfiretales.com.br/webhooks/asaas/, com um token forte
# no campo de autenticação (= ASAAS_WEBHOOK_TOKEN no .env), eventos PAYMENT_CONFIRMED
# e PAYMENT_RECEIVED. Cada assinatura/link no Asaas deve setar `externalReference` = a
# chave do plano (ex.: colaborador-marques-3m) — é assim que o webhook sabe o plano.
_ASAAS_PERIODO = {'1m': 'MONTHLY', '3m': 'QUARTERLY', '6m': 'SEMIANNUALLY', '12m': 'YEARLY'}
_ASAAS_MESES = {'1m': 1, '3m': 3, '6m': 6, '12m': 12}


def _asaas_api_get(path):
    """GET autenticado na API do Asaas. Retorna dict ou None."""
    import urllib.request
    import urllib.error
    if not settings.ASAAS_API_KEY:
        return None
    req = urllib.request.Request('%s/%s' % (settings.ASAAS_API_BASE, path.lstrip('/')),
                                 headers={'access_token': settings.ASAAS_API_KEY,
                                          'User-Agent': 'BonfireSite'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None


def _asaas_parse_dt(s):
    """Data do Asaas ('YYYY-MM-DD' ou com hora) → datetime aware. None se vazio."""
    if not s:
        return None
    from django.utils.dateparse import parse_datetime, parse_date
    dt = parse_datetime(s)
    if dt is None:
        d = parse_date(s)
        dt = datetime.combine(d, datetime.min.time()) if d else None
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _add_meses(dt, meses):
    import calendar
    m = dt.month - 1 + int(meses)
    ano, mes = dt.year + m // 12, m % 12 + 1
    return dt.replace(year=ano, month=mes, day=min(dt.day, calendar.monthrange(ano, mes)[1]))


def _asaas_map_transacao(payment, event):
    """Pagamento Asaas → campos da tabela `transactions`. Plano vem do externalReference
    (chave: colaborador-<conde|marques|duque>-<1m|3m|6m|12m>). Função PURA (testável)."""
    plano = (payment.get('externalReference') or '').strip()
    sufixo = plano.rsplit('-', 1)[-1] if '-' in plano else ''
    pdate = _asaas_parse_dt(payment.get('paymentDate') or payment.get('confirmedDate')
                            or payment.get('clientPaymentDate')) or timezone.now()
    return {
        'transactionCode': payment.get('id'),
        'transactionSource': 'ASAAS',
        'subscriptionPlan': plano,
        'subscriptionPeriod': _ASAAS_PERIODO.get(sufixo, ''),
        'subscriptionReference': payment.get('subscription') or '-',
        'status': 1,  # CONFIRMAR: int que o bot trata como pago/ativo (ver addPayment)
        'grossAmount': float(payment.get('value') or 0),
        'netAmount': float(payment.get('netValue') or payment.get('value') or 0),
        'name': None,
        'email': '',
        'comments': 'Asaas %s' % event,
        '_paymentDate': pdate,
        '_meses': _ASAAS_MESES.get(sufixo, 1),
    }


@csrf_exempt
@require_POST
def asaas_webhook(request):
    """Endpoint do webhook do Asaas. Valida o token, busca o pagamento completo (fonte
    da verdade) e cria a transação não-claimed na tabela compartilhada (idempotente)."""
    from .models import BotTransaction
    import uuid
    # 1. autenticação do webhook (header asaas-access-token == token do .env)
    if not settings.ASAAS_WEBHOOK_TOKEN or request.headers.get('asaas-access-token', '') != settings.ASAAS_WEBHOOK_TOKEN:
        return HttpResponse('unauthorized', status=401)
    # 2. corpo
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse('bad json', status=400)
    event = body.get('event') or ''
    pay_ref = body.get('payment') or {}
    payment_id = pay_ref.get('id')
    # 3. só pagamento liquidado vira benefício; o resto é só ACK (200)
    if event not in ('PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED'):
        return HttpResponse('ignored', status=200)
    if not payment_id:
        return HttpResponse('no payment id', status=200)
    # 4. idempotência (Asaas reentrega "at least once")
    if BotTransaction.objects.filter(transactionCode=payment_id).exists():
        return HttpResponse('already processed', status=200)
    # 5. busca o pagamento completo + e-mail do cliente (p/ o claim casar por email)
    payment = _asaas_api_get('payments/%s' % payment_id) or pay_ref
    campos = _asaas_map_transacao(payment, event)
    if payment.get('customer'):
        cust = _asaas_api_get('customers/%s' % payment['customer'])
        if cust:
            campos['email'] = (cust.get('email') or '').strip()
            campos['name'] = cust.get('name')
    pdate, meses = campos.pop('_paymentDate'), campos.pop('_meses')
    # 6. cria a transação não-claimed (o bot concede os tokens no claim)
    agora = timezone.now()
    try:
        BotTransaction.objects.create(
            id='asaas_%s' % uuid.uuid4().hex, paymentDate=pdate,
            expirationDate=_add_meses(pdate, meses), claimed=False,
            createdAt=agora, updatedAt=agora, **campos)
    except Exception:
        if BotTransaction.objects.filter(transactionCode=payment_id).exists():
            return HttpResponse('race-already', status=200)  # corrida: ok
        raise  # erro real → 500 → Asaas reentrega
    return HttpResponse('ok', status=200)


# ════════════════════════ Busca global do site ════════════════════════
def busca_global(request):
    """Busca global: cruza os principais conteúdos por nome/título e agrupa por categoria.
    Cada tipo é resiliente (try/except) — se um modelo/campo faltar, só pula aquela seção."""
    from django.db.models import Q
    q = (request.GET.get('q') or '').strip()
    grupos, total = [], 0
    if len(q) >= 2:
        from .models import (TbRaca, TbClasse, TbMagia, TbTalento, TbAntecedente,
                             TbItemMundano, TbItemMagico, TbBestiario, TbArmadilha,
                             TbCondicao, TbIdioma, TbRegra, TbOpcaojogo, TbRegiao,
                             TbCronica, TbJornal)
        LIM = 8

        def D(name):  # link p/ página de detalhe (por slug)
            return lambda o: reverse(name, args=[o.slug])

        def P(name):  # link p/ página de catálogo/lista
            return lambda o: reverse(name)

        # (categoria, ícone, Model, campo_nome, [campos de busca], link_fn, subtítulo_fn)
        SPECS = [
            ('Raças', '🧬', TbRaca, 'nome', ['nome'], D('raca_detail'), lambda o: o.tagline or ''),
            ('Classes', '⚔️', TbClasse, 'nome', ['nome'], D('classe_detail'), lambda o: ''),
            ('Magias', '✨', TbMagia, 'nome', ['nome'],
             lambda o: reverse('magias_listas') + '?magia=' + (o.slug or ''),
             lambda o: ('Truque' if o.nivel == 0 else 'Nível %d' % o.nivel) + (' · %s' % o.escola if o.escola else '')),
            ('Talentos', '📜', TbTalento, 'nome', ['nome'], P('jogador_talentos'), lambda o: o.tipo or ''),
            ('Antecedentes', '🎭', TbAntecedente, 'nome', ['nome'], P('jogador_antecedentes'), lambda o: ''),
            ('Itens Mundanos', '🎒', TbItemMundano, 'nome', ['nome'], P('mercado_itens_mundanos'),
             lambda o: o.get_categoria_display() if hasattr(o, 'get_categoria_display') else (o.categoria or '')),
            ('Itens Mágicos', '🔮', TbItemMagico, 'nome', ['nome'], P('mercado_itens_magicos'),
             lambda o: o.get_raridade_display() if hasattr(o, 'get_raridade_display') else ''),
            ('Bestiário', '🐉', TbBestiario, 'nome', ['nome'], P('bestiario'),
             lambda o: ('ND %s' % o.nd) if o.nd else (o.tipo or '')),
            ('Armadilhas', '⚠️', TbArmadilha, 'nome', ['nome'], P('mestre_armadilhas'), lambda o: o.tipo or ''),
            ('Condições', '🌀', TbCondicao, 'nome', ['nome'],
             lambda o: reverse('mestre_condicoes') + '#cond-' + (o.slug or ''), lambda o: o.resumo or ''),
            ('Idiomas', '🗣️', TbIdioma, 'nome', ['nome'], P('jogador_idiomas'), lambda o: o.categoria or ''),
            ('Glossário', '📖', TbRegra, 'nome', ['nome', 'nome_en'], P('sistemas_glossario'), lambda o: o.categoria or ''),
            ('Opções', '🎲', TbOpcaojogo, 'nome', ['nome'], P('jogador_opcoes'), lambda o: o.tipo or ''),
            ('Regiões', '🗺️', TbRegiao, 'nome', ['nome'], D('regiao_detail'),
             lambda o: o.get_categoria_display() if hasattr(o, 'get_categoria_display') else ''),
            ('Crônicas', '📰', TbCronica, 'titulo', ['titulo'], D('cronica_detail'), lambda o: o.personagem_nome or ''),
            ('Jornal', '🗞️', TbJornal, 'titulo', ['titulo'], D('jornal_detail'), lambda o: ''),
        ]
        for categoria, icone, Model, nome_field, campos, link_fn, sub_fn in SPECS:
            try:
                cond = Q()
                for c in campos:
                    cond |= Q(**{c + '__icontains': q})
                itens = []
                for o in Model.objects.filter(cond).order_by(nome_field)[:LIM]:
                    try:
                        url = link_fn(o)
                    except Exception:
                        url = ''
                    try:
                        sub = sub_fn(o) or ''
                    except Exception:
                        sub = ''
                    itens.append({'nome': getattr(o, nome_field, ''), 'sub': sub, 'url': url})
                if itens:
                    grupos.append({'categoria': categoria, 'icone': icone, 'itens': itens})
                    total += len(itens)
            except Exception:
                continue
    return render(request, 'home/pages/busca.html', {
        'page_title': ('Busca: %s' % q) if q else 'Busca',
        'q': q, 'grupos': grupos, 'total': total,
    })
