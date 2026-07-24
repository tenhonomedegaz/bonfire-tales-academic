import json
import hashlib
import re
import unicodedata
from urllib.parse import unquote, urlsplit
from .item_mecanica import mecanica_de_tags, dano_display, propriedades_display, ca_display
from . import badges as _badges
from . import conquistas as _conquistas
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import Http404, JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.paginator import Paginator
from django.db.models import Count, Q, F, Max
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html, format_html_join
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
    TbMapLayer,
    TbMapDesenho,
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


class SiteDataUnavailable(Exception):
    """Raised when a requested PostgreSQL table is not available."""
    pass


SITE_TABLES = {
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
    table_name = SITE_TABLES.get(key)
    if not table_name:
        raise SiteDataUnavailable(f"Tabela PostgreSQL nao configurada para: {key}")
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    if table_name not in table_names:
        raise SiteDataUnavailable(f"Tabela PostgreSQL nao encontrada: {table_name}")
    return table_name


def _postgres_columns(table_name):
    with connection.cursor() as cursor:
        return [column.name for column in connection.introspection.get_table_description(cursor, table_name)]


def _quote_name(name):
    return connection.ops.quote_name(name)


from decimal import Decimal
from datetime import date


def _serialize_site_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, dict)):
        return value
    return value


def serialize_document(document):
    return {key: _serialize_site_value(value) for key, value in (document or {}).items()}


def _row_to_document(columns, row):
    return serialize_document(dict(zip(columns, row)))


def _site_count(key, query=None):
    table_name = _postgres_table_for_key(key)
    columns = _postgres_columns(table_name)
    query = query or {}
    valid_query = {field: value for field, value in query.items() if field in columns}
    where_sql = ""
    params = []
    if valid_query:
        where_sql = " WHERE " + " AND ".join(f"{_quote_name(field)} = %s" for field in valid_query)
        params = list(valid_query.values())
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {_quote_name(table_name)}{where_sql}", params)
        return cursor.fetchone()[0]


def _site_docs(key, sort=None, query=None):
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


def _site_one(key, query):
    documents = _site_docs(key, query=query)
    return documents[0] if documents else None


def _upsert_site_document(key, id_field, id_value, payload):
    if id_value in (None, '', 'undefined', 'null'):
        return
    table_name = _postgres_table_for_key(key)
    columns = _postgres_columns(table_name)
    if id_field not in columns:
        raise SiteDataUnavailable(f"Coluna de chave ausente em {table_name}: {id_field}")

    document = dict(payload or {})
    document[id_field] = id_value
    data = {field: value for field, value in document.items() if field in columns}
    if not data:
        return

    where_sql = f"{_quote_name(id_field)} = %s"
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {_quote_name(table_name)} WHERE {where_sql}",
            [id_value],
        )
        exists = cursor.fetchone()[0] > 0
        if exists:
            update_data = {field: value for field, value in data.items() if field != id_field}
            if not update_data:
                return
            set_sql = ", ".join(f"{_quote_name(field)} = %s" for field in update_data)
            cursor.execute(
                f"UPDATE {_quote_name(table_name)} SET {set_sql} WHERE {where_sql}",
                [*update_data.values(), id_value],
            )
            return

        columns_sql = ", ".join(_quote_name(field) for field in data)
        placeholders = ", ".join(["%s"] * len(data))
        cursor.execute(
            f"INSERT INTO {_quote_name(table_name)} ({columns_sql}) VALUES ({placeholders})",
            list(data.values()),
        )


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


def _site_classe(doc):
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


def _site_subclasse(doc, classes_by_id=None):
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


def _site_habilidade(doc, classes_by_id=None, subclasses_by_id=None):
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


def _site_recurso(doc, classes_by_id=None, subclasses_by_id=None):
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


def _site_raca(doc):
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


def _site_linhagem(doc, tracos=None):
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


def _site_traco(doc):
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


APPEARANCE_THEMES = {
    'bonfire': {'label': 'Bonfire', 'class': 'theme-bonfire'},
    'ember': {'label': 'Brasas de Cineria', 'class': 'theme-ember'},
    'arcane': {'label': 'Arcano Violeta', 'class': 'theme-arcane'},
    'verdant': {'label': 'Bosque Esmeralda', 'class': 'theme-verdant'},
    'moonlit': {'label': 'Luar Prateado', 'class': 'theme-moonlit'},
    'custom': {'label': 'Personalizado', 'class': 'theme-custom'},
}

APPEARANCE_FRAMES = {
    'none': {'label': 'Sem moldura', 'class': ''},
    'ember-ring': {'label': 'Anel de Brasa', 'class': 'frame-ember-ring'},
    'arcane-pulse': {'label': 'Pulso Arcano', 'class': 'frame-arcane-pulse'},
    'gold-trim': {'label': 'Friso Dourado', 'class': 'frame-gold-trim'},
    'frost': {'label': 'Coroa de Gelo', 'class': 'frame-frost'},
    'verdant': {'label': 'Trança Verdejante', 'class': 'frame-verdant'},
}

APPEARANCE_EFFECTS = {
    'none': {'label': 'Sem efeito', 'class': ''},
    'soft-glow': {'label': 'Brilho suave', 'class': 'effect-soft-glow'},
    'glass': {'label': 'Vidro escuro', 'class': 'effect-glass'},
    'embers': {'label': 'Brasas discretas', 'class': 'effect-embers'},
    'aurora': {'label': 'Aurora', 'class': 'effect-aurora'},
    'starfall': {'label': 'Chuva de estrelas', 'class': 'effect-starfall'},
}

# Cor hex validada (#rrggbb). NUNCA injetar string livre em style inline.
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

# Fallback usado quando o tema custom não tem uma cor válida definida.
CUSTOM_THEME_DEFAULT = {
    'accent': '#f59e0b',
    'accent2': '#7c2d12',
    'surface': '#1b120f',
    'deep': '#0e0a08',
    'gradiente': False,
}


# Mapa dos dicts hardcoded por "tipo interno" (theme/frame/effect). Continuam sendo
# a semente do catálogo (data migration 0048) e um FALLBACK caso o catálogo esteja
# vazio/indisponível — garante zero regressão mesmo antes de rodar o seed.
_APPEARANCE_FALLBACK = {
    'theme': APPEARANCE_THEMES,
    'frame': APPEARANCE_FRAMES,
    'effect': APPEARANCE_EFFECTS,
}
_APPEARANCE_DEFAULT = {'theme': 'bonfire', 'frame': 'none', 'effect': 'none'}


def _appearance_catalog(tipo_interno):
    """Catálogo (dict {slug: {label, class, ...}}) de um tipo interno
    (theme/frame/effect), vindo do banco com cache; cai no dict hardcoded se o
    catálogo estiver vazio (ex.: antes do seed rodar). Contrato idêntico ao dict."""
    from .cosmetics import get_catalog, APPEARANCE_TIPO
    catalogo = get_catalog(APPEARANCE_TIPO[tipo_interno])
    return catalogo or _APPEARANCE_FALLBACK[tipo_interno]


def _appearance_choice(value, choices, default='none'):
    value = (value or default or '').strip()
    return value if value in choices else default


def _cosmetic_allowed(user, tipo_interno, value, escopo='ambos'):
    """True se `value` é escolha permitida do `tipo_interno` para o usuário:
    existe no catálogo ativo (escopo compatível) E (livre OU no inventário). Usa
    o dict de fallback quando o catálogo está vazio (mesmo comportamento antigo)."""
    from .cosmetics import cosmetic_allowed
    catalogo = _appearance_catalog(tipo_interno)
    if catalogo is _APPEARANCE_FALLBACK[tipo_interno]:
        return value in catalogo  # fallback: whitelist aberta como antes
    return cosmetic_allowed(user, tipo_interno, value, escopo)


def _appearance_validated(user, tipo_interno, value, escopo='ambos'):
    """Valida uma escolha de aparência POR POSSE (catálogo+inventário). Devolve o
    slug se permitido, senão o default do tipo. Substitui `_appearance_choice` no
    salvamento de perfil/ficha. Em F1 (tudo livre) devolve os mesmos resultados."""
    default = _APPEARANCE_DEFAULT[tipo_interno]
    value = (value or default or '').strip()
    if _cosmetic_allowed(user, tipo_interno, value, escopo):
        return value
    return default


def _validated_titulo_equipado(user, slug):
    """Slug de título só é aceito se o usuário POSSUI o cosmético (inventário, por
    slug completo). Qualquer outro valor → '' (nenhum título). Blinda contra POST
    de slug que o user não tem."""
    slug = (slug or '').strip()
    if not slug:
        return ''
    return slug if _badges.user_possui_cosmetico(user, slug, 'titulo') else ''


def _validated_badges_destaque(user, slugs):
    """Filtra a lista de slugs de badge para SÓ os que o usuário realmente possui
    (badges concedidas no inventário), preservando a ordem escolhida, sem duplicatas
    e cortando no limite. Slug inválido/não-possuído é descartado silenciosamente."""
    from .models import TbUsuarioCosmetico, BADGES_DESTAQUE_LIMITE
    slugs = [str(s).strip() for s in (slugs or []) if str(s).strip()]
    if not slugs:
        return []
    possuidos = set(
        TbUsuarioCosmetico.objects
        .filter(user=user, cosmetico__tipo='badge', cosmetico__ativo=True,
                cosmetico__slug__in=slugs)
        .values_list('cosmetico__slug', flat=True)
    )
    out, vistos = [], set()
    for s in slugs:
        if s in possuidos and s not in vistos:
            out.append(s)
            vistos.add(s)
    return out[:BADGES_DESTAQUE_LIMITE]


def _sanitize_custom_theme(raw):
    """Normaliza o dict do tema Personalizado: só cores ^#[0-9a-fA-F]{6}$ passam;
    valor inválido cai no default. `gradiente` vira bool. Blindado contra injeção
    em style inline — nenhuma string livre do usuário sobrevive daqui."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key in ('accent', 'accent2', 'surface', 'deep'):
        val = str(raw.get(key, '') or '').strip()
        out[key] = val if _HEX_COLOR_RE.match(val) else CUSTOM_THEME_DEFAULT[key]
    grad = raw.get('gradiente')
    out['gradiente'] = grad in (True, 'true', 'on', '1', 1)
    return out


def _custom_theme_from_post(request, prefix=''):
    """Monta o dict do tema custom a partir dos campos do formulário
    (accent/accent2/surface/deep + gradiente)."""
    return _sanitize_custom_theme({
        'accent': request.POST.get(prefix + 'custom_accent'),
        'accent2': request.POST.get(prefix + 'custom_accent2'),
        'surface': request.POST.get(prefix + 'custom_surface'),
        'deep': request.POST.get(prefix + 'custom_deep'),
        'gradiente': request.POST.get(prefix + 'custom_gradiente'),
    })


def _theme_vars_style(colors):
    """Builder ÚNICO do bloco de CSS custom properties inline (string), emitindo
    tanto `--profile-*` quanto `--sheet-*`. Usado pelo tema Personalizado E pelos
    temas-dado (definicao_json). Recebe um dict com chaves accent/accent2/surface/
    deep/gradiente (já sanitizadas — hex-only). `gradiente` True → o accent vira
    linear-gradient(accent, accent2); o *-solid mantém a cor chapada."""
    accent = colors['accent']
    accent2 = colors['accent2']
    surface = colors['surface']
    deep = colors['deep']
    if colors.get('gradiente'):
        accent_val = 'linear-gradient(120deg, %s, %s)' % (accent, accent2)
    else:
        accent_val = accent
    return (
        '--profile-accent:%s;--sheet-accent:%s;'
        '--profile-accent-solid:%s;--sheet-accent-solid:%s;'
        '--profile-accent-2:%s;--sheet-accent-2:%s;'
        '--profile-surface:%s;--sheet-surface:%s;'
        '--profile-deep:%s;--sheet-deep:%s;'
    ) % (accent_val, accent_val, accent, accent,
         accent2, accent2, surface, surface, deep, deep)


def _custom_theme_style(colors):
    """Bloco de CSS custom properties inline (string) para o tema Personalizado.
    Recebe SEMPRE cores já sanitizadas por _sanitize_custom_theme."""
    return _theme_vars_style(_sanitize_custom_theme(colors))


def _appearance_context(theme='bonfire', frame='none', effect='none',
                        theme_custom=None, background=''):
    from .cosmetics import sanitize_definicao_tema
    themes = _appearance_catalog('theme')
    frames = _appearance_catalog('frame')
    effects = _appearance_catalog('effect')
    theme_key = _appearance_choice(theme, themes, 'bonfire')
    frame_key = _appearance_choice(frame, frames, 'none')
    effect_key = _appearance_choice(effect, effects, 'none')
    custom = _sanitize_custom_theme(theme_custom)
    is_custom = theme_key == 'custom'

    theme_item = themes.get(theme_key, {})
    # Definição sanitizada do tema-dado escolhido (get_catalog já sanitiza; o dict
    # de fallback legado não tem 'definicao' → {} = sem definição, cai no legado).
    definicao = sanitize_definicao_tema(theme_item.get('definicao')) \
        if theme_item.get('definicao') else {}

    if is_custom:
        # Tema Personalizado: comportamento intacto (vars do custom) + fx default
        # pras partículas (subir/media), como pede a arquitetura §3.
        theme_class = themes[theme_key]['class']
        custom_style = _custom_theme_style(custom)
        fx_particula, fx_vel = 'subir', 'media'
        theme_css_href = ''
    elif definicao:
        # Tema-dado: classe neutra (não colide com as legadas) + vars via builder
        # único (mesmo do custom, com gradiente quando pedido) + fx por atributo.
        theme_class = 'theme-data'
        custom_style = _theme_vars_style(definicao)
        fx_particula = definicao['particula']
        fx_vel = definicao['vel']
        theme_css_href = theme_item.get('css_url', '') or ''
    else:
        # Legado (sem definição): EXATAMENTE o comportamento atual — regressão zero.
        theme_class = themes[theme_key]['class']
        custom_style = ''
        fx_particula, fx_vel = '', ''
        theme_css_href = ''

    return {
        'theme_key': theme_key,
        'frame_key': frame_key,
        'effect_key': effect_key,
        'theme_class': theme_class,
        'frame_class': frames[frame_key]['class'],
        'effect_class': effects[effect_key]['class'],
        'theme_label': themes[theme_key]['label'],
        'custom': custom,
        'background_url': (background or '').strip(),
        # style inline (tema custom OU tema-dado); '' pros legados.
        'custom_style': custom_style,
        'is_custom': is_custom,
        # Contrato de partículas por atributo (perfil-fx.css). '' = sem definição.
        'fx_particula': fx_particula,
        'fx_vel': fx_vel,
        # <link> do CSS avançado do tema (css_file), quando houver.
        'theme_css_href': theme_css_href,
    }


PROFILE_UPLOAD_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


# Prefixos de MEDIA que este site gerencia (só estes podem ser deletados por URL).
_MANAGED_UPLOAD_PREFIXES = ('profile_uploads/', 'character_uploads/')


def _local_profile_upload_path(value):
    value = (value or '').strip()
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    if not value or not value.startswith(media_url):
        return ''
    path = unquote(urlsplit(value).path)
    if not path.startswith(media_url):
        return ''
    rel = path[len(media_url):].lstrip('/\\')
    return rel if rel.startswith(_MANAGED_UPLOAD_PREFIXES) else ''


def _delete_profile_upload(value):
    rel = _local_profile_upload_path(value)
    if rel and default_storage.exists(rel):
        default_storage.delete(rel)


def _save_media_upload(rel_dir, uploaded, kind, old_value='', max_mb=10):
    """Salva um upload de imagem (mesma validação de perfil) em `rel_dir/<kind><ext>`
    dentro do MEDIA_ROOT. Extensões e content-type de imagem; substitui o anterior.
    Base compartilhada por perfil (profile_uploads/) e personagem (character_uploads/)."""
    if not uploaded:
        return ''
    if uploaded.size > max_mb * 1024 * 1024:
        raise ValueError('O arquivo de %s deve ter no maximo %d MB.' % (kind, max_mb))
    ext = ('.' + (uploaded.name or '').split('.')[-1].lower()) if '.' in (uploaded.name or '') else ''
    content_type = (getattr(uploaded, 'content_type', '') or '').lower()
    if not ext and content_type.startswith('image/'):
        ext = '.' + content_type.split('/', 1)[1].replace('jpeg', 'jpg')
    if ext not in PROFILE_UPLOAD_EXTENSIONS or not content_type.startswith('image/'):
        raise ValueError('Envie uma imagem PNG, JPG, WEBP ou GIF para %s.' % kind)
    _delete_profile_upload(old_value)
    path = '%s/%s%s' % (rel_dir.rstrip('/'), kind, ext)
    if default_storage.exists(path):
        default_storage.delete(path)
    saved = default_storage.save(path, ContentFile(uploaded.read()))
    return default_storage.url(saved)


def _save_profile_upload(user, uploaded, kind, old_value='', max_mb=10):
    return _save_media_upload('profile_uploads/user_%s' % user.pk, uploaded, kind, old_value, max_mb)


def _save_character_upload(pers, uploaded, kind, old_value='', max_mb=10):
    return _save_media_upload('character_uploads/pers_%s' % pers.pk, uploaded, kind, old_value, max_mb)


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
            new_banner = request.POST.get('banner_url', '').strip()
            new_background = request.POST.get('background_url', '').strip()
            clear_avatar = request.POST.get('clear_avatar') == 'on'
            clear_banner = request.POST.get('clear_banner') == 'on'
            clear_background = request.POST.get('clear_background') == 'on'
            new_bio = request.POST.get('bio', '').strip()
            profile_theme = _appearance_validated(user, 'theme', request.POST.get('profile_theme'), 'perfil')
            avatar_frame = _appearance_validated(user, 'frame', request.POST.get('avatar_frame'), 'perfil')
            profile_effect = _appearance_validated(user, 'effect', request.POST.get('profile_effect'), 'perfil')
            theme_custom = _custom_theme_from_post(request)
            titulo_equipado = _validated_titulo_equipado(user, request.POST.get('titulo_equipado'))
            badges_destaque = _validated_badges_destaque(user, request.POST.getlist('badges_destaque'))
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

            try:
                avatar_upload = request.FILES.get('avatar_file')
                banner_upload = request.FILES.get('banner_file')
                if avatar_upload:
                    new_avatar = _save_profile_upload(user, avatar_upload, 'avatar', profile.avatar_url, max_mb=8)
                elif clear_avatar:
                    _delete_profile_upload(profile.avatar_url)
                    new_avatar = ''
                elif new_avatar != (profile.avatar_url or ''):
                    _delete_profile_upload(profile.avatar_url)

                if banner_upload:
                    new_banner = _save_profile_upload(user, banner_upload, 'banner', profile.banner_url, max_mb=12)
                elif clear_banner:
                    _delete_profile_upload(profile.banner_url)
                    new_banner = ''
                elif new_banner != (profile.banner_url or ''):
                    _delete_profile_upload(profile.banner_url)

                background_upload = request.FILES.get('background_file')
                if background_upload:
                    new_background = _save_profile_upload(user, background_upload, 'background', profile.background_url, max_mb=12)
                elif clear_background:
                    _delete_profile_upload(profile.background_url)
                    new_background = ''
                elif new_background != (profile.background_url or ''):
                    _delete_profile_upload(profile.background_url)
            except ValueError as exc:
                errors.append(str(exc))

            profile.avatar_url = new_avatar or None
            profile.banner_url = new_banner or None
            profile.background_url = new_background or None
            profile.bio = new_bio[:800] or None
            profile.profile_theme = profile_theme
            profile.theme_custom = theme_custom
            profile.avatar_frame = None if avatar_frame == 'none' else avatar_frame
            profile.profile_effect = None if profile_effect == 'none' else profile_effect
            profile.titulo_equipado = titulo_equipado
            profile.badges_destaque = badges_destaque
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
        'appearance': _appearance_context(profile.profile_theme, profile.avatar_frame,
                                          profile.profile_effect, profile.theme_custom,
                                          profile.background_url),
        'appearance_themes': _appearance_catalog('theme'),
        'appearance_frames': _appearance_catalog('frame'),
        'appearance_effects': _appearance_catalog('effect'),
        # F2 — Badges & Títulos: títulos que o user possui (dropdown) + badges
        # concedidas (checkboxes de destaque) + o que ele já equipou/fixou.
        'titulos_disponiveis': _badges.titulos_disponiveis(user),
        'badges_concedidas': _badges.badges_concedidas(user),
        'badges_derivadas': _badges.badges_derivadas(user),
        'titulo_equipado_slug': (profile.titulo_equipado or '').strip(),
        'badges_destaque_slugs': list(profile.badges_destaque or []),
        # F3 — progresso das próprias conquistas (obtidas + bloqueadas não-secretas).
        'conquistas': _conquistas.conquistas_do_usuario(user),
    })


def public_profile_view(request, username):
    from .models import UserProfile, TbPersonagem
    from . import permissions as perms

    User = get_user_model()
    viewed_user = get_object_or_404(User, username__iexact=username)
    profile, _ = UserProfile.objects.get_or_create(user=viewed_user)
    pode_ver_privados = request.user.is_authenticated and (
        request.user.pk == viewed_user.pk or perms.is_staff_user(request.user)
    )
    personagens_qs = (TbPersonagem.objects.filter(dono=viewed_user)
                      .select_related('id_raca')
                      .prefetch_related('classes__id_classe')
                      .order_by('-atualizado_em'))
    if not pode_ver_privados:
        personagens_qs = personagens_qs.filter(publico=True, arquivado=False)
    personagens = [_personagem_card(p) for p in personagens_qs]
    return render(request, 'home/pages/perfil_publico.html', {
        'page_title': viewed_user.username,
        'viewed_user': viewed_user,
        'profile': profile,
        'personagens': personagens,
        'pode_ver_privados': pode_ver_privados,
        'appearance': _appearance_context(profile.profile_theme, profile.avatar_frame,
                                          profile.profile_effect, profile.theme_custom,
                                          profile.background_url),
        # F2 — badges (derivadas + concedidas, fixadas primeiro) e título equipado.
        'badges': _badges.badges_do_usuario(viewed_user),
        'titulo': _badges.titulo_do_usuario(viewed_user),
        # F3 — vitrine de conquistas (compacta). Secretas não-obtidas nunca aparecem.
        'conquistas': _conquistas.conquistas_do_usuario(viewed_user),
    })


# ───────────────────────── Discord OAuth2 (custom enxuto) ─────────────────────
def jogadores_view(request):
    from .models import UserProfile, TbPersonagem

    User = get_user_model()
    q = (request.GET.get('q') or '').strip()
    filtro = (request.GET.get('filtro') or 'todos').strip()
    ordem = (request.GET.get('ordem') or 'nome').strip()
    filtros_validos = {
        'todos': 'Todos',
        'personagens': 'Com personagens',
        'customizados': 'Perfil customizado',
        'equipe': 'Equipe',
    }
    ordens_validas = {
        'nome': 'Nome',
        'personagens': 'Mais personagens',
        'atividade': 'Atividade recente',
    }
    if filtro not in filtros_validos:
        filtro = 'todos'
    if ordem not in ordens_validas:
        ordem = 'nome'

    public_character_q = Q(personagens__publico=True, personagens__arquivado=False)
    custom_profile_q = (
        Q(profile__bio__gt='')
        | Q(profile__avatar_url__gt='')
        | Q(profile__banner_url__gt='')
        | Q(profile__background_url__gt='')
        | (Q(profile__profile_theme__isnull=False) & ~Q(profile__profile_theme='bonfire'))
        | (Q(profile__avatar_frame__isnull=False) & ~Q(profile__avatar_frame=''))
        | (Q(profile__profile_effect__isnull=False) & ~Q(profile__profile_effect=''))
    )
    base = (User.objects.filter(is_active=True)
            .select_related('profile')
            .annotate(public_character_count=Count(
                'personagens',
                filter=public_character_q,
                distinct=True,
            ))
            .annotate(public_character_updated=Max(
                'personagens__atualizado_em',
                filter=public_character_q,
            )))
    if q:
        base = base.filter(
            Q(username__icontains=q)
            | Q(profile__bio__icontains=q)
            | Q(personagens__nome__icontains=q, personagens__publico=True, personagens__arquivado=False)
        ).distinct()
    else:
        base = base.filter(
            Q(public_character_count__gt=0)
            | custom_profile_q
            | Q(is_staff=True)
        )

    if filtro == 'personagens':
        base = base.filter(public_character_count__gt=0)
    elif filtro == 'customizados':
        base = base.filter(custom_profile_q)
    elif filtro == 'equipe':
        base = base.filter(is_staff=True)

    if ordem == 'personagens':
        base = base.order_by('-public_character_count', 'username')
    elif ordem == 'atividade':
        base = base.order_by('-public_character_updated', 'username')
    else:
        base = base.order_by('username')

    users_page = Paginator(base, 18).get_page(request.GET.get('page'))
    ids = [u.pk for u in users_page.object_list]
    public_chars = {}
    if ids:
        qs = (TbPersonagem.objects.filter(dono_id__in=ids, publico=True, arquivado=False)
              .select_related('id_raca')
              .prefetch_related('classes__id_classe')
              .order_by('-atualizado_em'))
        for p in qs:
            bucket = public_chars.setdefault(p.dono_id, [])
            if len(bucket) < 3:
                bucket.append(_personagem_card(p))

    users_list = list(users_page.object_list)
    for u in users_list:
        # select_related('profile') já carregou; garante existência sem N+1 de save.
        if getattr(u, 'profile', None) is None:
            UserProfile.objects.get_or_create(user=u)
    # F2 — badges/títulos de TODOS os usuários da página em lote (sem N+1).
    perfil_badges = _badges.perfil_badges_batch(users_list)
    cards = []
    for u in users_list:
        profile = getattr(u, 'profile', None) or UserProfile.objects.get_or_create(user=u)[0]
        info = perfil_badges.get(u.pk, {})
        cards.append({
            'user': u,
            'profile': profile,
            'appearance': _appearance_context(profile.profile_theme, profile.avatar_frame,
                                              profile.profile_effect, profile.theme_custom),
            'public_count': int(getattr(u, 'public_character_count', 0) or 0),
            'characters': public_chars.get(u.pk, []),
            'badges': info.get('badges', []),
            'titulo': info.get('titulo'),
        })

    def _querystring(**updates):
        params = request.GET.copy()
        params.pop('page', None)
        for key, value in updates.items():
            if value in (None, '', 'todos') and key == 'filtro':
                params.pop(key, None)
            elif value in (None, '', 'nome') and key == 'ordem':
                params.pop(key, None)
            elif value in (None, '') and key == 'q':
                params.pop(key, None)
            else:
                params[key] = value
        encoded = params.urlencode()
        return ('?' + encoded) if encoded else '?'

    base_querystring = _querystring()
    page_query_prefix = base_querystring + ('&' if base_querystring != '?' else '')

    return render(request, 'home/pages/jogadores.html', {
        'page_title': 'Jogadores',
        'q': q,
        'filtro': filtro,
        'ordem': ordem,
        'filter_options': [
            {'key': key, 'label': label, 'url': _querystring(filtro=key)}
            for key, label in filtros_validos.items()
        ],
        'sort_options': [
            {'key': key, 'label': label}
            for key, label in ordens_validas.items()
        ],
        'base_querystring': base_querystring,
        'page_query_prefix': page_query_prefix,
        'cards': cards,
        'page_obj': users_page,
        'total_encontrados': users_page.paginator.count,
    })


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


def _site_classes_view(request):
    classes = [_site_classe(doc) for doc in _site_docs('classes', [('Nome', 1)])]
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
        'total_habilidades': _site_count('class_features'),
        'total_subclasses': _site_count('subclasses'),
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


def _tag_verb_rx(name):
    parts = [p for p in _normalize_key(str(name or '').replace('-', '_')).split('_') if p]
    return r'_'.join(re.escape(p) for p in parts)


def _tag_block(tag, head):
    m = re.match(r'^%s\s*\{(.*)\}\s*$' % _tag_verb_rx(head), str(tag or '').strip(), re.I | re.S)
    return m.group(1) if m else None


def _tag_levels(tags_json, verb):
    """Extrai os níveis de uma tag de classe como `verb{4, 8, 12, ...}`."""
    for tag in (tags_json or []):
        body = _tag_block(tag, verb)
        if body:
            return {int(n) for n in re.findall(r'\d+', body)}
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


def _site_classe_detail_view(request, slug):
    classe_doc = _site_one('classes', {'Slug': slug})
    if not classe_doc:
        raise Http404("Classe nao encontrada")

    all_classes = [_site_classe(doc) for doc in _site_docs('classes', [('Nome', 1)])]
    classes_by_id = {classe.id_classe: classe for classe in all_classes}
    classe = _site_classe(classe_doc)
    classes_by_id[classe.id_classe] = classe

    subclass_docs = _site_docs('subclasses', [('Nome', 1)], {'Id_Classe': classe.id_classe})
    subclasses = [_site_subclasse(doc, classes_by_id) for doc in subclass_docs]
    subclasses_by_id = {sub.id_subclasse: sub for sub in subclasses}
    selected_subclass_slug = request.GET.get('subclasse', '')

    habilidade_docs = _site_docs('class_features', [('NivelAdquirido', 1), ('Nome', 1)], {'Id_Classe': classe.id_classe})
    all_habilidades = [_site_habilidade(doc, classes_by_id, subclasses_by_id) for doc in habilidade_docs]
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
        _site_recurso(doc, classes_by_id, subclasses_by_id)
        for doc in _site_docs('class_resources', [('Id_Subclasse', 1), ('Id_Recurso', 1)], {'Id_Classe': classe.id_classe})
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


def _site_racas_view(request):
    racas = [_site_raca(doc) for doc in _site_docs('races', [('Nome', 1)])]
    context = {
        'raca': None,
        'all_racas': racas,
        'selected_raca_id': None,
        'tracos_base': [],
        'linhagens': [],
        'total_linhagens': _site_count('lineages'),
        'total_tracos': _site_count('racial_traits'),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


def _site_raca_detail_view(request, slug):
    raca_doc = _site_one('races', {'Slug': slug})
    if not raca_doc:
        raise Http404("Raca nao encontrada")
    raca = _site_raca(raca_doc)
    racas = [_site_raca(doc) for doc in _site_docs('races', [('Nome', 1)])]
    tracos = [_site_traco(doc) for doc in _site_docs('racial_traits', [('NivelRequisito', 1), ('Nome', 1)])]
    tracos_base = [traco for traco in tracos if traco.id_raca_id == raca.id_raca]
    tracos_por_linhagem = {}
    for traco in tracos:
        if traco.id_linhagem_id:
            tracos_por_linhagem.setdefault(traco.id_linhagem_id, []).append(traco)

    linhagens = [
        _site_linhagem(doc, tracos_por_linhagem.get(doc.get('Id_Linhagem'), []))
        for doc in _site_docs('lineages', [('Nome', 1)], {'Id_Raca': raca.id_raca})
    ]

    context = {
        'raca': raca,
        'all_racas': racas,
        'selected_raca_id': raca.id_raca,
        'tracos_base': tracos_base,
        'linhagens': linhagens,
        'total_linhagens': _site_count('lineages'),
        'total_tracos': _site_count('racial_traits'),
        'can_edit_wiki': request.user.is_staff,
    }
    if is_ajax(request):
        return render(request, 'home/partials/raca_detail_content.html', context)
    return render(request, 'home/pages/raca_detail.html', context)


def regras_punicoes_view(request):
    return render(request, 'home/pages/regras_punicoes.html')


def guia_mestres_view(request):
    return render(request, 'home/pages/guia_mestres.html')


def _parse_site_date(value):
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
    db_error = ''
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
        db_error = str(exc)

    context = {
        'quests': quests,
        'search': search,
        'status': status,
        'db_error': db_error,
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
    from .character_engine import _norm_skill_slug
    for t in (tags_json or []):
        inner = _tag_block(t, 'skills_lvl1')
        if inner is not None:
            mn = re.search(r'pick:\s*(\d+)', inner)
            ml = re.search(r'\[([^\]]*)\]', inner)
            lista = ([_norm_skill_slug(x) for x in ml.group(1).split(',') if x.strip()]
                     if ml else None)
            return (int(mn.group(1)) if mn else 2, lista)
    return (2, None)


_PROF_SKILL_RE = re.compile(r'(?<![a-z0-9_-])prof:([a-z0-9_-]+)')
_PROF_MENU_MARKERS = ('define{', 'list{', 'table{', 'while_active', 'while{',
                      'cast{', 'instant{', 'trigger=', 'action=')


def _classe_pericias_fixas(classe):
    """Slugs canônicos de perícia que FEATURES de nível 1 da classe concedem FIXAS (tag
    plana `prof:<skill>`, ex.: Mago/'Estudo Arcano' -> arcanismo). Bloqueio universal:
    perícia ganha pela classe não pode ser reescolhida em nenhuma lista do criador."""
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    from .models import TbClassehabilidade
    if classe is None:
        return set()
    out = set()
    for h in TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido__lte=1):
        for tag in (h.tags_json or []):
            s = str(tag)
            if any(mk in s.lower() for mk in _PROF_MENU_MARKERS):
                continue
            for m in _PROF_SKILL_RE.finditer(s):
                sl = _norm_skill_slug(m.group(1))
                if sl in _SKILL_INFO:
                    out.add(sl)
    return out


_ARMADURA_PROF_TOKEN = {
    'armadura_leve': 'leve',
    'armadura_media': 'media',
    'armadura_pesada': 'pesada',
    'escudos': 'escudo',
}
_PICK_ARMA_RE = re.compile(r'pick:arma:(\{[^}]*\}|[A-Za-z0-9_+\-]+)(?:\([^)]*\))*')
_PICK_OPCAO_NV_RE = re.compile(r'pick:opcao:([a-z0-9_-]+)(?:\([^)]*\))?(?::(\{[^}]*\}|[A-Za-z0-9_+\-]+))?(?:\([^)]*\))*')
_PICK_EXPERTISE_RE = re.compile(r'pick:pericia_expertise:(\{[^}]*\}|[A-Za-z0-9_+\-]+)(?:\([^)]*\))*')
_PICK_CLASSE_PROF_RE = re.compile(
    r'pick:(instrumento|ferramenta|ferramenta_artesao|ferramenta_ou_instrumento|ferramenta_artesao_ou_instrumento):'
    r'(\{[^}]*\}|[A-Za-z0-9_+\-]+)(?:\([^)]*\))*'
)


def _classe_armaduras_prof(classe):
    out = []
    for tag in (getattr(classe, 'tags_json', None) or []):
        body = _tag_block(tag, 'prof')
        if body is None:
            continue
        for token in [x.strip() for x in body.split(',') if x.strip()]:
            val = _ARMADURA_PROF_TOKEN.get(token)
            if val and val not in out:
                out.append(val)
    return out


def _count_expr_for_level(expr, level):
    expr = (expr or '').strip()
    if expr.startswith('{'):
        return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*([+-]?\d+)', expr)
                   if int(lv) <= level) or None
    if re.match(r'^[+-]?\d+$', expr):
        return int(expr)
    return None


def _resource_ref_from_tag(tag):
    m = re.search(r'=\s*(?:resource|recurso)\s+([a-z0-9_-]+)', str(tag))
    if not m:
        m = re.search(r'(?:resource|recurso)\{([a-z0-9_-]+)\}', str(tag))
    return m.group(1) if m else None


def _choice_resource_limit(classe, nivel, resource_slug):
    if not resource_slug:
        return None
    from .character_engine import RESOURCE_TIPO_CHOICE, _resource_max_at, _resource_tipo
    # tags referenciam o recurso com underscore (ex.: maestria_com_armas), mas o slug
    # em TbRecursoclasse é gerado com hífen (ex.: maestria-com-armas); casa as duas formas.
    alvo = resource_slug.replace('_', '-')
    qs = TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True)
    todos = list(qs)
    exatos = [r for r in todos if (r.slug or '').replace('_', '-') == alvo]
    parciais = [r for r in todos if alvo in (r.slug or '').replace('_', '-')]
    candidatos = exatos + [r for r in parciais if r not in exatos]
    r = next((rec for rec in candidatos if _resource_tipo(rec) == RESOURCE_TIPO_CHOICE), None)
    if r is None and candidatos:
        r = candidatos[0]
    return _resource_max_at(r, nivel) if r else None


def _pick_count_for_tag(classe, nivel, expr, tag):
    val = _count_expr_for_level(expr, nivel)
    if val is not None:
        return val
    if (expr or '').strip() in ('N', '+', ''):
        return _choice_resource_limit(classe, nivel, _resource_ref_from_tag(tag))
    return None


def _classe_nv1_sources(classe):
    return [classe] + list(TbClassehabilidade.objects.filter(
        id_classe=classe, id_subclasse__isnull=True, niveladquirido=1))


def _classe_maestria_n(classe, nivel=1):
    total = 0
    for src in _classe_nv1_sources(classe):
        for tag in (getattr(src, 'tags_json', None) or []):
            for m in _PICK_ARMA_RE.finditer(str(tag)):
                total += _pick_count_for_tag(classe, nivel, m.group(1), tag) or 0
    return total


def _criador_armas():
    """Catálogo de armas (TbItemMundano categoria=arma) com suas maestrias resolvidas."""
    from .models import TbItemMundano, TbOpcaojogo
    from .picks import normalize_slug
    # tags `maestrias{...}` da arma usam '_'; o catálogo TbOpcaojogo usa '-'. Normaliza
    # '_'→'-' NO LOOKUP p/ nome legível (sem reescrever a referência da arma).
    mast = {normalize_slug(o.slug): o.nome for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
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
        _mec = mecanica_de_tags(w.tags_json, w.subcategoria)
        out.append({'slug': w.slug, 'nome': w.nome, 'dano': dano_display(_mec),
                    'propriedades': propriedades_display(_mec),
                    'cat': sub_label.get(w.subcategoria, w.subcategoria or 'Arma'),
                    'maestrias': [mast.get(normalize_slug(s), s) for s in mslugs]})
    return out


def _classe_escolhas_nv1(classe):
    from .character_engine import _SKILL_INFO, _norm_skill_slug
    estilo_n = expertise_n = 0
    expertise_fixa = []
    opcao_picks = []
    for src in _classe_nv1_sources(classe):
        for tag in (getattr(src, 'tags_json', None) or []):
            text = str(tag)
            for m in _PICK_OPCAO_NV_RE.finditer(text):
                slug, expr = m.group(1), m.group(2)
                n = _pick_count_for_tag(classe, 1, expr, text) or 0
                if n > 0:
                    opcao_picks.append({'slug': slug, 'n': n})
                if slug.replace('_', '-') == 'estilo-de-luta':
                    estilo_n += n
            for m in _PICK_EXPERTISE_RE.finditer(text):
                expr = (m.group(1) or '').strip()
                n = _pick_count_for_tag(classe, 1, expr, text)
                if n is not None:
                    expertise_n += n
                elif expr.startswith('{') and 'classlvl' not in expr:
                    expertise_fixa += [_norm_skill_slug(s) for s in re.split(r'[,\s|]+', expr.strip('{} '))
                                       if _norm_skill_slug(s) in _SKILL_INFO]
    return {'estilo_n': estilo_n, 'expertise_n': expertise_n,
            'expertise_fixa': expertise_fixa, 'opcao_picks': opcao_picks}


def _classe_prof_picks_nv1(classe):
    """Escolhas de proficiencia em ferramenta/instrumento declaradas por tags."""
    out = []
    for src in _classe_nv1_sources(classe):
        for tag in (getattr(src, 'tags_json', None) or []):
            body = _tag_block(tag, 'prof')
            if body is None and _tag_block(tag, 'multiclass_prof') is not None:
                continue
            text = body if body is not None else str(tag)
            for m in _PICK_CLASSE_PROF_RE.finditer(text):
                tipo, expr = m.group(1), (m.group(2) or '').strip()
                n = _pick_count_for_tag(classe, 1, expr, text) or 0
                if n > 0:
                    out.append({'tipo': tipo, 'n': n, 'fonte': getattr(src, 'nome', classe.nome)})
    return out


def _classe_prof_pick_options(tipo):
    qs = TbItemMundano.objects.filter(categoria='ferramenta')
    if tipo == 'instrumento':
        qs = qs.filter(subcategoria='instrumento')
    elif tipo == 'ferramenta_artesao':
        qs = qs.filter(subcategoria='ferramenta_artesao')
    elif tipo == 'ferramenta_artesao_ou_instrumento':
        qs = qs.filter(subcategoria__in=['ferramenta_artesao', 'instrumento'])
    return set(qs.values_list('nome', flat=True))


def _caster_subclasse(pc):
    """Subclasse de um TbPersonagemClasse SE já desbloqueada (nv >= nível-da-subclasse). Usada
    para tornar o pipeline de magia subclasse-aware — os third-casters (Cavaleiro Arcano,
    Trapaceiro Arcano) carregam a tag `spellcasting{slots:third,...}` e os recursos de
    progressão (truques/magias-preparadas/1o..4o) numa HABILIDADE/RECURSO DE SUBCLASSE."""
    from .character_engine import _subclass_unlocked
    return pc.id_subclasse if _subclass_unlocked(pc) else None


def _classe_spellcasting_info(classe, nivel_habilidades=1, subclasse=None):
    from .character_engine import spell_scope_names
    # base (id_subclasse null) + habilidades da SUBCLASSE do personagem (third-casters
    # carregam o spellcasting{} numa habilidade de subclasse de nível 3).
    cond = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclasse is not None:
        cond |= Q(id_subclasse=subclasse)
    qs = TbClassehabilidade.objects.filter(cond)
    if nivel_habilidades is not None:
        qs = qs.filter(niveladquirido__lte=nivel_habilidades)
    qs = qs.order_by('niveladquirido', 'id_habilidade')
    sc, mods = None, []
    for src in [classe] + list(qs):
        for tag in (getattr(src, 'tags_json', None) or []):
            body = _tag_block(tag, 'spellcasting')
            if body is not None:
                if re.search(r'\b(?:slots|lista)\s*:', body):
                    sc = body
                else:
                    mods.append(body)
    if not sc:
        return None
    for body in mods:
        mm = re.search(r'prepara\s*:?=\s*([a-z_-]+)', body)
        if mm:
            sc = re.sub(r'prepara\s*:\s*[a-z_-]+', 'prepara:%s' % mm.group(1), sc)
    lista_raw = (re.search(r'lista\s*:\s*([a-z0-9_|,-]+)', sc) or [None, ''])[1]
    lista_slugs = [x.strip() for x in re.split(r'[|,]', lista_raw) if x.strip()]
    slots_raw = (re.search(r'slots\s*:\s*([^,}]+)', sc) or [None, 'full'])[1].strip()
    slots_resource = (re.search(r'resource\s*:\s*([a-z0-9_-]+)', slots_raw) or [None, None])[1]
    return {
        'raw': sc,
        'ability': (re.search(r'ability\s*:\s*([\w|]+)', sc) or [None, 'int'])[1],
        'lista': lista_slugs,
        'lista_nomes': spell_scope_names(lista_slugs) or [classe.nome],
        'prepara': (re.search(r'prepara\s*:\s*([a-z_-]+)', sc) or [None, None])[1],
        'prep_formula': (re.search(r'prep_limite\s*:\s*([^,}]+)', sc) or [None, None])[1],
        'slots': slots_raw.split('(', 1)[0].strip(),
        'slots_raw': slots_raw,
        'slots_resource': slots_resource,
    }


def _spell_list_q(lista_nomes):
    q = Q(pk__in=[])
    for nome in lista_nomes or []:
        q |= Q(classes__icontains=nome)
    return q


def _max_spell_level_for_slots(nivel, slots):
    """FALLBACK documentado. O teto REAL de nível de magia conjurável vem do TOPO da tabela de
    slots da PRÓPRIA classe (ver `_pendencias_magias`/`_magias_preparadas_info`, que leem
    `_classe_slot_table`). Estas fórmulas fechadas só valem como rede de segurança quando não
    houver tabela de slots carregada — daí o ramo `half` seguir a mesma escada da tabela
    (1º@nv2, 2º@nv5, 3º@nv9, 4º@nv13, 5º@nv17)."""
    if slots == 'half':
        return min(5, ((nivel + 1) // 2 + 1) // 2)
    if slots == 'third':
        if nivel >= 19:
            return 4
        if nivel >= 13:
            return 3
        if nivel >= 7:
            return 2
        return 1 if nivel >= 3 else 0
    if slots == 'pact':
        return min(5, max(1, (nivel + 1) // 2))
    return min(9, (nivel + 1) // 2)


def _classe_slot_table(classe, nivel, subclasse=None):
    """Le os recursos table-only 1o..9o da classe (e da subclasse, quando informada) para
    total de slots. Third-casters (Cavaleiro/Trapaceiro Arcano) guardam a tabela 1o..4o na
    SUBCLASSE — sem incluí-la, um conjurador-de-um-terço mostraria zero slots."""
    from .character_engine import _resource_max_at, _resource_tipo, RESOURCE_TIPO_TABLE_ONLY
    out = {}
    if not classe:
        return out
    cond = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclasse is not None:
        cond |= Q(id_subclasse=subclasse)
    for r in TbRecursoclasse.objects.filter(cond):
        slug = (r.slug or '').strip().lower()
        if not re.match(r'^[1-9]o$', slug):
            continue
        if _resource_tipo(r) != RESOURCE_TIPO_TABLE_ONLY:
            continue
        val = _resource_max_at(r, nivel)
        if val is not None:
            lv = int(slug[0])
            out[lv] = max(0, val, out.get(lv, 0))
    return out


def _full_caster_slot_source(casters):
    for c in casters:
        if c['info']['slots'] == 'full':
            return c['pc'].id_classe
    return (TbClasse.objects.filter(slug='mago').first()
            or TbClasse.objects.filter(slug='bardo').first()
            or (casters[0]['pc'].id_classe if casters else None))


def _spell_slot_totals(casters):
    slot_casters = [c for c in casters if c['info']['slots'] in {'full', 'half', 'third'}]
    if not slot_casters:
        return {}
    if len(slot_casters) == 1:
        pc = slot_casters[0]['pc']
        return _classe_slot_table(pc.id_classe, int(pc.nivel or 0), _caster_subclasse(pc))
    effective = 0
    for c in slot_casters:
        nivel = int(c['pc'].nivel or 0)
        kind = c['info']['slots']
        if kind == 'full':
            effective += nivel
        elif kind == 'half':
            effective += nivel // 2
        elif kind == 'third':
            effective += nivel // 3
    return _classe_slot_table(_full_caster_slot_source(slot_casters), max(1, effective))


def _spell_slot_rows(personagem, totals):
    atuais = {r.nome: r for r in personagem.recursos.filter(nome__startswith='spell-slot:')}
    rows = []
    for nivel in range(1, 10):
        total = int(totals.get(nivel) or 0)
        key = 'spell-slot:%d' % nivel
        pr = atuais.get(key)
        atual = min(int(getattr(pr, 'atual', total) or 0), total) if pr else total
        rows.append({'nivel': nivel, 'key': key, 'total': total, 'atual': max(0, atual)})
    return rows


_REST_LABELS = {
    'long-rest': 'day',
    'long_rest': 'day',
    'day': 'day',
    'short-rest': 'short-rest',
    'short_rest': 'short-rest',
    'short-or-long': 'rest',
    'short_or_long': 'rest',
    'rest': 'rest',
}
_REST_UNITS_RE = r'(long[-_]rest|short[-_]rest|short[-_]or[-_]long|rest|day)'
_INNATE_RESOURCE_PREFIX = 'spell-innate:'


def _uses_eval_ctx(ficha, classlvl=None):
    ficha = ficha or {}
    ctx = {
        'lvl': int(ficha.get('nivel_total') or classlvl or 1),
        'classlvl': int(classlvl or ficha.get('nivel_total') or 1),
        'pb': int(ficha.get('bonus_proficiencia') or 0),
    }
    attrs = ficha.get('atributos') or {}
    mods = []
    for sig, en in {'FOR': 'str', 'DES': 'dex', 'CON': 'con', 'INT': 'int', 'SAB': 'wis', 'CAR': 'cha'}.items():
        data = attrs.get(sig) or {}
        mod = int(data.get('mod') or 0)
        val = int(data.get('valor') or 0)
        ctx[en + '_mod'] = mod
        ctx[en + '_score'] = val
        if en in ('int', 'wis', 'cha'):
            mods.append(mod)
    if mods:
        ctx['spell_mod'] = max(mods)
    return ctx


def _uses_count_value(raw, ctx=None):
    raw = str(raw or '').strip().lower()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    ctx = ctx or {}
    if raw in ctx:
        return int(ctx[raw])
    try:
        from .character_engine import _eval_formula
        val = _eval_formula(raw, ctx)
        return int(val) if val is not None else None
    except Exception:
        return None


def _uses_label(count, reset):
    key = (reset or '').replace('_', '-')
    suffix = _REST_LABELS.get(reset or '', _REST_LABELS.get(key, reset or ''))
    return '%s/%s' % (count, suffix) if count and suffix else ''


def _uses_meta_from_text(text, ctx=None):
    s = str(text or '').lower()
    if re.search(r'\bat-will\b', s):
        return {'maximo': 0, 'reset': 'at-will', 'label': 'at-will'}

    patterns = [
        r'uses\s*\{\s*([^,{}]+)\s*,\s*reset\s*:\s*' + _REST_UNITS_RE,
        r'resource_cost\s*:\s*([^,\s{}|:]+)\s*/\s*' + _REST_UNITS_RE,
        r'\b([^,\s{}|:]+)\s*/\s*' + _REST_UNITS_RE,
    ]
    for rx in patterns:
        m = re.search(rx, s)
        if not m:
            continue
        count = _uses_count_value(m.group(1), ctx)
        if count is None:
            continue
        reset = m.group(2)
        return {'maximo': max(0, count), 'reset': reset, 'label': _uses_label(count, reset)}
    return None


def _uses_label_from_text(text, ctx=None):
    meta = _uses_meta_from_text(text, ctx)
    return meta.get('label', '') if meta else ''


def _iter_tag_blocks(text, head):
    s = str(text or '')
    rx = re.compile(r'\b%s\s*\{' % _tag_verb_rx(head), re.I)
    pos = 0
    while True:
        m = rx.search(s, pos)
        if not m:
            return
        open_pos = m.end() - 1
        depth = 0
        end = None
        for i in range(open_pos, len(s)):
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            return
        yield s[open_pos + 1:end]
        pos = end + 1


def _innate_resource_key(origem, spell_slug):
    origem_slug = slugify(origem or 'feature') or 'feature'
    spell_slug = slugify(spell_slug or 'spell') or 'spell'
    base = '%s:%s' % (origem_slug, spell_slug)
    key = _INNATE_RESOURCE_PREFIX + base
    if len(key) <= 100:
        return key
    digest = hashlib.sha1(base.encode('utf-8')).hexdigest()[:10]
    return '%s%s:%s:%s' % (_INNATE_RESOURCE_PREFIX, origem_slug[:28], spell_slug[:34], digest)


def _resource_resets_on_rest(reset, longo):
    reset = (reset or '').strip().lower().replace('_', '-')
    if longo:
        return reset in ('long-rest', 'day', 'short-rest', 'short-or-long', 'rest')
    return reset in ('short-rest', 'short-or-long', 'rest')


def _innate_spell_uses(personagem, ficha=None):
    """Mapeia (fonte, spell_slug) -> metadados de uso inato vindos das tags."""
    from .character_engine import (
        _features_de_classe, _tracos_raciais, _antecedente, _talentos,
        _features_de_itens, _features_de_opcoes,
    )
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id'))
    features = (_features_de_classe(classes) + _tracos_raciais(personagem)
                + _antecedente(personagem) + _talentos(personagem)
                + _features_de_itens(personagem) + _features_de_opcoes(personagem))
    catalog = set(TbMagia.objects.values_list('slug', flat=True))
    out = {}
    for (_origem, _fonte, obj, _cl) in features:
        fonte = getattr(obj, 'nome', '') or ''
        tags = [str(t) for t in (getattr(obj, 'tags_json', None) or [])]
        ctx = _uses_eval_ctx(ficha, _cl)
        source_meta = None
        for t in tags:
            source_meta = source_meta or _uses_meta_from_text(t, ctx)
        for t in tags:
            for body in _iter_tag_blocks(t, 'cast'):
                if not re.search(r'no_slot', body.lower()):
                    continue
                meta = _uses_meta_from_text(body, ctx) or _uses_meta_from_text(t, ctx) or source_meta
                if not meta:
                    continue
                for slug in re.findall(r'spell:([a-z0-9-]+)', body):
                    if slug in catalog:
                        out[(fonte, slug)] = meta
    return out


def _innate_spell_labels(personagem):
    """Compatibilidade: (fonte, spell_slug) -> 1/day, 3/day etc."""
    return {k: v.get('label', '') for k, v in _innate_spell_uses(personagem).items()}


def _attr_sig_from_spell_ability(ability_raw):
    first = (ability_raw or 'int').split('|', 1)[0].strip().lower()
    return {'str': 'FOR', 'for': 'FOR', 'dex': 'DES', 'des': 'DES',
            'con': 'CON', 'int': 'INT', 'wis': 'SAB', 'sab': 'SAB',
            'cha': 'CAR', 'car': 'CAR'}.get(first, 'INT')


def _magias_sheet_info(personagem, ficha, essencia_pendentes):
    from .models import TbPersonagemMagia
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id'))
    casters = []
    for pc in classes:
        info = _classe_spellcasting_info(pc.id_classe, nivel_habilidades=int(pc.nivel or 1),
                                         subclasse=_caster_subclasse(pc))
        if info:
            casters.append({'pc': pc, 'info': info})
    primary = casters[0] if casters else None
    spellcasting = None
    if primary:
        sig = _attr_sig_from_spell_ability(primary['info']['ability'])
        mod = int((((ficha.get('atributos') or {}).get(sig) or {}).get('mod')) or 0)
        pb = int(ficha.get('bonus_proficiencia') or 0)
        spellcasting = {
            'classe': primary['pc'].id_classe.nome,
            'ability': sig,
            'ability_nome': {'INT': 'Inteligencia', 'SAB': 'Sabedoria', 'CAR': 'Carisma',
                             'FOR': 'Forca', 'DES': 'Destreza', 'CON': 'Constituicao'}.get(sig, sig),
            'mod': mod,
            'cd': 8 + pb + mod,
            'ataque': pb + mod,
            'slots_kind': primary['info']['slots'],
            'slots_resource': primary['info'].get('slots_resource'),
            'prepara': primary['info'].get('prepara'),
        }

    innate_uses = _innate_spell_uses(personagem, ficha)
    innate_rows = {r.nome: r for r in personagem.recursos.filter(nome__startswith=_INNATE_RESOURCE_PREFIX)}
    magias_pers = list(TbPersonagemMagia.objects.filter(id_personagem=personagem)
                       .select_related('id_magia').order_by('nivel', 'nome'))
    lista = []
    for m in magias_pers:
        slug = getattr(m.id_magia, 'slug', '') or slugify(m.nome or '')
        innate_meta = innate_uses.get((m.origem or '', slug), {}) if m.sempre_preparada else {}
        innate_label = innate_meta.get('label', '') if innate_meta else ''
        innate_max = int(innate_meta.get('maximo') or 0) if innate_meta else 0
        innate_key = _innate_resource_key(m.origem or '', slug) if innate_max > 0 else ''
        innate_row = innate_rows.get(innate_key) if innate_key else None
        innate_atual = min(int(innate_row.atual or 0), innate_max) if innate_row else innate_max
        known_auto = bool(primary and primary['info'].get('prepara') == 'conhecidas'
                          and not m.sempre_preparada
                          and ((m.origem or '') in ('', primary['pc'].id_classe.nome)))
        always_display = bool(m.sempre_preparada or known_auto)
        _mag = m.id_magia
        lista.append({
            'id': m.id, 'slug': slug, 'nivel': m.nivel, 'nome': m.nome,
            'preparada': bool(m.preparada), 'sempre_preparada': always_display,
            'known_auto': known_auto,
            'origem': m.origem or '', 'escola': getattr(m.id_magia, 'escola', '') or '',
            'descricao': (getattr(_mag, 'descricao', '') or '').strip(),
            'em_niveis_superiores': (getattr(_mag, 'em_niveis_superiores', '') or '').strip(),
            'alcance': (getattr(_mag, 'alcance', '') or '').strip(),
            'duracao': (getattr(_mag, 'duracao', '') or '').strip(),
            'casting_time': (getattr(_mag, 'casting_time', '') or '').strip(),
            'componentes': (getattr(_mag, 'componentes', '') or '').strip(),
            'concentracao': bool(getattr(_mag, 'concentracao', False)),
            'ritual': bool(getattr(_mag, 'ritual', False)),
            'innate_label': innate_label,
            'innate_key': innate_key,
            'innate_max': innate_max,
            'innate_atual': max(0, innate_atual),
            'innate_reset': innate_meta.get('reset', '') if innate_meta else '',
        })

    by_level = {n: [] for n in range(0, 10)}
    for m in lista:
        by_level.setdefault(int(m['nivel'] or 0), []).append(m)

    totals = _spell_slot_totals(casters)
    slots = _spell_slot_rows(personagem, totals) if totals else []
    slot_map = {r['nivel']: r for r in slots}

    mystic_resource = None
    if primary and primary['info']['slots'] == 'pact':
        wanted = primary['info'].get('slots_resource')
        from .character_engine import _recursos_consumiveis
        for r in _recursos_consumiveis(personagem, classes):
            if not wanted or r.get('slug') == wanted:
                if wanted and r.get('slug') != wanted:
                    continue
                mystic_resource = r
                break
        max_cycle = None
        for r in ficha.get('recursos_por_tipo', {}).get('table-only', []):
            if 'ciclo' in (r.get('slug') or '') or 'feitico' in slugify(r.get('nome') or ''):
                try:
                    max_cycle = int(str(r.get('valor')).strip())
                except (TypeError, ValueError):
                    pass
        if mystic_resource:
            spellcasting['mystic_resource'] = mystic_resource
            spellcasting['max_cycle'] = max_cycle

    grupos = []
    for nivel in range(0, 10):
        grupos.append({
            'nivel': nivel,
            'titulo': 'Truques' if nivel == 0 else '%do Nivel' % nivel,
            'magias': by_level.get(nivel, []),
            'slot': slot_map.get(nivel),
        })

    return {
        'lista': lista,
        'grupos': grupos,
        'slots': slots,
        'spellcasting': spellcasting,
        'n_preparadas': sum(1 for m in lista if m['preparada'] and not m['sempre_preparada']
                            and int(m.get('nivel') or 0) >= 1),
        'n_sempre': sum(1 for m in lista if m['sempre_preparada']),
        'total': len(lista),
        'essencia_pendentes': essencia_pendentes,
    }


def _consumiveis_ficha_cards(personagem, ficha):
    from .character_engine import _recursos_consumiveis, derive
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse'))
    atuais = {pr.nome: pr for pr in personagem.recursos.all()}
    cards = []
    seen_names = set()
    seen_slugs = set()
    for r in _recursos_consumiveis(personagem, classes):
        seen_names.add(r['nome'])
        seen_slugs.add(r.get('slug') or '')
        cards.append({
            'kind': 'recurso', 'id': r['slug'], 'nome': r['nome'],
            'subtitulo': r.get('classe') or '', 'atual': r['atual'], 'maximo': r['maximo'],
            'reset': r.get('reset') or 'manual',
        })
    for nome, val in (ficha.get('recursos') or {}).items():
        nome_limpo = str(nome or '').strip()
        if not nome_limpo or nome_limpo in seen_names or nome_limpo.split(':')[-1].strip() in seen_names:
            continue
        tag_slug = slugify(nome_limpo.split(':')[-1].strip() or nome_limpo)
        if tag_slug in seen_slugs:
            continue
        m = re.match(r'^\s*(\d+)\s*\(reset\s+([^)]+)\)\s*$', str(val or '').strip())
        if not m:
            continue
        mx = int(m.group(1))
        if mx <= 0:
            continue
        key = 'tag-resource:%s' % slugify(nome_limpo)[:82]
        pr = atuais.get(key)
        atual = min(int(pr.atual or 0), mx) if pr else mx
        cards.append({
            'kind': 'recurso', 'id': 'tag:%s' % slugify(nome_limpo),
            'db_nome': key, 'nome': nome_limpo, 'subtitulo': 'habilidade',
            'atual': max(0, atual), 'maximo': mx, 'reset': m.group(2),
        })
    for it in (ficha.get('inventario') or []):
        if not it.get('consumivel'):
            continue
        qtd = max(0, int(it.get('qtd') or 0))
        cards.append({
            'kind': 'item', 'id': it['id'], 'nome': it['nome'],
            'subtitulo': it.get('raridade') or it.get('consumivel_tipo') or 'item',
            'atual': qtd, 'maximo': qtd, 'reset': '',
        })
    return cards


def _classe_conjuracao(classe):
    from .models import TbRecursoclasse, TbMagia
    from .character_engine import RESOURCE_TIPO_CHOICE, _resource_max_at, _resource_tipo
    info = _classe_spellcasting_info(classe, nivel_habilidades=1)
    if not info:
        return None

    def res_v1(substrs):
        needles = [s.replace('_', '-') for s in substrs] + [s.replace('-', '_') for s in substrs]
        for r in TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True):
            slug = (r.slug or '').lower()
            if any(s in slug for s in needles) and _resource_tipo(r) == RESOURCE_TIPO_CHOICE:
                val = _resource_max_at(r, 1)
                if val is not None:
                    return val
        for r in TbRecursoclasse.objects.filter(id_classe=classe, id_subclasse__isnull=True):
            if any(s in (r.slug or '').lower() for s in needles):
                val = _resource_max_at(r, 1)
                if val is not None:
                    return val
        return None

    def magia_qs(nivel):
        return TbMagia.objects.filter(_spell_list_q(info['lista_nomes']), nivel=nivel).order_by('nome')

    magias_n = res_v1(['magias-conhecidas', 'magias-preparadas'])
    truques = [{'slug': m.slug, 'nome': m.nome} for m in magia_qs(0)]
    nv1 = [{'slug': m.slug, 'nome': m.nome, 'escola': m.escola or ''} for m in magia_qs(1)]
    return {'ability': info['ability'], 'lista': info['lista'], 'lista_nomes': info['lista_nomes'],
            'truques_n': res_v1(['truque']) or 0, 'magias_n': magias_n,
            'magias_formula': None if magias_n is not None else info['prep_formula'],
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

def _spell_count_nv1(conj, base, mais2, mais1, asi_vals=(2, 1), asi_bonus=None):
    if conj.get('magias_n') is not None:
        return conj['magias_n']
    formula = conj.get('magias_formula')
    if formula:
        from .character_engine import _eval_formula
        ctx = {'classlvl': 1, 'lvl': 1}
        major, minor = asi_vals

        def _asi_add(sig):
            # asi_bonus (lista de pares atributo/valor) cobre as duas formas 2/1 e 1/1/1;
            # fallback p/ mais2/mais1 mantém compat com chamadas legadas (ex.: testes).
            if asi_bonus is not None:
                return sum(v for a, v in asi_bonus if a == sig)
            return (major if mais2 == sig else 0) + (minor if mais1 == sig else 0)
        for en, sig in _AB_SIG.items():
            score = int(base.get(sig, 8)) + _asi_add(sig)
            ctx[en + '_mod'] = (score - 10) // 2
        abil = conj.get('ability') or 'int'
        ctx['spell_mod'] = (max(ctx.get(a + '_mod', 0) for a in abil.split('|'))
                            if '|' in abil else ctx.get(abil + '_mod', 0))
        val = _eval_formula(formula, ctx)
        return max(1, int(val)) if val is not None else 0
    return 0


def _criador_armaduras():
    """Catálogo de armaduras+escudo (TbItemMundano categoria=armadura) com CA estruturada."""
    from .models import TbItemMundano
    out = []
    arms = []
    for a in TbItemMundano.objects.filter(categoria='armadura'):
        mec = mecanica_de_tags(a.tags_json, a.subcategoria)
        if mec['tipo_equip']:
            arms.append((mec['ca_base'] or 0, a, mec))
    for _cb, a, mec in sorted(arms, key=lambda x: x[0]):
        out.append({'slug': a.slug, 'nome': a.nome, 'ca': ca_display(mec), 'tipo_equip': mec['tipo_equip'],
                    'sub': a.subcategoria or '', 'forca_minima': mec['forca_minima'],
                    'furtividade': bool(mec['furtividade_desvantagem'])})
    return out


_SAVE_PT = {'str': 'FOR', 'for': 'FOR', 'forca': 'FOR', 'força': 'FOR',
            'dex': 'DES', 'des': 'DES', 'destreza': 'DES',
            'con': 'CON', 'constituicao': 'CON', 'constituição': 'CON',
            'int': 'INT', 'inteligencia': 'INT', 'inteligência': 'INT',
            'wis': 'SAB', 'sab': 'SAB', 'sabedoria': 'SAB',
            'cha': 'CAR', 'car': 'CAR', 'carisma': 'CAR'}


def _criador_resumo_md(txt, limit=320):
    """Primeiro parágrafo de um markdown, reduzido a texto curto para o painel de info
    do criador (mostrar o efeito da escolha SEM abrir outra aba)."""
    s = (txt or '').strip()
    if not s:
        return ''
    for bloco in re.split(r'\n\s*\n', s):
        b = re.sub(r'[#*_>`]+', '', bloco).strip()
        b = re.sub(r'\s+', ' ', b)
        if b:
            return b if len(b) <= limit else b[:limit].rsplit(' ', 1)[0] + '…'
    return ''


def _vertentes_catalogo():
    """Catálogo global de VERTENTES elementais, colhido de 'Vertente X' no texto dos traços."""
    from .models import TbTracoracial
    nomes = set()
    for tr in TbTracoracial.objects.all():
        txt = '%s\n%s' % (tr.pre_requisito or '', tr.descricao or '')
        nomes.update(m.group(1).strip() for m in re.finditer(r'Vertente\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ-]+)', txt))
        if 'vertente' in txt.lower():
            nomes.update(m.group(1).strip() for m in re.finditer(r'^\s*[-*]\s*\*\*([A-Za-zÀ-ÿ-]+)\b', txt, re.M))
    return [{'slug': slugify(n), 'nome': n} for n in sorted(nomes, key=lambda x: x.lower()) if slugify(n)]


def _essencia_vertentes(e, catalogo=None):
    from .models import TbTracoracial
    catalogo = catalogo if catalogo is not None else _vertentes_catalogo()
    txt = '\n'.join('%s\n%s' % (t.pre_requisito or '', t.descricao or '')
                    for t in TbTracoracial.objects.filter(id_essencia=e))
    norm = _norm_req(txt)
    return [v for v in catalogo if re.search(r'\b%s\b' % re.escape(v['slug']), norm)]


def _essencia_subescolha(e, catalogo=None):
    """Sub-escolha da essência: CLÃ/herança (via 'Clã X' no pré-requisito, ex.: Vampirismo)
    ou VERTENTE elemental (via 'Vertente X' na descrição). {'opcoes','label','tipo'} — 'opcoes'
    alimenta o mesmo seletor `cf-vertente` no criador."""
    from .character_engine import clas_de_essencia
    clas = clas_de_essencia(e)
    if clas:
        return {'opcoes': clas, 'label': 'Clã / Herança', 'tipo': 'cla'}
    return {'opcoes': _essencia_vertentes(e, catalogo), 'label': 'Vertente elemental', 'tipo': 'vertente'}


def _criador_catalogos():
    from .models import (TbRaca, TbLinhagem, TbEssencia, TbClasse, TbAntecedente,
                         TbTalento, TbTracoracial, TbIdioma, TbItemMundano, TbOpcaojogo,
                         TbClassehabilidade)
    from .character_engine import (_SKILL_INFO, _dado_de_vida_classe,
                                   clas_de_essencia, cla_de_traco)

    def _tracos_de(qs):
        # limite generoso: os traços mecânicos são o conteúdo principal do painel de raça
        # (aba "Traços"), não devem ser cortados curtos como um mero resumo.
        return [{'nome': t.nome, 'desc': _criador_resumo_md(t.descricao, 400)} for t in qs]

    # Perícias que a raça/linhagem/essência CONCEDE automaticamente (traços não-talento com
    # tag plana `prof:<skill>`, ex.: Orc/Presença Ameaçadora = ['prof:intimidacao']). O front
    # bloqueia essas perícias nas listas de classe/antecedente (já são próprias). Ignora tags
    # de menu/condicionais (define/list/while_active/…) para não contar o que não é estático.
    _prof_skill_re = re.compile(r'(?<![a-z_-])prof:([a-z0-9_-]+)')
    _prof_menu_active = ('define{', 'list{', 'table{', 'while_active', 'while{', 'cast{',
                         'instant{', 'trigger=', 'action=')

    def _pericias_concedidas(qs_traits, clas=None):
        # `clas` (heranças da essência) marca cada perícia com o clã do traço-fonte, p/ o
        # front só a exibir/bloquear quando o clã casa com o escolhido. clã='' = compartilhada.
        from .character_engine import _norm_skill_slug
        out, seen = [], set()
        for t in qs_traits:
            _cla = cla_de_traco(t, clas) if clas else ''
            for tag in (t.tags_json or []):
                s = str(tag)
                low = s.lower()
                if any(mk in low for mk in _prof_menu_active):
                    continue
                for m in _prof_skill_re.finditer(s):
                    sl = _norm_skill_slug(m.group(1))
                    if sl in _SKILL_INFO and sl not in seen:
                        seen.add(sl)
                        out.append({'slug': sl, 'fonte': t.nome, 'vertente': _cla})
        return out

    def _classe_pericias_concedidas(c):
        # Perícia que uma FEATURE de classe de nível 1 concede FIXA (tag plana `prof:<skill>`,
        # ex.: Mago/Estudo Arcano = ['always_active{prof:arcanismo}']). É uma perícia "ganha
        # pela classe" (não escolhida), então o front a bloqueia em TODAS as listas de perícia
        # (classe/antecedente/picks raciais) — mesmo tratamento das concedidas por raça.
        from .character_engine import _norm_skill_slug
        out, seen = [], set()
        habs = TbClassehabilidade.objects.filter(
            id_classe=c, id_subclasse__isnull=True, niveladquirido__lte=1)
        for h in habs:
            for tag in (h.tags_json or []):
                s = str(tag)
                if any(mk in s.lower() for mk in _prof_menu_active):
                    continue
                for m in _prof_skill_re.finditer(s):
                    sl = _norm_skill_slug(m.group(1))
                    if sl in _SKILL_INFO and sl not in seen:
                        seen.add(sl)
                        out.append({'slug': sl, 'fonte': h.nome, 'vertente': ''})
        return out

    def _classe_saves(c):
        out = []
        for tag in (c.tags_json or []):
            m = re.search(r'saves[_-]prof\s*\{([^}]*)\}', str(tag))
            if not m:
                continue
            for tok in m.group(1).split(','):
                sig = _SAVE_PT.get(tok.strip().lower())
                if sig and sig not in out:
                    out.append(sig)
        return out

    def _classe_features1(c):
        return [{'nome': h.nome, 'desc': _criador_resumo_md(h.descricao, 200)}
                for h in TbClassehabilidade.objects.filter(
                    id_classe=c, id_subclasse__isnull=True, niveladquirido__lte=1,
                    table_only=False).order_by('niveladquirido', 'nome')]

    racas = []
    for r in TbRaca.objects.all().order_by('nome'):
        linhagens = [{'slug': l.slug, 'nome': getattr(l, 'nome', l.slug),
                      'desc': _criador_resumo_md(getattr(l, 'descricao', '') or getattr(l, 'lore_presentation', ''), 200)}
                     for l in TbLinhagem.objects.filter(id_raca=r).order_by('nome')]
        tracos = _tracos_de(TbTracoracial.objects.filter(
            id_raca=r, talento_racial=False, id_linhagem__isnull=True,
            id_essencia__isnull=True, nivel_requisito__lte=1).order_by('nome'))
        racas.append({'slug': r.slug, 'nome': r.nome,
                      'permite_essencia': bool(getattr(r, 'permite_essencia', True)),
                      'tagline': (r.tagline or '').strip(),
                      'resumo': _criador_resumo_md(r.lore_presentation, 320),
                      'tracos': tracos,
                      'linhagens': linhagens})
    from . import picks as _picks
    classes = []
    for c in TbClasse.objects.all().order_by('nome'):
        n, lista = _parse_skills_lvl1(c.tags_json)
        sub = _tag_levels(c.tags_json, 'subclass-choices')
        esc1 = _classe_escolhas_nv1(c)
        classes.append({'slug': c.slug, 'nome': c.nome, 'pericias_n': n, 'pericias_lista': lista,
                        'pericias_concedidas': _classe_pericias_concedidas(c),
                        'equipamento': (c.equipamento or '').strip(),
                        'tagline': (c.tagline or '').strip(),
                        'hit_die': _dado_de_vida_classe(c) or 0,
                        'atributo_principal': (c.atributo_principal or '').strip(),
                        'saves': _classe_saves(c),
                        'features1': _classe_features1(c),
                        'resumo': _criador_resumo_md(c.tagline or '', 320),
                        'maestria_n': _classe_maestria_n(c, 1),
                        'estilo_n': esc1['estilo_n'], 'expertise_n': esc1['expertise_n'],
                        'expertise_fixa': esc1['expertise_fixa'],
                        'opcao_picks': esc1.get('opcao_picks', []),
                        'classe_prof_picks': _classe_prof_picks_nv1(c),
                        'conjuracao': _classe_conjuracao(c),
                        'armaduras_prof': _classe_armaduras_prof(c),
                        # grupos de escolha genéricos (kinds arma/opcao) que o JS renderiza
                        # em loop — substitui os catálogos dedicados maestria_n/estilo.
                        'pick_groups': _picks.resolve_builder(c, kinds={'arma', 'opcao'}),
                        'subclasse_nivel': min(sub) if sub else None})
    # catálogo global de vertentes + sub-escolha por essência: helpers no nível do módulo
    # (compartilhados com _criador_resolver, que valida a sub-escolha no POST).
    vertentes_catalogo = _vertentes_catalogo()

    def _vertente_de(t):
        # talentos elementais trazem "Vertente Sylph/Oread/Ifrit/Undine" no pré-requisito/descrição
        txt = _norm_req((t.pre_requisito or '') + ' ' + (t.descricao or ''))
        for v in vertentes_catalogo:
            if re.search(r'\b%s\b' % re.escape(v['slug']), txt):
                return v['slug']
        return ''

    def _traco_dict(t, linhagens=None):
        d = {'nome': t.nome, 'pre': (t.pre_requisito or '').strip(),
             'descricao': (t.descricao or '').strip(), 'vertente': _vertente_de(t)}
        if linhagens is not None:
            # talentos da RAÇA base podem trazer restrição de sub-raça no pré-requisito
            # (texto livre). Anota as linhagens exigidas para o front filtrar; [] = qualquer.
            lins, aceita_ess = _talento_linhagem_info(t, linhagens)
            d['linhagens'] = lins
            d['aceita_essencia'] = aceita_ess
        return d

    # Talentos raciais de nível 1, separados por fonte: raça base, linhagem (sub-raça) e
    # essência. O front mostra os da raça SEMPRE e adiciona os da linhagem/essência selecionadas.
    talentos_raca, talentos_linhagem, talentos_essencia = {}, {}, {}
    for r in TbRaca.objects.all():
        lins_r = list(TbLinhagem.objects.filter(id_raca=r))
        # POOL DA RAÇA-BASE: exclui traços de linhagem/essência (que carregam id_raca do
        # pai) — senão talentos raciais de uma linhagem vazam para toda a raça.
        qs = TbTracoracial.objects.filter(id_raca=r, talento_racial=True,
                                          id_linhagem__isnull=True, id_essencia__isnull=True,
                                          nivel_requisito__lte=1).order_by('nome')
        talentos_raca[r.slug] = [_traco_dict(t, lins_r) for t in qs]
    for l in TbLinhagem.objects.all():
        qs = TbTracoracial.objects.filter(id_linhagem=l, talento_racial=True,
                                          nivel_requisito__lte=1).order_by('nome')
        entries = [_traco_dict(t) for t in qs]
        # count_as: uma linhagem 'Sangue X' (Sálarin/Durkarn/Goruun) herda os talentos
        # raciais GERAIS da raça X — o criador passa a oferecê-los quando ela é selecionada.
        ca = _count_as_racial_targets(
            TbTracoracial.objects.filter(id_linhagem=l), linhagem_slug=l.slug)
        for t, other_lins in _talentos_raciais_count_as(ca, nivel_max=1):
            entries.append(_traco_dict(t, other_lins))
        if entries:
            talentos_linhagem[l.slug] = entries
    for e in TbEssencia.objects.all():
        _clas = clas_de_essencia(e)
        qs = TbTracoracial.objects.filter(id_essencia=e, talento_racial=True,
                                          nivel_requisito__lte=1).order_by('nome')
        if qs:
            ents = []
            for t in qs:
                d = _traco_dict(t)
                # essência com clã: o talento traz o clã (herança) no lugar da vertente,
                # p/ o front só oferecê-lo quando o clã escolhido casa (mesmo filtro).
                if _clas:
                    d['vertente'] = cla_de_traco(t, _clas)
                ents.append(d)
            talentos_essencia[e.slug] = ents

    # Escolhas de RAÇA automáticas: traços (não-talento) que concedem perícia/idioma/ferramenta
    # extra via tag pick:<tipo>:<n>[ de [lista]] (ex.: humano Habilidoso pick:pericia:2). O front
    # renderiza um seletor por escolha, reativo à raça/linhagem/essência, igual às escolhas de classe.
    # group(3) = conteúdo do modificador `(...)` (ex.: `de:[arcanismo, intuicao]`, `swap:long_rest`);
    # group(4) = lista pós-parêntese ` de [a, b]`. A lista `de` pode vir DENTRO dos parênteses
    # (`pick:pericia:1(de:[arcanismo, intuicao, persuasao])`, Educação Rubedo) — antes o grupo
    # `(?:\(...\))?` engolia isso e a lista era perdida (o front então oferecia QUALQUER perícia).
    _pick_re = re.compile(r'pick:(pericia|idioma|ferramenta):(\{[^}]*\}|[A-Za-z0-9_+\-]+)(?:\(([^)]*)\))?(?:\s+de\s+\[([^\]]*)\])?')

    def _racial_picks(qs_traits, clas=None):
        out = []
        for t in qs_traits:
            _cla = cla_de_traco(t, clas) if clas else ''
            for tag in (t.tags_json or []):
                for m in _pick_re.finditer(str(tag)):
                    de = [s.strip() for s in (m.group(4) or '').split(',') if s.strip()]
                    if not de and m.group(3):  # forma parentética: pick:pericia:1(de:[a, b, c])
                        md = re.search(r'de:\[([^\]]*)\]', m.group(3))
                        if md:
                            de = [s.strip() for s in md.group(1).split(',') if s.strip()]
                    n = _count_expr_for_level(m.group(2), 1) or 0
                    if n > 0:
                        out.append({'tipo': m.group(1), 'n': n, 'de': de,
                                    'fonte': t.nome, 'vertente': _cla})
        return out

    racial_choices_raca, racial_choices_linhagem, racial_choices_essencia = {}, {}, {}
    for r in TbRaca.objects.all():
        # RAÇA-BASE só: exclui picks de traços de linhagem/essência (id_raca herda do pai).
        p = _racial_picks(TbTracoracial.objects.filter(
            id_raca=r, id_linhagem__isnull=True, id_essencia__isnull=True,
            nivel_requisito__lte=1).exclude(talento_racial=True))
        if p:
            racial_choices_raca[r.slug] = p
    for l in TbLinhagem.objects.all():
        p = _racial_picks(TbTracoracial.objects.filter(id_linhagem=l, nivel_requisito__lte=1).exclude(talento_racial=True))
        if p:
            racial_choices_linhagem[l.slug] = p
    for e in TbEssencia.objects.all():
        p = _racial_picks(TbTracoracial.objects.filter(id_essencia=e, nivel_requisito__lte=1).exclude(talento_racial=True),
                          clas=clas_de_essencia(e))
        if p:
            racial_choices_essencia[e.slug] = p
    # Perícias auto-concedidas (prof:<skill> em traço não-talento) por raça/linhagem/essência.
    pericias_concedidas_raca, pericias_concedidas_linhagem, pericias_concedidas_essencia = {}, {}, {}
    for r in TbRaca.objects.all():
        # RAÇA-BASE só: exclui perícias de traços de linhagem/essência (id_raca herda do pai).
        g = _pericias_concedidas(TbTracoracial.objects.filter(
            id_raca=r, id_linhagem__isnull=True, id_essencia__isnull=True,
            nivel_requisito__lte=1).exclude(talento_racial=True))
        if g:
            pericias_concedidas_raca[r.slug] = g
    for l in TbLinhagem.objects.all():
        g = _pericias_concedidas(TbTracoracial.objects.filter(id_linhagem=l, nivel_requisito__lte=1).exclude(talento_racial=True))
        if g:
            pericias_concedidas_linhagem[l.slug] = g
    for e in TbEssencia.objects.all():
        g = _pericias_concedidas(TbTracoracial.objects.filter(id_essencia=e, nivel_requisito__lte=1).exclude(talento_racial=True),
                                 clas=clas_de_essencia(e))
        if g:
            pericias_concedidas_essencia[e.slug] = g
    pericias = sorted(({'slug': sl, 'nome': info[0]} for sl, info in _SKILL_INFO.items()),
                      key=lambda x: x['nome'])
    essencias_out = []
    for e in TbEssencia.objects.all().order_by('nome'):
        # sub-escolha da essência: vertente elemental OU clã/herança (Vampirismo). `vertentes`
        # mantém o nome da chave (o front já a consome); `subescolha_*` dá o rótulo dinâmico.
        sub = _essencia_subescolha(e, vertentes_catalogo)
        essencias_out.append({
            'slug': e.slug, 'nome': e.nome,
            'resumo': _criador_resumo_md(e.lore_presentation, 240),
            'tracos': _tracos_de(TbTracoracial.objects.filter(
                id_essencia=e, talento_racial=False, id_linhagem__isnull=True,
                nivel_requisito__lte=1).order_by('nome')),
            'vertentes': sub['opcoes'],
            'subescolha_label': sub['label'],
            'subescolha_tipo': sub['tipo']})
    from .character_engine import background_grants
    return {
        'racas': racas,
        'essencias': essencias_out,
        'vertentes': vertentes_catalogo,
        'classes': classes,
        'antecedentes': [{'slug': a.slug, 'nome': a.nome, 'grants': background_grants(a),
                          'resumo': _criador_resumo_md(a.resumo or a.descricao, 280)}
                         for a in TbAntecedente.objects.all().order_by('nome')],
        'grants_antecedente': background_grants(),
        'talentos_origem': [{'id': t.id_talento, 'nome': t.nome, 'pre': (t.pre_requisito or '').strip(),
                             'descricao': (t.descricao or '').strip()}
                            for t in TbTalento.objects.filter(tipo__iexact='origem').order_by('nome')],
        'talentos_raca': talentos_raca,
        'talentos_linhagem': talentos_linhagem,
        'talentos_essencia': talentos_essencia,
        'racial_choices_raca': racial_choices_raca,
        'racial_choices_linhagem': racial_choices_linhagem,
        'racial_choices_essencia': racial_choices_essencia,
        'pericias_concedidas_raca': pericias_concedidas_raca,
        'pericias_concedidas_linhagem': pericias_concedidas_linhagem,
        'pericias_concedidas_essencia': pericias_concedidas_essencia,
        'pericias': pericias,
        'idiomas': [{'nome': i.nome, 'desc': (i.categoria or '').strip()}
                    for i in TbIdioma.objects.exclude(nome__iexact='Comum').order_by('categoria', 'ordem', 'nome')],
        'ferramentas': [{'nome': f.nome, 'desc': _criador_resumo_md(f.descricao_markdown, 160),
                         'subcategoria': (f.subcategoria or '').strip()}
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


_TALENTO_ATTR_FIELDS = {
    'FOR': 'atrib_forca',
    'DES': 'atrib_destreza',
    'CON': 'atrib_constituicao',
    'INT': 'atrib_inteligencia',
    'SAB': 'atrib_sabedoria',
    'CAR': 'atrib_carisma',
}


def _asi_slots(personagem):
    slots = []
    classes = personagem.classes.select_related('id_classe').order_by('-principal', 'id')
    for pc in classes:
        for nivel in sorted(_tag_levels(pc.id_classe.tags_json, 'asi-choices')):
            if nivel <= int(pc.nivel or 0):
                slots.append({'classe': pc.id_classe, 'nivel': nivel,
                              'origem': 'ASI %s N%d' % (pc.id_classe.nome, nivel)})
    return slots


def _asi_aplicados(personagem):
    origens = {
        o for o in personagem.atributo_bonus
        .filter(origem_tipo__in=('asi-classe', 'classe-asi'))
        .values_list('origem', flat=True)
        if o
    }
    return len(origens) + personagem.talentos.filter(categoria='asi-nivel').count()


def _next_asi_slot(personagem):
    slots = _asi_slots(personagem)
    aplicados = _asi_aplicados(personagem)
    return slots[aplicados] if aplicados < len(slots) else None


def _talento_attr_options(talento):
    attrs = [sig for sig, field in _TALENTO_ATTR_FIELDS.items() if getattr(talento, field, False)]
    return attrs or list(_TALENTO_ATTR_FIELDS)


def _norm_req(texto):
    return unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().lower()


def _talento_linhagem_info(traco, linhagens_da_raca):
    """Linhagens ESPECÍFICAS da raça citadas no pré-requisito do talento (espelha
    _vertente_de, mas para sub-raças/TbLinhagem). Retorna (slugs, aceita_essencia):
    slugs=[] => vale para qualquer linhagem/base; aceita_essencia => o pré aceita
    'ou Essência'. Só varre o pré-requisito (não a descrição) para não restringir um
    talento por uma menção de linhagem em texto de flavor."""
    txt = _norm_req(traco.pre_requisito or '')
    hits = []
    for l in linhagens_da_raca:
        # nomes trazem parentético descritivo ("Orc Verde (Espírito da Caça)") que não
        # aparece no pré-requisito ("Orc Verde."): compara só o núcleo do nome.
        nome = re.sub(r'\(.*?\)', '', _norm_req(getattr(l, 'nome', '') or ''))
        nome = re.sub(r'\s+', ' ', nome).strip()
        if nome and re.search(r'\b%s\b' % re.escape(nome), txt) and l.slug not in hits:
            hits.append(l.slug)
    return hits, bool(re.search(r'\bessencia\b', txt))


_COUNT_AS_HEAD_RE = re.compile(r'^count_as:([a-z0-9_]+)\(')


def _count_as_racial_targets(traits, linhagem_slug=None):
    """Slugs de raça que estes traços fazem o personagem 'contar como' para efeito de
    talento_racial (tag `count_as:<raca>(for:prereq{...talento_racial...})`, ex.: a
    linhagem humana Sálarin → elfo). Respeita `except:linhagem:<slug>` (não aplica quando a
    linhagem ativa é essa) e ignora `count_as:pick:...` (escolha de raça — fora de escopo) e
    count_as sem `for:prereq{...talento_racial...}` (ex.: `for:detection`)."""
    out = set()
    for t in traits:
        for tag in (getattr(t, 'tags_json', None) or []):
            s = str(tag)
            m = _COUNT_AS_HEAD_RE.match(s)
            if not m or m.group(1) == 'pick':
                continue
            mf = re.search(r'for\s*:\s*prereq\{([^}]*)\}', s)
            if not mf or 'talento_racial' not in mf.group(1):
                continue
            mex = re.search(r'except:linhagem:([a-z0-9_-]+)', s)
            if mex and linhagem_slug and mex.group(1) == linhagem_slug:
                continue
            out.add(m.group(1))
    return out


def _talentos_raciais_count_as(raca_slugs, nivel_max=None):
    """Talentos raciais GERAIS (sem sub-raça/essência) das raças `raca_slugs` — o pool que
    uma linhagem `count_as:<raca>` herda (Sálarin humano pega os do Elfo etc.). 'Geral' =
    sem restrição de linhagem NA PRÓPRIA raça (`_talento_linhagem_info` vazio contra as
    linhagens daquela raça — exclui, ex., 'Passagem Umbral' que exige a linhagem Noctelar).
    Retorna [(traco, linhagens_da_outra_raca)] p/ o _traco_dict computar linhagens=[]."""
    from .models import TbRaca, TbTracoracial, TbLinhagem
    out = []
    for slug in raca_slugs:
        r = TbRaca.objects.filter(slug=slug).first()
        if not r:
            continue
        lins_r = list(TbLinhagem.objects.filter(id_raca=r))
        qs = TbTracoracial.objects.filter(id_raca=r, talento_racial=True,
                                          id_linhagem__isnull=True, id_essencia__isnull=True)
        if nivel_max is not None:
            qs = qs.filter(nivel_requisito__lte=nivel_max)
        for t in qs.order_by('nivel_requisito', 'nome'):
            lins, _ = _talento_linhagem_info(t, lins_r)
            if not lins:
                out.append((t, lins_r))
    return out


def _personagem_conjura(personagem):
    """Delega ao DETECTOR ÚNICO em character_engine._personagem_conjura (camada baixa) — a
    MESMA regra do PO que libera as listas de decreto, para nunca divergir. Cobre: classe
    base conjuradora, subclasse conjuradora DO PERSONAGEM (subclasse-aware — sem o
    falso-positivo do Ladino que via a Magia do Trapaceiro), magia de pacto (spellcasting
    {slots:pact} na base) e TbPersonagemMagia não-vazia (magia de qualquer origem)."""
    from .character_engine import _personagem_conjura as _ce_personagem_conjura
    return _ce_personagem_conjura(personagem)


def _talento_prereq_ok(talento, personagem, ficha):
    req = _norm_req(talento.pre_requisito)
    if not req:
        return True
    nivel_total = int(ficha.get('nivel_total') or personagem.nivel or 1)
    m = re.search(r'nivel\s*(\d+)\s*\+', req)
    if m and nivel_total < int(m.group(1)):
        return False
    attrs = ficha.get('atributos') or {}
    req_attrs = {
        'forca': 'FOR', 'destreza': 'DES', 'constituicao': 'CON',
        'inteligencia': 'INT', 'sabedoria': 'SAB', 'carisma': 'CAR',
    }
    for nome, sig in req_attrs.items():
        m = re.search(r'%s\s*(\d+)\s*\+' % nome, req)
        if m and int((attrs.get(sig) or {}).get('valor') or 0) < int(m.group(1)):
            return False
    if ('conjuracao' in req or 'magia de pacto' in req) and not _personagem_conjura(personagem):
        return False
    if 'arma marcial' in req and not any('Marcial' in p for p in ficha.get('proficiencias_arma', [])):
        return False
    if 'talento ' in req:
        owned = {_norm_req(t.nome) for t in personagem.talentos.all()}
        trecho = req.split('talento ', 1)[1]
        if not owned or not any(nome and nome in trecho for nome in owned):
            return False
    # ── MARCAS: cláusulas que o avaliador genérico ignorava (exclusão mútua + Marca-base
    # nomeada nas Superiores) — não citam a palavra 'talento', então escapavam do branch acima.
    if 'marca' in req:
        owned_marcas = {_norm_req(t.nome) for t in personagem.talentos.all()}
        if 'nao possuir outra' in req:
            # (a) EXCLUSÃO MÚTUA — "não possuir outra Marca Arcana [ou Marca Anômala]": falha
            # se já tem QUALQUER talento da(s) família(s) citada(s) (Arcana vs Anômala,
            # precisamente conforme o texto — a base Anômala só exclui Arcana).
            depois = req.split('nao possuir outra', 1)[1]
            familias = [f for f in ('marca arcana', 'marca anomala') if f in depois]
            if any(fam in nome for fam in familias for nome in owned_marcas):
                return False
        elif 'qualquer' not in req:
            # (b) MARCA-BASE NOMEADA — as Superiores/Maior citam o nome EXATO de um TbTalento
            # de Marca ("Marca Arcana da Busca."): exige possuí-lo. Cláusulas de CATEGORIA
            # ("qualquer Marca Superior…", Marca Potente) ficam permissivas.
            from .models import TbTalento
            nomes_marca = [_norm_req(t.nome) for t in TbTalento.objects.filter(nome__icontains='marca')]
            exigidos = [n for n in nomes_marca if n and n in req]
            if exigidos and not any(n in owned_marcas for n in exigidos):
                return False
    return True


def _talentos_asi_disponiveis(personagem, ficha):
    from .models import TbTalento
    owned_ids = set(personagem.talentos.exclude(id_talento__isnull=True).values_list('id_talento_id', flat=True))
    out = []
    for t in TbTalento.objects.filter(tipo__iexact='geral').order_by('nome'):
        if t.id_talento in owned_ids or not _talento_prereq_ok(t, personagem, ficha):
            continue
        attrs = _talento_attr_options(t)
        out.append({
            'id': t.id_talento,
            'nome': t.nome,
            'pre': (t.pre_requisito or '').strip(),
            'descricao': (t.descricao or '').strip(),
            'attrs': attrs,
            'attrs_csv': ','.join(attrs),
        })
    return out


def _personagem_classe_contexto(personagem, classe_id=None):
    """Resolve a classe alvo; endpoints legados continuam caindo na principal."""
    if classe_id:
        pc = personagem.classes.filter(id_classe_id=classe_id).first()
        if pc:
            return pc
    return personagem.classes.filter(principal=True).first() or personagem.classes.first()


def _pendencias_nivel(personagem, classe_id=None):
    """Escolhas que faltam no nível atual: subclasse (N>=nível-da-subclasse) e ASIs."""
    from .models import TbSubclasse
    pend = {'subclasse': False, 'asi_pendentes': 0, 'subclasse_nivel': None, 'subclasses': []}
    pc = _personagem_classe_contexto(personagem, classe_id)
    if not pc:
        return pend
    nivel = pc.nivel or 1
    classe = pc.id_classe
    from .character_engine import _subclass_min_level
    pend['subclasse_nivel'] = _subclass_min_level(classe)
    if pend['subclasse_nivel'] and nivel >= pend['subclasse_nivel'] and not pc.id_subclasse_id:
        pend['subclasse'] = True
        pend['subclasses'] = [{'id': s.id_subclasse, 'nome': s.nome,
                               'descricao': (s.tagline or '').strip()}
                              for s in TbSubclasse.objects.filter(id_classe=classe).order_by('nome')]
    pend['asi_pendentes'] = max(0, len(_asi_slots(personagem)) - _asi_aplicados(personagem))
    return pend




def _pendencias_talento_racial(personagem):
    """Talentos raciais a escolher por nivel_requisito dos tracos raciais marcados
    como talento_racial, vindos de raca, linhagem ou essencia, menos os ja escolhidos."""
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
    # Filtro de linhagem (mesmo critério do criador): talento da RAÇA base restrito a
    # sub-raças que o personagem não tem some da lista; quem tem só Essência não vê os
    # exclusivos de linhagem, mas continua vendo os que aceitam 'ou Essência'.
    from .models import TbLinhagem
    lins_raca = list(TbLinhagem.objects.filter(id_raca=personagem.id_raca_id)) if personagem.id_raca_id else []
    lin_sel_slug = getattr(getattr(personagem, 'id_linhagem', None), 'slug', None)
    tem_essencia = bool(getattr(personagem, 'id_essencia_id', None))

    def _linhagem_ok(o):
        if getattr(o, 'id_linhagem_id', None) or getattr(o, 'id_essencia_id', None):
            return True  # já é específico de linhagem/essência: cond já filtrou certo
        lins, aceita_ess = _talento_linhagem_info(o, lins_raca)
        if not lins:
            return True  # sem restrição de linhagem
        if lin_sel_slug and lin_sel_slug in lins:
            return True
        return bool(aceita_ess and tem_essencia)
    # Clã/herança de essência (Vampirismo): um talento racial de clã (Segredos Rubedo,
    # Evolução Sybaris…) só entra no pool do clã ESCOLHIDO — senão o vampiro veria os
    # Segredos dos cinco clãs de uma vez. Talentos compartilhados (Brumas de Velmourn,
    # Espreitador Noturno…) valem para qualquer clã.
    from .character_engine import clas_de_essencia, cla_de_traco, cla_escolhido
    _clas = clas_de_essencia(personagem.id_essencia) if getattr(personagem, 'id_essencia_id', None) else []
    _cla_sel = cla_escolhido(personagem) if _clas else ''

    def _cla_ok(o):
        if not _clas or getattr(o, 'id_essencia_id', None) != personagem.id_essencia_id:
            return True  # traço não é da essência com clã: não filtra
        c = cla_de_traco(o, _clas)
        return not c or c == _cla_sel
    # count_as: raças que o personagem conta-como p/ talento_racial (Sálarin→elfo etc.),
    # herdando os talentos raciais GERAIS delas — no criador e AQUI (level-up). Os marcos
    # (tiers) passam a incluir os das raças emprestadas; as opções emprestadas já vêm
    # filtradas como gerais, então dispensam _linhagem_ok.
    from .character_engine import _tracos_raciais
    ca_targets = _count_as_racial_targets(
        [obj for (_o, _f, obj, _cl) in _tracos_raciais(personagem)], linhagem_slug=lin_sel_slug)
    borrowed = _talentos_raciais_count_as(ca_targets)
    borrowed_pks = {t.pk for (t, _l) in borrowed}
    out = []
    tiers = sorted({
        n for n in (list(TbTracoracial.objects.filter(cond, talento_racial=True)
                         .values_list('nivel_requisito', flat=True))
                    + [t.nivel_requisito for (t, _l) in borrowed])
        if n
    })
    for tier in tiers:
        if tier > total or tier in picked_tiers:
            continue
        # nivel_requisito__lte=tier: o slot deste marco oferece os talentos deste tier
        # E os de tiers anteriores ainda não escolhidos (ex.: no nível 5 aparecem os de
        # nível 1 não pegos na criação + os de nível 5). picked_nomes evita repetir.
        combinado = list(TbTracoracial.objects.filter(cond, talento_racial=True,
                                                      nivel_requisito__lte=tier))
        combinado += [t for (t, _l) in borrowed if t.nivel_requisito and t.nivel_requisito <= tier]
        seen = set(picked_nomes)
        opcoes = []
        for o in sorted(combinado, key=lambda x: x.nome):
            if o.nome in seen:
                continue
            if o.pk not in borrowed_pks and not _linhagem_ok(o):
                continue
            if not _cla_ok(o):
                continue
            seen.add(o.nome)
            opcoes.append(o)
        if opcoes:
            out.append({'nivel': tier, 'opcoes': [
                {'nome': o.nome, 'descricao': (o.descricao or '').strip(),
                 'pre': (o.pre_requisito or '').strip()} for o in opcoes]})
    return out


# pick:opcao:<slug>(<mod>):<count>  — count = {progressão} | inteiro | N | +
_PICK_OPCAO_RE = re.compile(r'pick:opcao:([a-z0-9_-]+)(?:\([^)]*\))?(?::(\{[^}]*\}|[+-]?\d+|N|\+))?')


def _pick_count_expr(expr, level):
    """Conta de um pick:opcao. Literal '2'→2; progressão '{classlvl=X:n,...}'→SOMA
    cumulativa dos n com limiar<=level (semântica de 'conhecidas'). 'N'/'+'/vazio→None
    (a conta vem de um recurso de tabela)."""
    expr = (expr or '').strip()
    if expr.startswith('{'):
        return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*([+-]?\d+)', expr)
                   if int(lv) <= level)
    if re.match(r'^[+-]?\d+$', expr):
        return int(expr)
    return None


# Painel genérico de Escolhas (level-up/editar): mostra TODOS os grupos `pick:*`
# resolvíveis — opções (metamagia/estilos/…), perícias, menus inline `define{list}`
# (Máscara de Guerra, Runas, Doutrina Marcial…) e sub-escolhas de essência
# (sangue/energia/polo/elemento). `kinds=None` = todos; o resolvedor só emite grupo
# para kind com universo (registrado ou menu), então nada espúrio entra. Excluímos só
# `arma` (tem painel dedicado de Maestria). Adicionar capacidade nova não exige mexer aqui.
_OPCAO_PANEL_KINDS = None
_OPCAO_PANEL_EXCLUDE = {'arma'}


def _opcao_grupos(personagem, classe_id=None):
    """Grupos de escolha de classe de nível alto exibidos no editar-ficha: opções
    (metamagia, manobras, segredos, estilos…) E perícias (`pick:pericia`, ex.: Bárbaro
    Conhecimento Primitivo). FONTE ÚNICA: o resolvedor genérico (`home.picks`) descobre
    os grupos pelas tags; aqui só reformatamos os PickGroup no shape do template, sem
    ramificar por tipo — o submit token de cada opção é `val` (id da opção OU slug)."""
    from . import picks as _picks
    grupos = []
    if personagem is None:
        return grupos
    slug2tipo = _picks._slug2tipo_map()
    for g in _picks.resolve_personagem(personagem, kinds=_OPCAO_PANEL_KINDS):
        if g['kind'] in _OPCAO_PANEL_EXCLUDE:
            continue
        if classe_id and str(g['classe_id']) != str(classe_id):
            continue
        slug = g['persist_tipo']
        tipo_disp = (g.get('tipo_display') or slug2tipo.get(slug)
                     or slug2tipo.get(_picks.normalize_slug(slug)) or slug)
        escs = g['escolhidas']
        esc_ids = {e.get('id_opcao') for e in escs if e.get('id_opcao')}
        esc_slugs = {e.get('valor') for e in escs if e.get('valor')}
        disponiveis = [{'id': o['id'], 'slug': o['slug'],
                        'val': str(o['id']) if o.get('id') is not None else o['slug'],
                        'nome': o['nome'], 'descricao': o.get('descricao') or '',
                        'pre': o.get('pre') or ''}
                       for o in g['universo']
                       if o['id'] not in esc_ids and o['slug'] not in esc_slugs]
        grupos.append({
            'classe_id': g['classe_id'], 'classe': g['classe'], 'slug': slug, 'kind': g['kind'],
            'tipo': tipo_disp, 'limite': g['n'], 'usados': g['usados'],
            'pendentes': g['pendentes'], 'prox_slot': g['prox_slot'],
            'escolhidas': [{'id': e['id'], 'nome': e['nome']} for e in escs],
            'disponiveis': disponiveis,
        })
    grupos.sort(key=lambda g: (g['pendentes'] == 0, g['classe'], g['tipo']))
    return grupos


@login_required(login_url='/login/')
def editar_ficha_view(request, pk):
    """Edição de uma ficha: inventário, mercado, informações e manutenção de magias. O
    LEVEL-UP (subir de nível + escolhas de progressão) vive numa experiência dedicada
    (personagem_subir_nivel); aqui fica só o botão de acesso a ela."""
    from .character_engine import derive
    from . import permissions as perms_mod
    p = _ficha_editavel(request, pk)
    pc = p.classes.filter(principal=True).first() or p.classes.first()
    ficha = derive(p)
    # Level-up saiu daqui: vive numa página dedicada (personagem_subir_nivel GET). Aqui só
    # o STATUS (fonte do botão) e a manutenção de magias (trocar/preparar) permanecem.
    pendm = _pendencias_magias(p)
    levelup_status = _levelup_status(p, ficha)
    from .models import TbTalento, TbItemMundano
    # ── Mercado no formato CATÁLOGO (busca + chips + cards nome/preço) ──
    # Listas planas com metadados por item para busca/filtro no cliente; só itens
    # comercializáveis (preço parseável no mundano; preco>0 no mágico — guard já existe
    # no backend, recompensa de missão/preço 0 fica de fora).
    from .models import TbItemMagico
    cat_label = dict(TbItemMundano.CATEGORIA_CHOICES)
    loja_mundano, _cats_seen = [], []
    for it in TbItemMundano.objects.order_by('nome'):
        if _preco_em_pc(it.preco) is None:
            continue
        if it.categoria not in _cats_seen:
            _cats_seen.append(it.categoria)
        loja_mundano.append({
            'slug': it.slug, 'nome': it.nome, 'preco': it.preco,
            'cat': it.categoria, 'cat_label': cat_label.get(it.categoria, it.categoria),
            'meta': it.subcategoria or cat_label.get(it.categoria, it.categoria)})
    loja_mundano_cats = [{'id': c, 'label': cat_label.get(c, c)}
                         for c in sorted(_cats_seen, key=lambda c: cat_label.get(c, c))]

    rar_label = dict(TbItemMagico.RARIDADE_CHOICES)
    slot_label = dict(TbItemMagico.SLOT_CHOICES)
    _base_order = ['comum', 'incomum', 'raro', 'muito_raro', 'lendario', 'artefato']

    def _rar_key(r):
        base = re.sub(r'_(menor|maior)$', '', r or '')
        return (_base_order.index(base) if base in _base_order else 99,
                1 if (r or '').endswith('_maior') else 0, r or '')
    loja_magico, _rars_seen, _lojas_seen = [], [], []
    for it in TbItemMagico.objects.filter(preco__gt=0).order_by('raridade', 'nome'):
        base_rar = re.sub(r'_(menor|maior)$', '', it.raridade or '')
        if it.raridade not in _rars_seen:
            _rars_seen.append(it.raridade)
        loja_nome = (it.loja or '').strip()
        if loja_nome and loja_nome not in _lojas_seen:
            _lojas_seen.append(loja_nome)
        loja_magico.append({
            'slug': it.slug, 'nome': it.nome, 'preco': '%g PO' % float(it.preco),
            'raridade': it.raridade, 'raridade_label': rar_label.get(it.raridade, it.raridade),
            'base_rarity': base_rar, 'tipo': it.tipo or slot_label.get(it.slot, it.slot),
            'loja': loja_nome, 'requer_sintonizacao': it.requer_sintonizacao})
    loja_magico_rars = [{'value': r, 'label': rar_label.get(r, r), 'base': re.sub(r'_(menor|maior)$', '', r or '')}
                        for r in sorted(_rars_seen, key=_rar_key)]
    loja_magico_lojas = sorted(_lojas_seen)
    sintonizados_usados = p.inventario.filter(sintonizado=True).count()
    from .character_engine import _recursos_consumiveis, derive
    recursos_consumiveis = _recursos_consumiveis(p, list(p.classes.select_related('id_classe', 'id_subclasse')))
    magias_preparadas = _magias_preparadas_info(p, ficha)
    # preço de venda (80%) dos itens mundanos com custo parseável
    for it in ficha.get('inventario', []):
        if not it.get('magico'):
            v = _preco_venda_mundano_pc(it.get('custo'))
            if v:
                it['venda_pc'], it['venda_display'] = v, _pc_display(v)
    transacoes = list(p.transacoes.all()[:30])
    classes_atuais = [{'id': c.id_classe.id_classe, 'nome': c.id_classe.nome, 'nivel': c.nivel,
                       'principal': c.principal} for c in p.classes.select_related('id_classe').order_by('-principal', 'id')]
    aventura_ledger = list(p.aventuras_ledger.select_related('criado_por', 'revertido_por')[:30])
    # ── Painel STAFF de CONCESSÃO de item (missão/recompensa sem preço) ──
    # Catálogo COMPLETO (sem o filtro de preço da loja) só é montado para a staff, com
    # um flag `sem_preco` por item para sinalizar recompensa de missão. A trilha das
    # concessões já feitas (linhas de inventário com concedido_em) sai numa mini-lista.
    is_staff = perms_mod.is_staff_user(request.user)
    conceder_magico = conceder_mundano = concessoes = None
    if is_staff:
        conceder_magico = [
            {'slug': it.slug, 'nome': it.nome,
             'meta': rar_label.get(it.raridade, it.raridade),
             'sem_preco': not (it.preco and float(it.preco) > 0)}
            for it in TbItemMagico.objects.order_by('nome')]
        conceder_mundano = [
            {'slug': it.slug, 'nome': it.nome,
             'meta': cat_label.get(it.categoria, it.categoria),
             'sem_preco': _preco_em_pc(it.preco) is None}
            for it in TbItemMundano.objects.order_by('nome')]
        concessoes = list(p.inventario.filter(concedido_em__isnull=False)
                          .select_related('concedido_por', 'id_item_magico')
                          .order_by('-concedido_em', '-id')[:40])
    return render(request, 'home/pages/editar_ficha.html', {
        'page_title': 'Editar — %s' % p.nome,
        'p': p, 'pc': pc, 'ficha': ficha,
        'nivel': pc.nivel if pc else 1,
        'pend_magias': pendm,
        'levelup_status': levelup_status,
        'carteira_display': _pc_display(p.carteira_pc),
        'loja_mundano': loja_mundano,
        'loja_mundano_cats': loja_mundano_cats,
        'loja_magico': loja_magico,
        'loja_magico_rars': loja_magico_rars,
        'loja_magico_lojas': loja_magico_lojas,
        'sintonizados_usados': sintonizados_usados,
        'recursos_consumiveis': recursos_consumiveis,
        'magias_preparadas': magias_preparadas,
        'transacoes': transacoes,
        'is_staff': is_staff,
        'classes_atuais': classes_atuais,
        'compra_msg': request.GET.get('compra'),
        'aventura_ledger': aventura_ledger,
        'rollback_msg': request.GET.get('rollback'),
        'conceder_magico': conceder_magico,
        'conceder_mundano': conceder_mundano,
        'concessoes': concessoes,
        'concessao_msg': request.GET.get('concessao'),
    })


@login_required(login_url='/login/')
def personagem_subir_nivel(request, pk):
    """Rota `subir-nivel/` com duas caras (mesmo gate dono/staff via `_ficha_editavel`):

      • GET  → EXPERIÊNCIA DEDICADA de level-up (BG3-like): página imersiva passo-a-passo
        com os ganhos do nível-alvo, os passos de escolha em sequência, prévia ao vivo e
        um único "Confirmar" que aplica o LOTE. Toda a mecânica reusa os endpoints em lote
        `personagem_levelup_preview`/`personagem_levelup_aplicar`.
      • POST → wrapper PRG LEGADO (1 passo): sobe 1 nível da classe. Mantido por
        compatibilidade (redireciona pra ficha)."""
    p = _ficha_editavel(request, pk)
    if request.method == 'POST':
        erros = _lvl_aplicar_subir_nivel(p, {'classe': request.POST.get('classe')})
        if not erros:
            # Novos níveis podem desbloquear ciclos de Magia Elemental (nv 5/9/13).
            _sync_magias_essencia(p)
            _refresh_vitais_derivados(p)
        return redirect('ficha_detail', pk=pk)
    return _subir_nivel_experiencia(request, p)


def _subir_nivel_experiencia(request, p):
    """Monta a página dedicada. As pendências/ganhos são derivadas do NÍVEL-ALVO: quando
    o personagem é elegível, roda `subir_nivel` numa transação REVERTIDA e coleta subclasse/
    ASI/magias/opções JÁ no nível conquistado (semântica BG3 — escolhe no novo nível). Sem
    elegibilidade, exibe apenas as pendências ainda abertas do nível atual."""
    from .character_engine import derive
    ficha_atual = derive(p)
    status = _levelup_status(p, ficha_atual)
    classes_atuais = [{'id': c.id_classe.id_classe, 'nome': c.id_classe.nome, 'nivel': c.nivel,
                       'principal': c.principal}
                      for c in p.classes.select_related('id_classe').order_by('-principal', 'id')]
    sel_id = request.GET.get('classe')
    pc = (p.classes.filter(id_classe_id=sel_id).first() if sel_id else None) \
        or p.classes.filter(principal=True).first() or p.classes.first()
    classe_id = pc.id_classe_id if pc else None
    con_mod = ((ficha_atual.get('atributos') or {}).get('CON') or {}).get('mod', 0) or 0
    nivel_atual_total = int(ficha_atual.get('nivel_total') or 0)
    pode_subir = status['pode_subir']
    classes_multiclasse = _classes_multiclasse(p, ficha_atual) if nivel_atual_total < 20 else []
    # recursos ANTES (p/ marcar o que cresce no nível-alvo)
    from .character_engine import _recursos_consumiveis
    rec_antes = {r['slug']: r for r in _recursos_consumiveis(
        p, list(p.classes.select_related('id_classe', 'id_subclasse')))}

    ganhos = recursos_delta = None
    with transaction.atomic():
        if pode_subir:
            _lvl_aplicar_subir_nivel(p, {'classe': classe_id})
            _sync_magias_concedidas(p)
        ficha_alvo = derive(p)
        pend = _pendencias_nivel(p, classe_id)
        # ciente da subclasse que será escolhida NESTE passo (third-casters: a conjuração
        # vem da subclasse, ainda não atribuída no nível em que ela é adquirida).
        pendm = _pendencias_magias_levelup(p, pend, classe_id)
        talentos_raciais_pend = _pendencias_talento_racial(p)
        opcao_grupos = _opcao_grupos(p, classe_id)
        talentos = _talentos_asi_disponiveis(p, ficha_alvo)
        # nível-alvo da classe: re-lê do banco DENTRO da transação (o `pc` de fora é o nível
        # atual; `_lvl_aplicar_subir_nivel` gravou o novo nível numa instância própria).
        pc_alvo = (p.classes.filter(id_classe_id=classe_id).first() if classe_id else None) \
            or p.classes.filter(principal=True).first() or p.classes.first()
        nivel_classe_alvo = int(pc_alvo.nivel or 1) if pc_alvo else 1
        ganhos = _levelup_ganhos(p, classe_id, nivel_classe_alvo, con_mod)
        # PV real do salto = derive(alvo) - derive(atual): inclui bônus de PV por nível de
        # talento/traço (Robusto, Sangue Elemental…), não só a média do dado da classe.
        if pode_subir:
            cur_pv = (ficha_atual.get('pv') or {}).get('maximo_calculado')
            tgt_pv = (ficha_alvo.get('pv') or {}).get('maximo_calculado')
            if cur_pv is not None and tgt_pv is not None:
                ganhos['pv_ganho'] = max(0, int(tgt_pv) - int(cur_pv))
        else:
            ganhos['pv_ganho'] = None
        recursos_delta = _levelup_recursos_delta(rec_antes, _recursos_consumiveis(
            p, list(p.classes.select_related('id_classe', 'id_subclasse'))))
        nivel_alvo_total = int(ficha_alvo.get('nivel_total') or nivel_atual_total)
        preview_resumo = _criador_preview_resumo(ficha_alvo)
        transaction.set_rollback(True)

    sem_pendencias = not (pend['subclasse'] or pend['asi_pendentes']
                          or (pendm and (pendm['cantrips_pend'] or pendm['known_pend']))
                          or talentos_raciais_pend
                          or any(g['pendentes'] for g in opcao_grupos))
    from . import point_buy
    return render(request, 'home/pages/subir_nivel.html', {
        'page_title': 'Subir de Nível — %s' % p.nome,
        'p': p, 'pc': pc, 'ficha': ficha_atual, 'preview_resumo': preview_resumo,
        'status': status, 'pode_subir': pode_subir,
        'nivel_atual': nivel_atual_total, 'nivel_alvo': nivel_alvo_total,
        'classe_id': classe_id, 'classes_atuais': classes_atuais,
        'classes_multiclasse': classes_multiclasse,
        'ganhos': ganhos, 'recursos_delta': recursos_delta,
        'pend': pend, 'pend_magias': pendm,
        'talentos_raciais_pend': talentos_raciais_pend,
        'opcao_grupos': opcao_grupos, 'talentos_normais': talentos,
        'atributos': point_buy.SIGLAS, 'sem_pendencias': sem_pendencias,
    })


def _refresh_vitais_derivados(personagem, refill=False):
    """Persiste campos vitais que continuam sendo derivados pelas tags do engine."""
    from .character_engine import derive
    antigo_max = int(personagem.pv_maximo or 0)
    antigo_atual = int(personagem.pv_atual or 0)
    ficha = derive(personagem)
    pv = ficha.get('pv') or {}
    novo_max = int(pv.get('maximo_calculado') or antigo_max or 0)
    personagem.pv_maximo = novo_max
    if refill or antigo_max <= 0:
        personagem.pv_atual = novo_max
    elif novo_max > antigo_max:
        personagem.pv_atual = min(novo_max, antigo_atual + (novo_max - antigo_max))
    elif novo_max > 0:
        personagem.pv_atual = min(antigo_atual, novo_max)
    personagem.ca = int(ficha.get('ca') or personagem.ca or 10)
    # NÃO persistir velocidade: personagem.velocidade é a BASE imutável (semente de
    # criação). O derive semeia dela e soma os bônus de tags sempre-ativas a cada vez;
    # gravar a velocidade DERIVADA de volta aqui realimentava o cálculo e inflava a
    # base a cada refresh (30 -> 50 -> 70 ... ft). CA e PV são recomputados do zero,
    # por isso não inflam; a velocidade agora segue a mesma regra.
    personagem.save(update_fields=['pv_maximo', 'pv_atual', 'ca', 'atualizado_em'])
    return ficha


def aplicar_aventuras(personagem, n, evento=False, nome_aventura=None, criado_por=None,
                      registrar_ledger=True):
    """Aplica `n` aventuras a um personagem (lançado por staff). Regra de SPLIT no rank-up:
    cada aventura é recompensada no rank ANTES de ela contar (a que sobe de rank paga no
    rank antigo; as seguintes no novo). Sempre credita o ouro do rank (PO→PC). BRASEIROS
    (= BP) só em missão de EVENTO (`evento=True`) — jogar evento dá braseiros; aventura
    normal, não.

    Quando `registrar_ledger`, grava UMA linha em TbPersonagemAventura (ledger de
    lançamentos) na MESMA transação do crédito — dá NOME ao lançamento e habilita o
    rollback (`personagem_reverter_aventura`). NÃO muda a matemática de ouro/nível; só
    registra o que foi pago. Retorna (ouro_po, braseiros)."""
    from .character_engine import nivel_por_aventuras, ouro_de_progressao, braseiros_por_aventura
    from .models import TbPersonagemAventura
    n = max(0, int(n))
    if n == 0:
        return (0, 0)
    base = int(personagem.aventuras or 0)
    # Ouro do intervalo = diferença do acumulado (regra sequencial de rank-up embutida).
    ouro = ouro_de_progressao(base + n) - ouro_de_progressao(base)
    bras = 0
    if evento:
        for k in range(n):
            bras += braseiros_por_aventura(nivel_por_aventuras(base + k))
    nome = (nome_aventura or '').strip() or 'Aventura'
    with transaction.atomic():
        personagem.aventuras = base + n
        personagem.braseiros = int(personagem.braseiros or 0) + bras
        personagem.carteira_pc = int(personagem.carteira_pc or 0) + ouro * 100
        personagem.save(update_fields=['aventuras', 'braseiros', 'carteira_pc', 'atualizado_em'])
        desc = '%d aventura(s)%s' % (n, (' de evento — +%d braseiros' % bras) if evento else '')
        _registrar_transacao(personagem, 'aventura', desc, ouro * 100)
        if registrar_ledger:
            TbPersonagemAventura.objects.create(
                id_personagem=personagem, nome_aventura=nome[:200], qtd_aventuras=n,
                ouro_pago_pc=ouro * 100, braseiros_pago=bras,
                nivel_no_lancamento=int(personagem.nivel or 1), criado_por=criado_por)
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
    # Concessões FIXAS não-mágicas (grant:opcao / grant:talento) sincronizam no MESMO ponto
    # (toda persistência que reavalia magias reavalia grants); mantém a ficha consistente
    # sem espalhar chamadas por todos os fluxos de save.
    _sync_grants_fixos(personagem)
    return len(info['pendentes'])


def _sync_grants_fixos(personagem):
    """Materializa as concessões FIXAS reportadas por `character_engine.grants_fixos`
    (grant:opcao / grant:talento), no padrão idempotente e origem-rastreado de
    `_sync_magias_concedidas`:
      • Opções → TbPersonagemEscolha(tipo='grant-opcao', id_opcao) — lidas por
        `_features_de_opcoes` (efeitos passivos + aparecem em state['features']) SEM contar no
        limite de pick (o painel de opções filtra por tipo≠'grant-opcao').
      • Talentos → TbPersonagemTalento(categoria='concedido') — lidos por `_talentos`
        (proficiências/perícias/tags do talento). SEM ASI: o grant NÃO passa pelo fluxo de
        level-up, então nenhum TbPersonagemAtributoBonus é criado (as opções em escopo não
        carregam `attr:` nas tags).
    Gerência restrita aos registros que ELE cria (tipo='grant-opcao' / categoria='concedido'):
    reconstrói-os a cada sync (conjunto pequeno) preservando escolhas de pick e talentos de ASI.
    Retorna (n_opcoes, n_talentos)."""
    from .models import TbPersonagemEscolha, TbPersonagemTalento, TbOpcaojogo, TbTalento
    from .character_engine import grants_fixos
    info = grants_fixos(personagem)
    # ── opções concedidas ──
    TbPersonagemEscolha.objects.filter(id_personagem=personagem, tipo='grant-opcao').delete()
    por_fonte = {}
    for c in info['opcoes']:
        por_fonte.setdefault((c['fonte'] or '')[:150], []).append(c)
    for fonte, itens in por_fonte.items():
        for slot, c in enumerate(itens):
            op = TbOpcaojogo.objects.filter(id_opcao=c['id_opcao']).first()
            if op:
                TbPersonagemEscolha.objects.create(
                    id_personagem=personagem, origem=fonte, tipo='grant-opcao',
                    slot=slot, id_opcao=op, valor=op.slug)
    # ── talentos concedidos (só os 'concedido'; preserva os de ASI/origem) ──
    TbPersonagemTalento.objects.filter(id_personagem=personagem, categoria='concedido').delete()
    for c in info['talentos']:
        t = TbTalento.objects.filter(id_talento=c['id_talento']).first()
        if t:
            TbPersonagemTalento.objects.create(
                id_personagem=personagem, id_talento=t, nome=t.nome,
                categoria='concedido', detalhes=('grant:%s' % (c['fonte'] or ''))[:200])
    return len(info['opcoes']), len(info['talentos'])


# compat: nome antigo
_sync_magias_essencia = _sync_magias_concedidas


def _aventuras_staff_resposta(request, p, *, compra_msg='', rollback_msg='', ok=True):
    """Fragmento atualizado do ledger para fetch, preservando redirect no POST clássico."""
    back = reverse('editar_ficha', args=[p.pk])
    if not is_ajax(request):
        query = ('?compra=' + compra_msg) if compra_msg else ('?rollback=' + rollback_msg)
        return redirect(back + query)

    from django.template.loader import render_to_string
    from .character_engine import derive

    p.refresh_from_db()
    ficha = derive(p)
    ledger = list(p.aventuras_ledger.select_related(
        'criado_por', 'revertido_por')[:30])
    html = render_to_string(
        'home/partials/_ficha_aventuras_staff.html',
        {
            'p': p,
            'aventura_ledger': ledger,
            'compra_msg': compra_msg,
            'rollback_msg': rollback_msg,
        },
        request=request,
    )
    prog = ficha.get('progressao') or {}
    return JsonResponse({
        'ok': ok,
        'msg': compra_msg or rollback_msg,
        'staffbox_html': html,
        'progressao': {
            'aventuras': int(prog.get('aventuras') or 0),
            'nivel_label': prog.get('nivel_label') or p.nivel,
            'braseiros': int(prog.get('braseiros') or 0),
        },
        'carteira_display': _pc_display(p.carteira_pc or 0),
    }, status=200 if ok else 400)


def _inventario_ajax_payload(request, p, *, msg='ok', ok=True):
    """Estado mínimo para mutações da edição sem recarregar a página."""
    from django.template.loader import render_to_string
    from .character_engine import derive

    p.refresh_from_db()
    ficha = derive(p)
    for item in ficha.get('inventario', []):
        if not item.get('magico'):
            venda = _preco_venda_mundano_pc(item.get('custo'))
            if venda:
                item['venda_pc'], item['venda_display'] = venda, _pc_display(venda)
    return {
        'ok': ok,
        'msg': msg,
        'carteira_display': _pc_display(p.carteira_pc or 0),
        'carteira_pc': int(p.carteira_pc or 0),
        'sintonizados_usados': p.inventario.filter(sintonizado=True).count(),
        'inventario_html': render_to_string(
            'home/partials/_ficha_inventario.html',
            {'ficha': ficha, 'p': p},
            request=request,
        ),
        'ficha': {
            'ca': ficha.get('ca'),
            'pv_maximo': (ficha.get('pv') or {}).get('maximo_calculado'),
        },
    }


def _inventario_mutacao_resposta(request, p, fallback, *, msg='ok', ok=True):
    if is_ajax(request):
        return JsonResponse(_inventario_ajax_payload(request, p, msg=msg, ok=ok),
                            status=200 if ok else 400)
    return redirect(fallback)


def _concessao_resposta(request, p, msg, *, ok=True):
    """Atualiza inventário e ledger da staff; POST clássico preserva o PRG."""
    back = reverse('editar_ficha', args=[p.pk])
    if not is_ajax(request):
        return redirect(back + '?concessao=' + msg)

    from django.template.loader import render_to_string

    payload = _inventario_ajax_payload(request, p, msg=msg, ok=ok)
    payload['concessoes_html'] = render_to_string(
        'home/partials/_ficha_concessoes_staff.html',
        {
            'p': p,
            'concessao_msg': msg,
            'concessoes': list(
                p.inventario.filter(concedido_em__isnull=False)
                .select_related('concedido_por', 'id_item_magico')
                .order_by('-concedido_em', '-id')[:40]
            ),
        },
        request=request,
    )
    return JsonResponse(payload, status=200 if ok else 400)


@login_required(login_url='/login/')
@require_POST
def personagem_registrar_aventuras(request, pk):
    """Staff lança N aventuras num personagem → ouro (por rank) + nível-teto, e braseiros
    (BP) se for missão de EVENTO. Exige NOME da aventura e grava a linha do ledger
    (TbPersonagemAventura) na mesma transação — para dar nome ao lançamento e permitir
    rollback."""
    from . import permissions as perms
    if not perms.is_staff_user(request.user):
        raise Http404
    p = _ficha_editavel(request, pk)
    nome = (request.POST.get('nome_aventura') or '').strip()
    if not nome:
        return _aventuras_staff_resposta(
            request, p, compra_msg='aventuras_sem_nome', ok=False)
    try:
        n = max(1, min(200, int(request.POST.get('aventuras') or 1)))
    except (TypeError, ValueError):
        n = 1
    aplicar_aventuras(p, n, evento=(request.POST.get('evento') == 'on'),
                      nome_aventura=nome, criado_por=request.user)
    return _aventuras_staff_resposta(request, p, compra_msg='aventuras')


@login_required(login_url='/login/')
@require_POST
def personagem_reverter_aventura(request, pk, lancamento_id):
    """Staff ESTORNA um lançamento do ledger de aventuras. Em transação única, devolve:
    personagem.aventuras -= qtd e carteira -= ouro pago (e braseiros, com piso 0), e marca a
    linha revertida. GUARDAS (recusa com mensagem clara, sem tocar nos contadores):
      (a) se `aventuras - qtd` ficar abaixo do mínimo exigido pelo NÍVEL ATUAL do
          personagem → 'o personagem já subiu de nível com essas aventuras';
      (b) se a carteira não cobrir o estorno → 'ouro insuficiente para estornar';
      (c) se a linha já estiver revertida."""
    from . import permissions as perms
    from .models import TbPersonagem, TbPersonagemAventura
    from .character_engine import aventuras_para_nivel
    if not perms.is_staff_user(request.user):
        raise Http404
    p = _ficha_editavel(request, pk)
    erro = None
    with transaction.atomic():
        lanc = get_object_or_404(
            TbPersonagemAventura.objects.select_for_update(),
            pk=lancamento_id, id_personagem=p,
        )
        p = TbPersonagem.objects.select_for_update().get(pk=p.pk)
        if lanc.revertido:
            erro = 'ja_revertido'
        else:
            qtd = int(lanc.qtd_aventuras or 0)
            ouro_pc = int(lanc.ouro_pago_pc or 0)
            minimo = aventuras_para_nivel(p.nivel or 1)
            if int(p.aventuras or 0) - qtd < minimo:
                erro = 'teto_nivel'
            elif int(p.carteira_pc or 0) < ouro_pc:
                erro = 'ouro_insuf'
            else:
                p.aventuras = int(p.aventuras or 0) - qtd
                p.carteira_pc = int(p.carteira_pc or 0) - ouro_pc
                p.braseiros = max(0, int(p.braseiros or 0) - int(lanc.braseiros_pago or 0))
                p.save(update_fields=['aventuras', 'carteira_pc', 'braseiros', 'atualizado_em'])
                _registrar_transacao(
                    p, 'ajuste', 'Estorno de aventuras: %s' % lanc.nome_aventura, -ouro_pc)
                lanc.revertido = True
                lanc.revertido_em = timezone.now()
                lanc.revertido_por = request.user
                lanc.save(update_fields=['revertido', 'revertido_em', 'revertido_por'])
    if erro:
        return _aventuras_staff_resposta(
            request, p, rollback_msg=erro, ok=False)
    return _aventuras_staff_resposta(request, p, rollback_msg='ok')


@login_required(login_url='/login/')
@require_POST
def personagem_conceder_item(request, pk):
    """STAFF concede um item do CATÁLOGO COMPLETO (mágico OU mundano, INCLUSIVE os itens
    de missão sem preço, que a loja não vende) ao inventário do personagem. NÃO debita
    ouro e NÃO registra transação — não é compra, é recompensa. Empilha consumível
    idêntico da MESMA origem (qtd) como a compra faz; item equipável/sintonizável vira
    uma linha própria. Grava a trilha (quem/quando/origem) na linha de inventário — o
    item concedido aparece no inventário normal e pode ser equipado/sintonizado.

    Gate `is_staff_user` idêntico ao registrar-aventuras: o DONO (não-staff) não concede.
    """
    from . import permissions as perms
    from .models import TbItemMagico, TbItemMundano, TbPersonagemItem
    from .character_engine import _item_consumivel_meta
    if not perms.is_staff_user(request.user):
        raise Http404
    p = _ficha_editavel(request, pk)
    back = reverse('editar_ficha', args=[pk])
    tipo = (request.POST.get('tipo') or 'magico').strip().lower()
    slug = (request.POST.get('item') or '').strip()
    nota = (request.POST.get('nota_origem') or '').strip()[:255]
    try:
        qtd = max(1, min(99, int(request.POST.get('qtd') or 1)))
    except (TypeError, ValueError):
        qtd = 1
    agora = timezone.now()
    if tipo == 'mundano':
        item = TbItemMundano.objects.filter(slug=slug).first()
        if not item:
            return _concessao_resposta(request, p, 'invalido', ok=False)
        with transaction.atomic():
            mec = mecanica_de_tags(item.tags_json, item.subcategoria)
            # empilha só em outra CONCESSÃO da mesma origem (mantém a trilha coerente e a
            # reversão precisa); item equipável (armadura/escudo) nunca empilha.
            existente = (TbPersonagemItem.objects.filter(
                id_personagem=p, nome=item.nome, id_item_magico__isnull=True,
                equipado=False, concedido_em__isnull=False, origem_nota=nota).first()
                if not mec['tipo_equip'] else None)
            if existente:
                existente.qtd = (existente.qtd or 0) + qtd
                existente.concedido_por = request.user
                existente.concedido_em = agora
                existente.save(update_fields=['qtd', 'concedido_por', 'concedido_em'])
            else:
                TbPersonagemItem.objects.create(
                    id_personagem=p, qtd=qtd, nome=item.nome, custo=(item.preco or ''),
                    tags_json=list(item.tags_json or []),
                    concedido_por=request.user, concedido_em=agora, origem_nota=nota)
    else:
        item = TbItemMagico.objects.filter(slug=slug).first()
        if not item:
            return _concessao_resposta(request, p, 'invalido', ok=False)
        with transaction.atomic():
            consumivel = _item_consumivel_meta(None, item)['consumivel']
            existente = (TbPersonagemItem.objects.filter(
                id_personagem=p, id_item_magico=item, equipado=False, sintonizado=False,
                concedido_em__isnull=False, origem_nota=nota).first()
                if consumivel else None)
            if existente:
                existente.qtd = (existente.qtd or 0) + qtd
                existente.concedido_por = request.user
                existente.concedido_em = agora
                existente.save(update_fields=['qtd', 'concedido_por', 'concedido_em'])
            else:
                custo = ('%g PO' % float(item.preco)) if item.preco and float(item.preco) > 0 else ''
                TbPersonagemItem.objects.create(
                    id_personagem=p, qtd=qtd, nome=item.nome, custo=custo,
                    id_item_magico=item, equipado=False, sintonizado=False,
                    concedido_por=request.user, concedido_em=agora, origem_nota=nota)
    return _concessao_resposta(request, p, 'ok')


@login_required(login_url='/login/')
@require_POST
def personagem_reverter_concessao(request, pk, item_id):
    """STAFF reverte uma concessão errada removendo a LINHA de inventário concedida.
    Como a concessão não mexeu em ouro, a reversão também não — só apaga a linha.
    GUARDA mínima e sensata (recusa com mensagem, sem apagar nada):
      (a) a linha precisa SER uma concessão (concedido_em não-nulo) — reversão não
          apaga item comprado/normal;
      (b) o item NÃO pode estar equipado nem sintonizado (o personagem já está usando):
          desequipe/dessintonize antes. Não rastreamos consumo parcial além do `qtd`,
          então reverter remove o restante daquela concessão (documentado).
    """
    from . import permissions as perms
    from .models import TbPersonagemItem
    if not perms.is_staff_user(request.user):
        raise Http404
    p = _ficha_editavel(request, pk)
    back = reverse('editar_ficha', args=[pk])
    with transaction.atomic():
        it = (TbPersonagemItem.objects.select_for_update()
              .filter(id=item_id, id_personagem=p).first())
        if not it or it.concedido_em is None:
            return _concessao_resposta(request, p, 'rev_invalido', ok=False)
        if it.equipado or it.sintonizado:
            return _concessao_resposta(request, p, 'rev_em_uso', ok=False)
        it.delete()
    return _concessao_resposta(request, p, 'revertido')


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
        body = _tag_block(t, 'multiclass_req')
        if body is not None:
            return body
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
    """Wrapper fino do PRG legado: adiciona uma classe por multiclasse (nível 1). A
    lógica pura (teto de aventuras + pré-requisito) vive em `_lvl_aplicar_adicionar_classe`;
    aqui só mapeia o código de erro para a query-string `?mc=…` que a página consome."""
    p = _ficha_editavel(request, pk)
    erros = _lvl_aplicar_adicionar_classe(p, {'classe': request.POST.get('classe')})
    if not erros:
        _sync_magias_concedidas(p)
        _refresh_vitais_derivados(p)
        return redirect(reverse('editar_ficha', args=[pk]) + '?mc=ok')
    return redirect(reverse('editar_ficha', args=[pk]) + '?mc=' + _MC_ERRO_CODE.get(erros[0], 'invalido'))


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_subclasse(request, pk):
    """Wrapper fino do PRG legado: escolhe a subclasse da classe principal."""
    p = _ficha_editavel(request, pk)
    erros = _lvl_aplicar_subclasse(p, {'subclasse': request.POST.get('subclasse')})
    if not erros:
        _sync_magias_concedidas(p)
        _refresh_vitais_derivados(p)
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_aplicar_asi(request, pk):
    """Wrapper fino do PRG legado: aplica um ASI (+2/+1 em atributos OU talento+atributo).
    Lógica pura em `_lvl_aplicar_asi`."""
    p = _ficha_editavel(request, pk)
    erros = _lvl_aplicar_asi(p, {
        'modo': request.POST.get('tipo'),
        'talento': request.POST.get('talento'),
        'talento_attr': request.POST.get('talento_attr'),
        'asi_attr_1': request.POST.get('asi_attr_1'), 'mais2': request.POST.get('mais2'),
        'asi_attr_2': request.POST.get('asi_attr_2'), 'mais1': request.POST.get('mais1'),
    })
    if not erros:
        _sync_magias_concedidas(p)
        _refresh_vitais_derivados(p)
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_talento_racial(request, pk):
    """Escolhe um TALENTO RACIAL de nível-marco (5/9/13/17) do pool raça/linhagem/essência.
    Valida contra `_pendencias_talento_racial`, grava TbPersonagemTalento (categoria='racial')
    e ressincroniza as magias da Essência (caso o talento conceda magias, ex.: Magia
    Elemental Aprimorada)."""
    p = _ficha_editavel(request, pk)
    erros = _lvl_aplicar_talento_racial(p, {'nivel': request.POST.get('nivel'),
                                            'talento': request.POST.get('talento')})
    if not erros:
        _sync_magias_essencia(p)
        _refresh_vitais_derivados(p)
    return redirect(reverse('editar_ficha', args=[pk]) + '#talentos-raciais')


@login_required(login_url='/login/')
@require_POST
def personagem_escolher_opcoes(request, pk):
    """Adiciona/remove uma escolha de classe do painel genérico (opção — metamagia,
    manobra, segredo, estilo de luta… — OU perícia de `pick:pericia`). Valida contra o
    grupo derivado (limite + universo) e PERSISTE pelo REGISTRY do kind (FONTE ÚNICA,
    sem ramificar por tipo): o token submetido `val` é o id da opção OU o slug da perícia."""
    p = _ficha_editavel(request, pk)
    destino = reverse('editar_ficha', args=[pk]) + '#opcoes'
    erros = _lvl_aplicar_opcao(p, {
        'acao': request.POST.get('acao'), 'escolha': request.POST.get('escolha'),
        'classe': request.POST.get('classe'), 'slug': request.POST.get('slug'),
        'val': request.POST.get('opcao') or request.POST.get('val'),
    })
    if not erros:
        _sync_magias_concedidas(p)
        _refresh_vitais_derivados(p)
    return redirect(destino)


def _pendencias_magias(personagem, subclasse_override=None, classe_id=None):
    """Magias a aprender no nível atual: truques (todos casters) e magias conhecidas
    (só known casters, com recurso 'Magias Conhecidas'), até o nível máximo conjurável.

    `subclasse_override`: força a subclasse-fonte da conjuração (em vez da já atribuída ao
    personagem). Usado no level-up para computar a pendência PROSPECTIVA de um third-caster
    (Cavaleiro/Trapaceiro Arcano) cuja subclasse ainda está sendo ESCOLHIDA no mesmo passo —
    a conjuração vem da subclasse, e sem isto os truques do nível-alvo não apareceriam."""
    from .models import TbMagia, TbRecursoclasse, TbClassehabilidade, TbPersonagemEscolha
    pc = _personagem_classe_contexto(personagem, classe_id)
    if not pc:
        return None
    classe, nivel = pc.id_classe, (pc.nivel or 1)
    subclasse = subclasse_override if subclasse_override is not None else _caster_subclasse(pc)
    spell_info = _classe_spellcasting_info(classe, nivel_habilidades=nivel, subclasse=subclasse)
    if not spell_info:
        return None

    def res_at(substrs):
        needles = [s.replace('_', '-') for s in substrs] + [s.replace('-', '_') for s in substrs]
        # base (id_subclasse null) + recursos da SUBCLASSE do personagem (third-casters
        # guardam truques/magias-preparadas como recurso de subclasse a partir do nv3).
        cond = Q(id_classe=classe, id_subclasse__isnull=True)
        if subclasse is not None:
            cond |= Q(id_subclasse=subclasse)
        for r in TbRecursoclasse.objects.filter(cond):
            if any(s in (r.slug or '').lower() for s in needles):
                vj = r.valores_json or {}
                ks = sorted(int(k) for k in vj if int(k) <= nivel)
                if ks:
                    try:
                        return int(str(vj[str(ks[-1])]).strip())
                    except (ValueError, TypeError):
                        pass
        return None

    # TETO DE NÍVEL DE MAGIA = topo da tabela de slots DA PRÓPRIA CLASSE (single-class de
    # propósito). Regra 5e: o nível máximo conhecível/preparável vem do nível NAQUELA classe,
    # não dos slots *pooled* de multiclasse — por isso lemos a tabela desta classe/subclasse.
    _slot_tbl = _classe_slot_table(classe, nivel, subclasse)
    maxlv = max([lv for lv, t in _slot_tbl.items() if t > 0], default=0)
    conhecidos = set(personagem.magias.values_list('id_magia__slug', flat=True))
    magias_classe = personagem.magias.filter(origem__iexact=classe.nome)
    if personagem.classes.count() == 1:
        magias_classe = personagem.magias.filter(
            Q(origem__iexact=classe.nome) | Q(origem__isnull=True) | Q(origem=''))
    truques_exp = res_at(['truque']) or 0
    # third-casters (Cavaleiro/Trapaceiro Arcano) chamam o recurso de 'magias-preparadas'
    # (apesar de prepara:conhecidas) — o needle precisa cobrir os dois rótulos, como o criador.
    known_exp = res_at(['magias-conhecidas', 'magias-preparadas'])
    cant_pend = max(0, truques_exp - magias_classe.filter(nivel=0).count())
    known_pend = max(
        0, known_exp - magias_classe.filter(nivel__gte=1).count()
    ) if known_exp is not None else 0
    lt = [{'slug': m.slug, 'nome': m.nome} for m in
          TbMagia.objects.filter(_spell_list_q(spell_info['lista_nomes']), nivel=0).order_by('nome') if m.slug not in conhecidos]
    lm = [{'slug': m.slug, 'nome': m.nome, 'nivel': m.nivel} for m in
          TbMagia.objects.filter(_spell_list_q(spell_info['lista_nomes']), nivel__gte=1,
                                  nivel__lte=maxlv).order_by('nivel', 'nome') if m.slug not in conhecidos]
    _swap_cond = Q(id_classe=classe, id_subclasse__isnull=True)
    if subclasse is not None:
        _swap_cond |= Q(id_subclasse=subclasse)
    # TROCA DE MAGIA AO SUBIR DE NÍVEL: tag explícita `swap:level_up` OU inferida quando o
    # spellcasting da classe/subclasse é do tipo `prepara:conhecidas`. Regra 5e: o caster que
    # CONHECE magias troca 1 conhecida por outra ao subir de nível; o caster que PREPARA
    # re-prepara livre a cada descanso e NÃO usa swap. A inferência cobre o Cavaleiro Arcano
    # (prepara:conhecidas) sem editar o dado; tags `swap:level_up` já existentes continuam
    # válidas (redundantes, inofensivas).
    swap_lvl = (spell_info.get('prepara') == 'conhecidas'
                or any(re.search(r'swap\s*:\s*level_up', str(t))
                       for h in TbClassehabilidade.objects.filter(_swap_cond)
                       for t in (h.tags_json or [])))
    # QUOTA DE TROCA (regra do PO): o caster CONHECIDO troca UMA magia por nível. `swap_disponivel`
    # = a classe permite troca (`swap_lvl`) E ainda NÃO houve troca registrada no NÍVEL TOTAL atual
    # (`TbPersonagemEscolha` tipo='troca_magia', valor=str(nível total)). Personagens antigos, sem
    # registro, caem naturalmente no ramo "disponível". Enforcement em `_lvl_aplicar_trocar_magia`.
    nivel_total = sum(int(c.nivel or 0) for c in personagem.classes.all()) or int(personagem.nivel or 1)
    swap_usada = TbPersonagemEscolha.objects.filter(
        id_personagem=personagem, tipo='troca_magia', valor=str(nivel_total)).exists()
    conhecidas = [{'slug': m.id_magia.slug, 'nome': m.nome, 'nivel': m.nivel}
                  for m in magias_classe.select_related('id_magia').filter(
                      id_magia__isnull=False).order_by('nivel', 'nome')]
    return {'cantrips_pend': cant_pend, 'known_pend': known_pend, 'max_nivel': maxlv,
            'lista_truques': lt, 'lista_magias': lm, 'lista_nomes': spell_info['lista_nomes'],
            'swap_level_up': swap_lvl, 'swap_disponivel': bool(swap_lvl) and not swap_usada,
            'conhecidas': conhecidas, 'prospectiva': False, 'subclasses_prospectivas': []}


def _pendencias_magias_levelup(personagem, pend_nivel, classe_id=None):
    """Pendência de magias para o WIZARD de level-up, ciente da subclasse que está prestes a
    ser escolhida NESTE passo. Regressão do print 'Cavaleiro Arcano não deixa escolher truque':
    para third-casters (Cavaleiro/Trapaceiro Arcano) a conjuração vem da SUBCLASSE, e no nível
    em que a subclasse é adquirida ela ainda NÃO está atribuída — `_pendencias_magias` via
    None e o passo de truques nunca era renderizado (a classe BASE não conjura).

    Estratégia: se a pendência normal existe (classe base conjura, ou a subclasse já foi
    atribuída), devolve-a. Senão, se há uma subclasse PENDENTE no nível-alvo, calcula a
    pendência PROSPECTIVA para cada subclasse candidata que conjure — unindo os pools (o
    validador de `_lvl_aplicar_aprender_magias` filtra depois pela subclasse de fato escolhida)
    — e a marca `prospectiva=True` com a lista de slugs de subclasse que a destravam. O cliente
    só revela o passo quando a prévia ao vivo (subclasse já no lote) confirma truques/conhecidas > 0."""
    from .models import TbSubclasse
    pendm = _pendencias_magias(personagem, classe_id=classe_id)
    if pendm is not None:
        return pendm
    if not pend_nivel.get('subclasse'):
        return None
    pc = _personagem_classe_contexto(personagem, classe_id)
    if not pc or pc.id_subclasse_id:
        return None
    base = None
    truques, magias, nomes, slugs = {}, {}, [], []
    for opt in pend_nivel.get('subclasses') or []:
        sub = TbSubclasse.objects.filter(pk=opt['id']).first()
        if not sub or not _classe_spellcasting_info(
                pc.id_classe, nivel_habilidades=int(pc.nivel or 1), subclasse=sub):
            continue
        cand = _pendencias_magias(
            personagem, subclasse_override=sub, classe_id=classe_id)
        if not cand or not (cand['cantrips_pend'] or cand['known_pend']):
            continue
        slugs.append(sub.slug)
        if base is None:
            base = cand
        else:  # une contagens/pools de múltiplas subclasses conjuradoras (raro)
            base['cantrips_pend'] = max(base['cantrips_pend'], cand['cantrips_pend'])
            base['known_pend'] = max(base['known_pend'], cand['known_pend'])
            base['max_nivel'] = max(base['max_nivel'], cand['max_nivel'])
        for m in cand['lista_truques']:
            truques.setdefault(m['slug'], m)
        for m in cand['lista_magias']:
            magias.setdefault(m['slug'], m)
        for n in cand['lista_nomes']:
            if n not in nomes:
                nomes.append(n)
    if base is None:
        return None
    base['lista_truques'] = sorted(truques.values(), key=lambda m: m['nome'])
    base['lista_magias'] = sorted(magias.values(), key=lambda m: (m['nivel'], m['nome']))
    base['lista_nomes'] = nomes
    base['prospectiva'] = True
    base['subclasses_prospectivas'] = slugs
    return base


_ABIL_EN = {'FOR': 'str', 'DES': 'dex', 'CON': 'con', 'INT': 'int', 'SAB': 'wis', 'CAR': 'cha'}


def _magias_preparadas_info(personagem, ficha):
    """Conjuradores PREPARADOS (prepara:preparadas + prep-limite): limite calculado da
    fórmula, lista de magias da classe (nv1..máx) e set preparado atual. None se não-preparado."""
    from .models import TbMagia
    from .character_engine import _eval_formula
    pc = personagem.classes.filter(principal=True).first() or personagem.classes.first()
    if not pc:
        return None
    classe, nivel = pc.id_classe, (pc.nivel or 1)
    subclasse = _caster_subclasse(pc)
    spell_info = _classe_spellcasting_info(classe, nivel_habilidades=nivel, subclasse=subclasse)
    if not spell_info or spell_info.get('prepara') != 'preparadas' or not spell_info.get('prep_formula'):
        return None
    ats = ficha['atributos']
    ctx = {'classlvl': nivel, 'lvl': ficha['nivel_total'], 'pb': ficha['bonus_proficiencia']}
    for sig, en in _ABIL_EN.items():
        ctx[en + '_mod'] = ats[sig]['mod']
    abil = spell_info['ability']
    ctx['spell_mod'] = (max(ctx[a + '_mod'] for a in abil.split('|')) if '|' in abil
                        else ctx.get(abil + '_mod', 0))
    limite = _eval_formula(spell_info['prep_formula'].strip(), ctx)
    limite = max(1, limite) if limite is not None else None
    # Mesmo teto de nível de magia do caminho conhecido: topo da tabela de slots DA PRÓPRIA
    # classe (single-class de propósito — regra 5e do nível NAQUELA classe).
    _slot_tbl = _classe_slot_table(classe, nivel, subclasse)
    maxlv = max([lv for lv, t in _slot_tbl.items() if t > 0], default=0)
    preparadas = set(personagem.magias.filter(nivel__gte=1, preparada=True, sempre_preparada=False)
                     .values_list('id_magia__slug', flat=True))
    por_nivel = {}
    for m in TbMagia.objects.filter(_spell_list_q(spell_info['lista_nomes']), nivel__gte=1,
                                    nivel__lte=maxlv).order_by('nivel', 'nome'):
        por_nivel.setdefault(m.nivel, []).append(
            {'slug': m.slug, 'nome': m.nome, 'marcada': m.slug in preparadas})
    grupos = [{'nivel': nv, 'magias': por_nivel[nv]} for nv in sorted(por_nivel)]
    return {'classe': classe.nome, 'ability': abil, 'limite': limite, 'max_nivel': maxlv,
            'grupos': grupos, 'preparadas_count': len(preparadas)}


@login_required(login_url='/login/')
@require_POST
def personagem_aprender_magias(request, pk):
    """Wrapper fino do PRG legado: aprende truques/magias conhecidas no nível atual."""
    p = _ficha_editavel(request, pk)
    _lvl_aplicar_aprender_magias(p, {'classe': request.POST.get('classe'),
                                     'truques': request.POST.getlist('truques'),
                                     'magias': request.POST.getlist('magias')})
    return redirect('editar_ficha', pk=pk)


@login_required(login_url='/login/')
@require_POST
def personagem_trocar_magia(request, pk):
    """Wrapper fino do PRG legado: troca 1 magia conhecida por outra (tag swap:level_up)."""
    p = _ficha_editavel(request, pk)
    _lvl_aplicar_trocar_magia(p, {'classe': request.POST.get('classe'),
                                  'remover': request.POST.get('remover'),
                                  'adicionar': request.POST.get('adicionar')})
    return redirect('editar_ficha', pk=pk)


# ======================================================================================
# LEVEL-UP: núcleo puro (validar+gravar, SEM request/redirect) + orquestração em lote.
#
# Cada `_lvl_aplicar_<coisa>(personagem, payload) -> list[str]` valida e grava uma escolha
# de progressão e devolve a lista de erros (vazia = ok). Os 8 endpoints PRG legados viraram
# wrappers finos em cima destas funções (FONTE ÚNICA), e o mesmo conjunto alimenta os dois
# endpoints JSON novos (`personagem_levelup_aplicar` em lote + `personagem_levelup_preview`
# em transação revertida) — mesmo padrão de `_criador_resolver`/`_criador_persistir`.
#
# CONTRATO das funções puras: NÃO chamam `_sync_magias_concedidas`/`_refresh_vitais_derivados`
# (o orquestrador chama UMA vez ao final); apenas gravam o próprio domínio no banco. São
# aplicadas em SEQUÊNCIA (cada uma relê o estado já gravado pela anterior — ex.: subir de
# nível ANTES de liberar o slot de ASI/subclasse), por isso o lote é ordenado por `_LVL_ORDEM`.
# ======================================================================================

# Mensagens canônicas (também servem de código p/ mapear a query-string dos wrappers legados).
_ERR_LVL_MAX = 'Nível 20 é o máximo — não há como subir mais.'
_ERR_LVL_TETO = 'Suas aventuras ainda não permitem subir de nível.'
_ERR_MC_MAX = 'Nível 20 é o máximo — não há como multiclassar.'
_ERR_MC_TETO = 'Suas aventuras ainda não permitem adicionar uma classe.'
_ERR_MC_INVALIDO = 'Classe inválida ou já possuída.'
_ERR_MC_PREREQ = 'Pré-requisito de multiclasse não atendido.'
_ERR_SUB_INVALIDA = 'Subclasse inválida ou já escolhida.'
_ERR_ASI_SEM_SLOT = 'Nenhum incremento de atributo (ASI) pendente neste nível.'
_ERR_ASI_TALENTO = 'Talento de ASI inválido para este personagem.'
_ERR_ASI_ATRIB = 'Escolha de atributos do ASI inválida.'
_ERR_TALENTO_RACIAL = 'Talento racial inválido para este nível.'
_ERR_OPCAO_INVALIDA = 'Escolha de opção inválida (fora do universo, duplicada ou sem slot).'
_ERR_MAGIAS_SEM_PEND = 'Nada a aprender: nenhuma magia pendente neste nível.'
_ERR_TROCA_INDISPONIVEL = 'Troca de magia indisponível para esta classe/nível.'
_ERR_TROCA_INVALIDA = 'Troca de magia inválida (regra de nível/truque não satisfeita).'
_ERR_TROCA_JA_USADA = 'Você já trocou uma magia neste nível.'

_MC_ERRO_CODE = {_ERR_MC_MAX: 'max', _ERR_MC_TETO: 'teto',
                 _ERR_MC_INVALIDO: 'invalido', _ERR_MC_PREREQ: 'prereq'}


def _lvl_aplicar_subir_nivel(personagem, payload):
    """Sobe 1 nível da classe escolhida (ou principal), respeitando o teto de aventuras."""
    from .character_engine import nivel_por_aventuras
    if (personagem.nivel or 0) >= 20:
        return [_ERR_LVL_MAX]
    # nº de aventuras define o nível-TETO (não passa do que as aventuras permitem)
    if (personagem.nivel or 0) >= min(nivel_por_aventuras(personagem.aventuras), 20):
        return [_ERR_LVL_TETO]
    cid = (payload or {}).get('classe')
    pc = (personagem.classes.filter(id_classe_id=cid).first() if cid else None) \
        or personagem.classes.filter(principal=True).first() or personagem.classes.first()
    if pc and (pc.nivel or 1) < 20:
        pc.nivel = (pc.nivel or 1) + 1
        pc.save(update_fields=['nivel'])
        personagem.nivel = sum(c.nivel or 0 for c in personagem.classes.all())
        personagem.save(update_fields=['nivel', 'atualizado_em'])
    return []


def _lvl_aplicar_adicionar_classe(personagem, payload):
    """Adiciona uma classe por multiclasse (nível 1) se o pré-requisito for atendido.
    Multiclasse também SOBE o nível total — respeita o mesmo teto de aventuras (BUG-1)."""
    from .models import TbClasse, TbPersonagemClasse
    from .character_engine import derive, nivel_por_aventuras
    if (personagem.nivel or 0) >= 20:
        return [_ERR_MC_MAX]
    if (personagem.nivel or 0) >= min(nivel_por_aventuras(personagem.aventuras), 20):
        return [_ERR_MC_TETO]
    cl = TbClasse.objects.filter(id_classe=(payload or {}).get('classe')).first()
    if not cl or personagem.classes.filter(id_classe=cl).exists():
        return [_ERR_MC_INVALIDO]
    if not _multiclass_atende(derive(personagem)['atributos'], _classe_req(cl)):
        return [_ERR_MC_PREREQ]
    TbPersonagemClasse.objects.create(id_personagem=personagem, id_classe=cl, nivel=1, principal=False)
    personagem.nivel = sum(c.nivel or 0 for c in personagem.classes.all())
    personagem.save(update_fields=['nivel', 'atualizado_em'])
    return []


def _lvl_aplicar_subclasse(personagem, payload):
    """Escolhe a subclasse da classe indicada; o legado cai na principal."""
    from .models import TbSubclasse
    payload = payload or {}
    pc = _personagem_classe_contexto(personagem, payload.get('classe'))
    if not pc:
        return [_ERR_SUB_INVALIDA]
    sub = TbSubclasse.objects.filter(
        id_subclasse=payload.get('subclasse'), id_classe=pc.id_classe).first()
    if not sub or pc.id_subclasse_id:
        return [_ERR_SUB_INVALIDA]
    pc.id_subclasse = sub
    pc.save(update_fields=['id_subclasse'])
    return []


def _lvl_aplicar_asi(personagem, payload):
    """Aplica um incremento de atributo: `modo='talento'` (talento + atributo do talento)
    ou o ASI de classe padrão (+2 num atributo OU +1/+1 em dois)."""
    from .models import TbPersonagemAtributoBonus, TbPersonagemTalento, TbTalento
    from . import point_buy
    from .character_engine import derive
    payload = payload or {}
    if _pendencias_nivel(personagem)['asi_pendentes'] < 1:
        return [_ERR_ASI_SEM_SLOT]
    slot = _next_asi_slot(personagem)
    nivel = slot['nivel'] if slot else (personagem.nivel or 1)
    origem_base = slot['origem'] if slot else 'ASI N%d' % nivel
    if (payload.get('modo') or payload.get('tipo')) == 'talento':
        t = TbTalento.objects.filter(id_talento=payload.get('talento')).first()
        attr = payload.get('talento_attr')
        validos = {x['id'] for x in _talentos_asi_disponiveis(personagem, derive(personagem))}
        if not (t and t.id_talento in validos and attr in _talento_attr_options(t)):
            return [_ERR_ASI_TALENTO]
        TbPersonagemTalento.objects.create(id_personagem=personagem, id_talento=t, categoria='asi-nivel',
                                           nivel=nivel, nome=t.nome, detalhes='asi_attr:%s' % attr)
        TbPersonagemAtributoBonus.objects.create(
            id_personagem=personagem, atributo=attr, valor=1,
            origem='Talento %s N%d' % (t.nome, nivel), origem_tipo='talento-asi')
        return []
    attr1 = payload.get('asi_attr_1') or payload.get('mais2')
    attr2 = payload.get('asi_attr_2') or payload.get('mais1')
    ok, _e = point_buy.validar_asi_classe(attr1, attr2)
    if not ok:
        return [_ERR_ASI_ATRIB]
    if attr1 == attr2:
        TbPersonagemAtributoBonus.objects.create(
            id_personagem=personagem, atributo=attr1, valor=2,
            origem=origem_base, origem_tipo='asi-classe')
    else:
        TbPersonagemAtributoBonus.objects.create(
            id_personagem=personagem, atributo=attr1, valor=1,
            origem=origem_base, origem_tipo='asi-classe')
        TbPersonagemAtributoBonus.objects.create(
            id_personagem=personagem, atributo=attr2, valor=1,
            origem=origem_base, origem_tipo='asi-classe')
    return []


def _lvl_aplicar_talento_racial(personagem, payload):
    """Escolhe um TALENTO RACIAL de nível-marco (5/9/13/17), validado contra o pool
    raça/linhagem/essência de `_pendencias_talento_racial`."""
    from .models import TbPersonagemTalento
    payload = payload or {}
    try:
        nivel = int(payload.get('nivel') or 0)
    except (TypeError, ValueError):
        nivel = 0
    nome = (payload.get('talento') or '').strip()
    bloco = next((b for b in _pendencias_talento_racial(personagem) if b['nivel'] == nivel), None)
    if not (bloco and any(o['nome'] == nome for o in bloco['opcoes'])):
        return [_ERR_TALENTO_RACIAL]
    TbPersonagemTalento.objects.create(id_personagem=personagem, categoria='racial', nivel=nivel, nome=nome)
    return []


def _lvl_aplicar_opcao(personagem, payload):
    """Adiciona/remove uma escolha de classe do painel genérico (opção OU perícia de
    `pick:pericia`). `acao='remover'` apaga a TbPersonagemEscolha; senão anexa `val`
    (id da opção OU slug) validando limite/universo e persistindo pelo REGISTRY do kind."""
    from .models import TbPersonagemEscolha
    from . import picks as _picks
    payload = payload or {}
    if payload.get('acao') == 'remover':
        TbPersonagemEscolha.objects.filter(id=payload.get('escolha'), id_personagem=personagem).delete()
        return []
    slug = (payload.get('slug') or '').strip()
    val = (payload.get('val') or payload.get('opcao') or '').strip()
    if not (slug and val):
        return [_ERR_OPCAO_INVALIDA]
    # classe do grupo: features raciais/antecedente têm classe_id=None e o front manda ''
    # (ou 'None' renderizado por template) — normaliza os dois lados antes de comparar.
    alvo_classe = str(payload.get('classe') or '')
    if alvo_classe == 'None':
        alvo_classe = ''

    def _grp_universo(g):
        return ({str(u['slug']) for u in g['universo']}
                | {str(u['id']) for u in g['universo'] if u.get('id') is not None})

    def _grp_escolhidos(g):
        # já-escolhidas por QUALQUER forma do token (id da opção ou slug/valor) p/ não duplicar
        out = set()
        for e in g['escolhidas']:
            if e.get('valor') is not None:
                out.add(str(e['valor']))
            if e.get('id_opcao') is not None:
                out.add(str(e['id_opcao']))
        return out

    # Um MESMO persist_tipo pode render VÁRIOS grupos com a mesma classe (ex.: humano Erthari
    # com talento de ORIGEM 'Determinação Comum' E talento GERAL 'Multitalentoso', ambos
    # persist_tipo='talento', classe_id=None). Desambigua pelo grupo cujo UNIVERSO contém o
    # `val`, com slot livre e sem duplicar — assim o talento geral cai no grupo geral e não é
    # recusado contra o universo (só-origem) do outro pick. Um único grupo mantém o comportamento.
    candidatos = [g for g in _picks.resolve_personagem(personagem, kinds=_OPCAO_PANEL_KINDS)
                  if g['persist_tipo'] == slug
                  and ('' if g['classe_id'] is None else str(g['classe_id'])) == alvo_classe]
    grupo = next((g for g in candidatos
                  if g['pendentes'] >= 1
                  and val in _grp_universo(g) and val not in _grp_escolhidos(g)), None)
    if grupo is None:
        return [_ERR_OPCAO_INVALIDA]
    # anexa no próximo slot livre (não sobrescreve escolhas anteriores)
    grupo['slot_base'] = grupo['prox_slot']
    _picks.registry_entry(grupo['kind'])['persist'](personagem, grupo, [val])
    return []


def _lvl_aplicar_aprender_magias(personagem, payload):
    """Aprende truques + magias conhecidas do nível atual (limitado às pendências)."""
    from .models import TbMagia, TbPersonagemMagia
    payload = payload or {}
    pc = _personagem_classe_contexto(personagem, payload.get('classe'))
    if not pc:
        return [_ERR_MAGIAS_SEM_PEND]
    pend = _pendencias_magias(personagem, classe_id=pc.id_classe_id)
    if not pend:
        return [_ERR_MAGIAS_SEM_PEND]
    classe = pc.id_classe
    tslugs = {m['slug'] for m in pend['lista_truques']}
    mslugs = {m['slug'] for m in pend['lista_magias']}
    novos_t = [s for s in dict.fromkeys(payload.get('truques') or []) if s in tslugs][:pend['cantrips_pend']]
    novos_m = [s for s in dict.fromkeys(payload.get('magias') or []) if s in mslugs][:pend['known_pend']]
    for slug in novos_t + novos_m:
        mg = TbMagia.objects.filter(slug=slug).first()
        if mg:
            TbPersonagemMagia.objects.create(id_personagem=personagem, id_magia=mg, nivel=mg.nivel,
                                             nome=mg.nome, preparada=True, origem=classe.nome)
    return []


def _lvl_aplicar_trocar_magia(personagem, payload):
    """Troca 1 magia CONHECIDA por outra ao subir de nível (tag swap:level_up).
    Truque↔truque, conhecida↔conhecida (nível 1..máx conjurável).

    GATE (regra do PO): UMA troca por NÍVEL TOTAL. Cada troca aplicada grava o nível em que
    foi usada como `TbPersonagemEscolha` (tipo='troca_magia', origem='swap', slot/valor = nível
    total). Uma SEGUNDA troca no MESMO nível é recusada com `_ERR_TROCA_JA_USADA`. Subir de
    nível libera outra troca naturalmente: o nível gravado passa a ser MENOR que o novo, então a
    checagem por `valor=str(nível_atual)` não acha registro. Personagens ANTIGOS (sem nenhum
    registro) ganham a troca do nível atual de graça — sem registro do nível → o gate deixa passar.
    Vale para o POST direto, para o endpoint legado (`personagem_trocar_magia`) e para o lote."""
    from .models import TbMagia, TbPersonagemMagia, TbPersonagemEscolha
    payload = payload or {}
    pc = _personagem_classe_contexto(personagem, payload.get('classe'))
    if not pc:
        return [_ERR_TROCA_INDISPONIVEL]
    pend = _pendencias_magias(personagem, classe_id=pc.id_classe_id)
    if not pend or not pend['swap_level_up']:
        return [_ERR_TROCA_INDISPONIVEL]
    # UMA por nível: se já há registro de troca no nível total atual, recusa antes de aplicar.
    nivel_atual = sum(int(c.nivel or 0) for c in personagem.classes.all()) or int(personagem.nivel or 1)
    if TbPersonagemEscolha.objects.filter(
            id_personagem=personagem, tipo='troca_magia', valor=str(nivel_atual)).exists():
        return [_ERR_TROCA_JA_USADA]
    classe = pc.id_classe
    conhecidas = {m['slug'] for m in pend['conhecidas']}
    disponiveis = {m['slug'] for m in pend['lista_truques']} | {m['slug'] for m in pend['lista_magias']}
    novo_slug = payload.get('adicionar')
    old_qs = personagem.magias.select_related('id_magia').filter(
        id_magia__slug=payload.get('remover'))
    if personagem.classes.count() == 1:
        old_qs = old_qs.filter(
            Q(origem__iexact=classe.nome) | Q(origem__isnull=True) | Q(origem=''))
    else:
        old_qs = old_qs.filter(origem__iexact=classe.nome)
    old = old_qs.first()
    new_mg = TbMagia.objects.filter(slug=novo_slug).first() if novo_slug in disponiveis else None
    if (old and new_mg and new_mg.slug not in conhecidas
            and (old.nivel == 0) == (new_mg.nivel == 0)        # truque↔truque
            and new_mg.nivel <= pend['max_nivel']):
        old.delete()
        TbPersonagemMagia.objects.create(id_personagem=personagem, id_magia=new_mg, nivel=new_mg.nivel,
                                         nome=new_mg.nome, preparada=True, origem=classe.nome)
        # Registra o nível em que a troca foi usada (slot=nível → um registro por nível, sem
        # colidir no unique_together (personagem, origem, tipo, slot)).
        TbPersonagemEscolha.objects.get_or_create(
            id_personagem=personagem, origem='swap', tipo='troca_magia', slot=nivel_atual,
            defaults={'valor': str(nivel_atual)})
        return []
    return [_ERR_TROCA_INVALIDA]


# Despacho por `tipo` da ação + ordem estável de aplicação do lote. A ordem garante as
# DEPENDÊNCIAS: subir de nível ANTES de subclasse/ASI/talento-racial/opções/magias, pois
# esses passos releem o nível já gravado para liberar o slot correspondente.
_LVL_ACTIONS = {
    'subir_nivel': _lvl_aplicar_subir_nivel,
    'adicionar_classe': _lvl_aplicar_adicionar_classe,
    'subclasse': _lvl_aplicar_subclasse,
    'asi': _lvl_aplicar_asi,
    'talento_racial': _lvl_aplicar_talento_racial,
    'opcao': _lvl_aplicar_opcao,
    'aprender_magias': _lvl_aplicar_aprender_magias,
    'trocar_magia': _lvl_aplicar_trocar_magia,
}
_LVL_ORDEM = {'subir_nivel': 0, 'adicionar_classe': 1, 'subclasse': 2, 'asi': 3,
              'talento_racial': 4, 'opcao': 5, 'aprender_magias': 6, 'trocar_magia': 7}


def _levelup_pendencias(personagem, classe_id=None):
    """Resumo das pendências de progressão restantes (mesmos critérios de editar_ficha_view)."""
    pend = _pendencias_nivel(personagem, classe_id)
    pendm = _pendencias_magias(personagem, classe_id=classe_id)
    tr = _pendencias_talento_racial(personagem)
    grupos = _opcao_grupos(personagem, classe_id)
    cant = int(pendm['cantrips_pend']) if pendm else 0
    known = int(pendm['known_pend']) if pendm else 0
    opcoes_pend = sum(g['pendentes'] for g in grupos)
    return {
        'subclasse': bool(pend['subclasse']),
        'asi_pendentes': int(pend['asi_pendentes']),
        'talento_racial_niveis': [b['nivel'] for b in tr],
        'opcoes_pendentes': int(opcoes_pend),
        'cantrips_pend': cant,
        'known_pend': known,
        'sem_pendencias': not (pend['subclasse'] or pend['asi_pendentes']
                               or cant or known or tr or opcoes_pend),
    }


def _levelup_status(personagem, ficha):
    """Elegibilidade de level-up (fonte do BOTÃO da ficha). `pode_subir` = há folga no teto
    de aventuras e nível < 20; `tem_pendencias` = escolhas do nível atual ainda abertas;
    `faltam_aventuras` = quanto falta pro próximo nível quando travado no teto."""
    from .character_engine import aventuras_para_nivel
    prog = ficha.get('progressao') or {}
    nivel_total = int(ficha.get('nivel_total') or 0)
    no_teto = bool(prog.get('no_teto'))
    pode_subir = nivel_total < 20 and not no_teto
    resumo = _levelup_pendencias(personagem)
    tem_pend = not resumo['sem_pendencias']
    faltam = None
    if not pode_subir and nivel_total < 20:
        faltam = max(0, aventuras_para_nivel(min(nivel_total + 1, 22)) - int(prog.get('aventuras') or 0))
    return {
        'pode_subir': pode_subir,
        'tem_pendencias': tem_pend,
        'mostrar_botao': pode_subir or tem_pend,
        'faltam_aventuras': faltam,
        'nivel_alvo': min(nivel_total + 1, 20),
        'no_maximo': nivel_total >= 20,
        'no_teto': no_teto,
    }


def _levelup_ganhos(personagem, classe_id, nivel_alvo, con_mod):
    """Ganhos DETERMINÍSTICOS de levar `classe_id` ao `nivel_alvo` (derivável das tabelas
    de progressão): aumento de PV (dado//2+1+CON), features novas da classe base + da
    subclasse já escolhida NAQUELE nível (table_only=False) e a nota de subclasse quando o
    nível a desbloqueia sem uma escolhida ainda."""
    from .models import TbClassehabilidade
    from .character_engine import _dado_de_vida_classe, _subclass_min_level
    pc = (personagem.classes.filter(id_classe_id=classe_id).first() if classe_id else None) \
        or personagem.classes.filter(principal=True).first() or personagem.classes.first()
    ganhos = {'classe': '', 'subclasse': '', 'nivel_alvo': nivel_alvo, 'pv_ganho': None,
              'features': [], 'abre_subclasse': False, 'subclasse_nivel': None}
    if not pc:
        return ganhos
    classe = pc.id_classe
    ganhos['classe'] = classe.nome
    die = _dado_de_vida_classe(classe)
    if die is not None:
        ganhos['pv_ganho'] = die // 2 + 1 + int(con_mod or 0)
    for h in TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True,
            niveladquirido=nivel_alvo, table_only=False).order_by('nome'):
        ganhos['features'].append({'fonte': classe.nome, 'nome': h.nome, 'descricao': h.descricao})
    if pc.id_subclasse_id:
        ganhos['subclasse'] = pc.id_subclasse.nome
        for h in TbClassehabilidade.objects.filter(
                id_subclasse=pc.id_subclasse, niveladquirido=nivel_alvo,
                table_only=False).order_by('nome'):
            ganhos['features'].append({'fonte': pc.id_subclasse.nome, 'nome': h.nome,
                                       'descricao': h.descricao})
    smin = _subclass_min_level(classe)
    if smin and nivel_alvo == smin and not pc.id_subclasse_id:
        ganhos['abre_subclasse'] = True
        ganhos['subclasse_nivel'] = smin
    return ganhos


def _levelup_recursos_delta(rec_antes, rec_alvo):
    """Recursos de classe que NASCEM ou CRESCEM no nível-alvo (compara o `maximo` de antes
    com o do estado já subido). `rec_antes` é {slug: recurso}; `rec_alvo` é a lista do estado
    subido. Devolve [{nome, classe, de, para, novo}]."""
    out = []
    for r in rec_alvo:
        antes = rec_antes.get(r['slug'])
        try:
            mx_alvo = int(r.get('maximo') or 0)
            mx_antes = int(antes['maximo']) if antes else None
        except (TypeError, ValueError):
            continue
        if antes is None:
            out.append({'nome': r['nome'], 'classe': r.get('classe', ''),
                        'de': None, 'para': mx_alvo, 'novo': True})
        elif mx_antes is not None and mx_alvo > mx_antes:
            out.append({'nome': r['nome'], 'classe': r.get('classe', ''),
                        'de': mx_antes, 'para': mx_alvo, 'novo': False})
    return out


def _levelup_aplicar_lote(personagem, acoes):
    """Aplica, EM SEQUÊNCIA e na ordem estável de `_LVL_ORDEM`, o lote de ações
    [{tipo, payload}, …]. Acumula e devolve a lista de erros; NÃO abre transação nem
    ressincroniza (responsabilidade do endpoint). Ordem preservada entre ações do mesmo
    tipo (sort estável)."""
    erros = []
    ordenadas = sorted((a for a in acoes if isinstance(a, dict)),
                       key=lambda a: _LVL_ORDEM.get(a.get('tipo'), 99))
    for acao in ordenadas:
        fn = _LVL_ACTIONS.get(acao.get('tipo'))
        if not fn:
            erros.append('Ação de level-up desconhecida: %r' % acao.get('tipo'))
            continue
        erros += fn(personagem, acao.get('payload') or {})
    return erros


def _levelup_acoes_do_body(request):
    """Extrai a lista de ações do corpo JSON — aceita `{"acoes": [...]}` ou um array puro."""
    body = _json_body(request)
    if isinstance(body, list):
        return body
    return (body.get('acoes') if isinstance(body, dict) else None) or []


def _levelup_classe_id_acoes(acoes):
    """Extrai a classe ancora do lote para recalcular as mesmas pendencias."""
    for tipo in ('subir_nivel', 'adicionar_classe'):
        for acao in acoes:
            if isinstance(acao, dict) and acao.get('tipo') == tipo:
                payload = acao.get('payload') or {}
                if payload.get('classe'):
                    return payload['classe']
    return None


@login_required(login_url='/login/')
@require_POST
def personagem_levelup_aplicar(request, pk):
    """Aplica um LOTE de escolhas de level-up numa ÚNICA transação (padrão
    `criar_personagem_view`). Corpo: `{"acoes": [{"tipo": <str>, "payload": {…}}, …]}`.
    Se qualquer ação falhar, reverte tudo e devolve 400 com a lista de erros. No sucesso,
    ressincroniza magias/vitais UMA vez e devolve `{ok, ficha, pendencias}`."""
    from .character_engine import derive
    p = _ficha_editavel(request, pk)
    acoes = _levelup_acoes_do_body(request)
    classe_id = _levelup_classe_id_acoes(acoes)
    with transaction.atomic():
        erros = _levelup_aplicar_lote(p, acoes)
        if erros:
            transaction.set_rollback(True)
        else:
            # ordem idêntica aos wrappers legados: materializa concedidas, depois vitais.
            _sync_magias_concedidas(p)
            _refresh_vitais_derivados(p)
    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)
    ficha = derive(p)
    pendencias = _levelup_pendencias(p, classe_id)
    status = _levelup_status(p, ficha)
    # O próximo GET reabre o wizard já no novo estado: ele inclui tanto eventuais
    # escolhas recém-liberadas quanto a âncora do nível seguinte. Não exigir
    # ``sem_pendencias`` aqui, senão justamente essas escolhas quebram o encadeamento.
    continuar = bool(status['pode_subir'])
    return JsonResponse({
        'ok': True,
        'ficha': _criador_preview_resumo(ficha),
        'pendencias': pendencias,
        'continuar': continuar,
        'proximo_nivel': status['nivel_alvo'] if continuar else None,
    })


@login_required(login_url='/login/')
@require_POST
def personagem_levelup_preview(request, pk):
    """Prévia AO VIVO do lote de level-up: aplica tudo numa transação REVERTIDA (padrão
    `criar_personagem_preview_view`) e devolve o derive previsto + as pendências restantes,
    SEM persistir nada. Ações inválidas não gravam, apenas aparecem em `erros` (a prévia
    reflete o subconjunto válido, como no criador)."""
    p = _ficha_editavel(request, pk)
    acoes = _levelup_acoes_do_body(request)
    classe_id = _levelup_classe_id_acoes(acoes)
    preview = pend = None
    erros = []
    try:
        with transaction.atomic():
            erros = _levelup_aplicar_lote(p, acoes)
            _sync_magias_concedidas(p)
            ficha = _refresh_vitais_derivados(p)
            preview = _criador_preview_resumo(ficha)
            pend = _levelup_pendencias(p, classe_id)
            transaction.set_rollback(True)
    except Exception:
        return JsonResponse({'ok': True, 'ready': False, 'erros': erros})
    return JsonResponse({'ok': True, 'ready': True, 'preview': preview,
                         'pendencias': pend, 'erros': erros})


def _compra_resposta(request, pk, p, msg, ok):
    """Resposta de compra: JSON (quando fetch/XHR) ou redirect PRG clássico (no-JS).

    No caso AJAX bem-sucedido devolve carteira + inventário re-renderizado para a loja da
    ficha atualizar a página sem reload. O partial de inventário é o MESMO usado no template."""
    if is_ajax(request):
        if not ok:
            return JsonResponse({'ok': False, 'msg': msg})
        return JsonResponse(_inventario_ajax_payload(request, p, msg=msg))
    return redirect(reverse('editar_ficha', args=[pk]) + '?compra=' + msg)


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
        return _compra_resposta(request, pk, p, 'invalido', False)
    total = custo_unit * qtd
    if total > (p.carteira_pc or 0):
        return _compra_resposta(request, pk, p, 'saldo', False)
    with transaction.atomic():
        p.carteira_pc = (p.carteira_pc or 0) - total
        p.save(update_fields=['carteira_pc', 'atualizado_em'])
        _mec = mecanica_de_tags(item.tags_json, item.subcategoria)
        existente = TbPersonagemItem.objects.filter(id_personagem=p, nome=item.nome, equipado=False).first()
        if existente and not _mec['tipo_equip']:
            existente.qtd = (existente.qtd or 0) + qtd
            existente.save(update_fields=['qtd'])
        else:
            TbPersonagemItem.objects.create(id_personagem=p, qtd=qtd, nome=item.nome, custo=item.preco,
                tags_json=list(item.tags_json or []))
        _registrar_transacao(p, 'compra', 'Compra: %s x%d' % (item.nome, qtd), -total)
    return _compra_resposta(request, pk, p, 'ok', True)


@login_required(login_url='/login/')
@require_POST
def personagem_equipar_item(request, pk):
    """Equipa/desequipa um item. Item possuído mas não equipado NÃO concede benefícios.
    Só 1 armadura e 1 escudo equipados por vez."""
    from .character_engine import _item_magico_equipavel
    from .models import TbPersonagemItem
    p = _ficha_editavel(request, pk)
    it = TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p).first()
    if not it:
        return _inventario_mutacao_resposta(
            request, p, reverse('editar_ficha', args=[pk]), msg='item_invalido', ok=False)
    if it.id_item_magico and not _item_magico_equipavel(it.id_item_magico):
        # Compatibilidade graciosa: uma flag antiga inválida deixa de surtir efeito e
        # pode ser limpa sem remover a linha do inventário.
        if it.equipado:
            it.equipado = False
            it.save(update_fields=['equipado'])
        return _inventario_mutacao_resposta(
            request, p, reverse('editar_ficha', args=[pk]), msg='nao_equipavel', ok=False)
    novo = not it.equipado
    _mec = mecanica_de_tags(it.tags_json)
    if novo and _mec['tipo_equip']:  # equipar: tira o que ocupa o mesmo "slot"
        alvo_escudo = _mec['is_escudo']
        for outro in TbPersonagemItem.objects.filter(id_personagem=p, equipado=True):
            om = mecanica_de_tags(outro.tags_json)
            if (alvo_escudo and om['is_escudo']) or (not alvo_escudo and om['is_armadura']):
                outro.equipado = False
                outro.save(update_fields=['equipado'])
    it.equipado = novo
    it.save(update_fields=['equipado'])
    return _inventario_mutacao_resposta(
        request, p, reverse('editar_ficha', args=[pk]),
        msg='equipado' if novo else 'desequipado')


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
    from .character_engine import _item_consumivel_meta
    p = _ficha_editavel(request, pk)
    item = TbItemMagico.objects.filter(slug=request.POST.get('item')).first()
    # Preço nulo OU <= 0 = item não-comercializável (recompensa de missão). Bloqueia a compra
    # mesmo por POST direto (a loja também deixa de listá-lo — ver editar_ficha_view).
    if not item or not item.preco or float(item.preco) <= 0:
        return _compra_resposta(request, pk, p, 'invalido', False)
    custo_pc = int(round(float(item.preco) * 100))  # preço em PO -> PC
    if custo_pc > (p.carteira_pc or 0):
        return _compra_resposta(request, pk, p, 'saldo', False)
    with transaction.atomic():
        p.carteira_pc = (p.carteira_pc or 0) - custo_pc
        p.save(update_fields=['carteira_pc', 'atualizado_em'])
        # Consumíveis idênticos (poção/pergaminho) empilham numa só linha (qtd += 1) em vez de
        # virar N linhas qtd=1. Itens equipáveis/sintonizáveis continuam 1 linha por unidade.
        consumivel = _item_consumivel_meta(None, item)['consumivel']
        existente = (TbPersonagemItem.objects.filter(
            id_personagem=p, id_item_magico=item, equipado=False, sintonizado=False).first()
            if consumivel else None)
        if existente:
            existente.qtd = (existente.qtd or 0) + 1
            existente.save(update_fields=['qtd'])
        else:
            TbPersonagemItem.objects.create(
                id_personagem=p, qtd=1, nome=item.nome, custo=('%g PO' % float(item.preco)),
                id_item_magico=item, equipado=False, sintonizado=False)
        _registrar_transacao(p, 'compra', 'Compra mágica: %s' % item.nome, -custo_pc)
    return _compra_resposta(request, pk, p, 'ok', True)


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
        return _inventario_mutacao_resposta(
            request, p, reverse('editar_ficha', args=[pk]), msg='item_invalido', ok=False)
    if not it.sintonizado:
        usados = TbPersonagemItem.objects.filter(id_personagem=p, sintonizado=True).count()
        if usados >= 3:
            return _inventario_mutacao_resposta(
                request, p, reverse('editar_ficha', args=[pk]) + '?sint=limite',
                msg='limite_sintonizacao', ok=False)
        it.sintonizado = True
        if not it.equipado:          # sintonizar implica portar o item
            it.equipado = True
        it.save(update_fields=['sintonizado', 'equipado'])
    else:
        it.sintonizado = False
        it.save(update_fields=['sintonizado'])
    return _inventario_mutacao_resposta(
        request, p, reverse('editar_ficha', args=[pk]),
        msg='sintonizado' if it.sintonizado else 'dessintonizado')


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
def _redirect_next_or(request, fallback_url):
    nxt = (request.POST.get('next') or '').strip()
    if nxt.startswith('/') and not nxt.startswith('//'):
        return redirect(nxt)
    return redirect(fallback_url)


def _recursos_ajax_payload(p):
    """Snapshot dos recursos recuperáveis exibidos no editor da ficha."""
    from .character_engine import _recursos_consumiveis

    classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
    return [
        {
            'slug': r['slug'],
            'atual': int(r.get('atual') or 0),
            'maximo': int(r.get('maximo') or 0),
        }
        for r in _recursos_consumiveis(p, classes)
    ]


@login_required(login_url='/login/')
@require_POST
def personagem_usar_recurso(request, pk):
    """Gasta (−1) ou desfaz (+1) um uso de um recurso consumível do personagem."""
    from .character_engine import _recursos_consumiveis, derive
    from .models import TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
    cons = {r['slug']: r for r in _recursos_consumiveis(p, classes)}
    for r_tag in _consumiveis_ficha_cards(p, derive(p)):
        if r_tag.get('db_nome'):
            cons[r_tag['id']] = r_tag
    r = cons.get(request.POST.get('recurso'))
    if not r:
        if is_ajax(request):
            return JsonResponse({'ok': False, 'msg': 'recurso_invalido'}, status=400)
        return _redirect_next_or(request, reverse('editar_ficha', args=[pk]))
    delta = 1 if request.POST.get('acao') == 'desfazer' else -1
    novo = max(0, min(r['maximo'], r['atual'] + delta))
    pr, _ = TbPersonagemRecurso.objects.get_or_create(
        id_personagem=p, nome=r.get('db_nome') or r['nome'],
        defaults={'maximo': r['maximo'], 'atual': r['maximo']})
    pr.atual, pr.maximo = novo, r['maximo']
    pr.save(update_fields=['atual', 'maximo'])
    if is_ajax(request):
        return JsonResponse({
            'ok': True,
            'recursos': _recursos_ajax_payload(p),
        })
    return _redirect_next_or(request, reverse('editar_ficha', args=[pk]))


@login_required(login_url='/login/')
@require_POST
def personagem_usar_item_consumivel(request, pk):
    """Gasta (-1) ou devolve (+1) a quantidade de um item consumivel do inventario."""
    from .character_engine import _item_consumivel_meta
    from .models import TbPersonagemItem
    p = _ficha_editavel(request, pk)
    it = (TbPersonagemItem.objects.filter(id=request.POST.get('item'), id_personagem=p)
          .select_related('id_item_magico').first())
    if not it or not _item_consumivel_meta(it, it.id_item_magico)['consumivel']:
        return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=ficha')
    delta = 1 if request.POST.get('acao') == 'desfazer' else -1
    nova_qtd = max(0, min(999, int(it.qtd or 0) + delta))
    if nova_qtd == 0:
        it.delete()
    else:
        it.qtd = nova_qtd
        it.save(update_fields=['qtd'])
    return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=ficha')


@login_required(login_url='/login/')
@require_POST
def personagem_usar_slot_magia(request, pk):
    """Gasta (-1) ou devolve (+1) um slot de magia rastreado na aba Magias."""
    from .character_engine import derive
    from .models import TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    try:
        nivel = int(request.POST.get('nivel') or 0)
    except (TypeError, ValueError):
        nivel = 0
    if nivel < 1 or nivel > 9:
        return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')
    info = _magias_sheet_info(p, derive(p), [])
    slot = next((s for s in info.get('slots', []) if s['nivel'] == nivel), None)
    total = int((slot or {}).get('total') or 0)
    if total <= 0:
        return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')
    key = 'spell-slot:%d' % nivel
    pr, _ = TbPersonagemRecurso.objects.get_or_create(
        id_personagem=p, nome=key, defaults={'maximo': total, 'atual': total})
    atual_base = min(int(pr.atual or 0), total)
    delta = 1 if request.POST.get('acao') == 'desfazer' else -1
    pr.atual = max(0, min(total, atual_base + delta))
    pr.maximo = total
    pr.save(update_fields=['atual', 'maximo'])
    return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')


@login_required(login_url='/login/')
@require_POST
def personagem_usar_magia_inata(request, pk, magia_id):
    """Gasta (-1) ou devolve (+1) o uso oculto de uma magia inata/concedida."""
    from .character_engine import derive
    from .models import TbPersonagemMagia, TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    m = get_object_or_404(TbPersonagemMagia, pk=magia_id, id_personagem=p)
    if not m.sempre_preparada:
        return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')
    info = _magias_sheet_info(p, derive(p), [])
    row = next((x for x in info.get('lista', []) if x.get('id') == m.id), None)
    key = (row or {}).get('innate_key') or ''
    total = int((row or {}).get('innate_max') or 0)
    if not key or total <= 0:
        return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')
    pr, _ = TbPersonagemRecurso.objects.get_or_create(
        id_personagem=p, nome=key, defaults={'maximo': total, 'atual': total})
    atual_base = min(int(pr.atual or 0), total)
    delta = 1 if request.POST.get('acao') == 'desfazer' else -1
    pr.atual = max(0, min(total, atual_base + delta))
    pr.maximo = total
    pr.save(update_fields=['atual', 'maximo'])
    return _redirect_next_or(request, reverse('ficha_detail', args=[pk]) + '?aba=magias')


@login_required(login_url='/login/')
@require_POST
def personagem_descansar(request, pk):
    """Descanso: recupera recursos conforme o reset declarado no recurso."""
    from .character_engine import _recursos_consumiveis, derive
    from .models import TbPersonagemRecurso
    p = _ficha_editavel(request, pk)
    longo = request.POST.get('tipo') == 'longo'
    classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
    ficha = derive(p)
    for r in _recursos_consumiveis(p, classes):
        reset = r.get('reset') or ''
        if _resource_resets_on_rest(reset, longo):
            pr, _ = TbPersonagemRecurso.objects.get_or_create(
                id_personagem=p, nome=r['nome'], defaults={'maximo': r['maximo'], 'atual': r['maximo']})
            pr.atual, pr.maximo = r['maximo'], r['maximo']
            pr.save(update_fields=['atual', 'maximo'])
    for r in _consumiveis_ficha_cards(p, ficha):
        if not r.get('db_nome') or not _resource_resets_on_rest(r.get('reset'), longo):
            continue
        pr, _ = TbPersonagemRecurso.objects.get_or_create(
            id_personagem=p, nome=r['db_nome'], defaults={'maximo': r['maximo'], 'atual': r['maximo']})
        pr.atual, pr.maximo = r['maximo'], r['maximo']
        pr.save(update_fields=['atual', 'maximo'])
    magias_info = _magias_sheet_info(p, ficha, [])
    if longo:
        for s in magias_info.get('slots', []):
            total = int(s.get('total') or 0)
            if total <= 0:
                continue
            pr, _ = TbPersonagemRecurso.objects.get_or_create(
                id_personagem=p, nome=s['key'], defaults={'maximo': total, 'atual': total})
            pr.atual, pr.maximo = total, total
            pr.save(update_fields=['atual', 'maximo'])
    for m in magias_info.get('lista', []):
        key = m.get('innate_key') or ''
        total = int(m.get('innate_max') or 0)
        if not key or total <= 0 or not _resource_resets_on_rest(m.get('innate_reset'), longo):
            continue
        pr, _ = TbPersonagemRecurso.objects.get_or_create(
            id_personagem=p, nome=key, defaults={'maximo': total, 'atual': total})
        pr.atual, pr.maximo = total, total
        pr.save(update_fields=['atual', 'maximo'])
    if is_ajax(request):
        return JsonResponse({
            'ok': True,
            'descanso': 'longo' if longo else 'curto',
            'recursos': _recursos_ajax_payload(p),
        })
    return _redirect_next_or(request, reverse('editar_ficha', args=[pk]) + ('?rest=longo' if longo else '?rest=curto'))


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
    _vert_disp = _vert.replace('-', ' ').title()
    if _vert and p.id_essencia_id:
        # essência com clã/herança (Vampirismo): o nome bonito vem do catálogo de clãs;
        # essência elemental: varre 'Vertente X' nos traços. Um OU outro, nunca ambos.
        from .character_engine import clas_de_essencia
        _cla_nome = next((c['nome'] for c in clas_de_essencia(p.id_essencia) if c['slug'] == _vert), None)
        if _cla_nome:
            _vert_disp = _cla_nome
        else:
            from .models import TbTracoracial
            for tr in TbTracoracial.objects.filter(id_essencia=p.id_essencia):
                txt = '%s\n%s' % (tr.pre_requisito or '', tr.descricao or '')
                nomes = [m.group(1).strip() for m in re.finditer(r'Vertente\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ-]+)', txt)]
                if 'vertente' in txt.lower():
                    nomes += [m.group(1).strip() for m in re.finditer(r'^\s*[-*]\s*\*\*([A-Za-zÀ-ÿ-]+)\b', txt, re.M)]
                achado = next((n for n in nomes if slugify(n) == _vert), None)
                if achado:
                    _vert_disp = achado
                    break
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
    from .models import TbTransacao, TbMagia
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
    magias_info = _magias_sheet_info(p, ficha, essencia_pendentes)
    consumiveis_cards = _consumiveis_ficha_cards(p, ficha)
    # Página de Histórico: compras/vendas do personagem.
    transacoes = list(TbTransacao.objects.filter(id_personagem=p).order_by('-pk')[:300])
    pode_editar = p.dono_id == request.user.id or perms.is_staff_user(request.user)
    # Botão de level-up: só quem edita, e só quando elegível (ou com pendências abertas).
    levelup_status = _levelup_status(p, ficha) if pode_editar else None
    return render(request, 'home/pages/ficha_detail.html', {
        'page_title': p.nome,
        'p': p,
        'ficha': ficha,
        'raca_linha': raca_linha,
        'magias_info': magias_info,
        'consumiveis_cards': consumiveis_cards,
        'transacoes': transacoes,
        'pode_editar': pode_editar,
        'levelup_status': levelup_status,
        'appearance': _appearance_context(p.ficha_theme, p.foto_frame, p.ficha_effect,
                                          p.ficha_theme_custom, p.ficha_background_url),
        'appearance_themes': _appearance_catalog('theme'),
        'appearance_frames': _appearance_catalog('frame'),
        'appearance_effects': _appearance_catalog('effect'),
    })


@login_required(login_url='/login/')
def personagem_trocar_maestria(request, pk):
    """Painel de Maestria de Arma em DOIS NÍVEIS: por slot, a ARMA e UMA maestria DELA. Fica
    acessível quando a feature é TROCÁVEL (tag `trocavel` — pode trocar a arma) OU quando há
    maestria PENDENTE a completar (escolhas legadas só-arma). Nº de slots = quantas maestrias o
    personagem já tem. Persiste `'<arma>|<maestria>'` (1 linha por slot, tipo='maestria')."""
    from .models import TbPersonagem, TbPersonagemEscolha
    from . import permissions as perms
    from .character_engine import derive
    from . import picks as _picks
    p = get_object_or_404(TbPersonagem, pk=pk)
    if not (p.dono_id == request.user.id or perms.is_staff_user(request.user)):
        raise Http404()
    atuais = list(p.escolhas.filter(tipo='maestria').order_by('slot'))
    n_slots = len(atuais)
    ficha = derive(p)
    trocavel = bool(ficha.get('maestria_trocavel'))
    pendente = bool(ficha.get('maestria_pendente'))
    # sem slots, e sem poder trocar arma nem completar maestria pendente -> nada a fazer aqui.
    if n_slots == 0 or not (trocavel or pendente):
        return redirect(reverse('ficha_detail', args=[pk]))
    universo = _picks._arma_universe({})
    by_slug = {u['slug']: u for u in universo}
    erro = None
    if request.method == 'POST':
        pares = [((request.POST.get('arma_%d' % i) or '').strip(),
                  (request.POST.get('maestria_%d' % i) or '').strip()) for i in range(n_slots)]
        # sem `trocavel`, as ARMAS ficam travadas nas atuais (só a maestria é completada).
        if not trocavel:
            atuais_armas = [_picks.split_arma_maestria(e.valor)[0] for e in atuais]
            pares = [(atuais_armas[i], m) for i, (_a, m) in enumerate(pares)]
        # A duplicata proibida é o PAR (arma, maestria) — a MESMA ARMA pode repetir entre
        # slots para aprender uma 2ª maestria dela (regra confirmada pela staff). Uma arma
        # SEM maestrias cadastradas não tem par distinto, então aí a própria arma não repete.
        valores, vistos, ok = [], set(), True
        for arma, maestria in pares:
            u = by_slug.get(arma)
            if not u:
                ok = False
                break
            ms = {m['slug'] for m in (u.get('maestrias') or [])}
            if ms:
                par = (arma, maestria)
                if maestria not in ms or par in vistos:
                    ok = False
                    break
                vistos.add(par)
                valores.append('%s|%s' % (arma, maestria))
            else:
                if (arma, None) in vistos:
                    ok = False
                    break
                vistos.add((arma, None))
                valores.append(arma)
        if ok and len(valores) == n_slots:
            p.escolhas.filter(tipo='maestria').delete()
            for i, val in enumerate(valores):
                TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', valor=val, slot=i)
            return redirect(reverse('ficha_detail', args=[pk]))
        erro = ('Escolha exatamente %d arma(s), cada uma com a sua maestria (a mesma arma pode '
                'repetir com maestrias diferentes; não repita o mesmo par arma+maestria).' % n_slots)
    slots = []
    for i, e in enumerate(atuais):
        a, m = _picks.split_arma_maestria(e.valor)
        u = by_slug.get(a)
        slots.append({'idx': i, 'arma': a, 'arma_nome': (u['nome'] if u else a),
                      'maestria': m, 'maestrias': (u['maestrias'] if u else [])})
    return render(request, 'home/pages/trocar_maestria.html', {
        'page_title': 'Maestrias de Arma — %s' % p.nome,
        'p': p, 'armas': universo, 'n_slots': n_slots,
        'slots': slots, 'trocavel': trocavel, 'erro': erro,
    })


@login_required(login_url='/login/')
@require_POST
def personagem_toggle_magia(request, pk, magia_id):
    """Marca/desmarca uma magia como PREPARADA (clicável na aba Magias da ficha).
    Magias `sempre_preparada` (raça/outros) não são alternáveis."""
    from .character_engine import derive
    from .models import TbPersonagemMagia
    p = _ficha_editavel(request, pk)
    m = get_object_or_404(TbPersonagemMagia, pk=magia_id, id_personagem=p)
    url = reverse('ficha_detail', args=[pk]) + '?aba=magias'
    if m.sempre_preparada:
        return redirect(url)
    if m.preparada:
        m.preparada = False
        m.save(update_fields=['preparada'])
        return redirect(url)

    ficha = derive(p)
    info = _magias_preparadas_info(p, ficha)
    if info and int(m.nivel or 0) >= 1:
        validos = {x['slug'] for g in info.get('grupos', []) for x in g.get('magias', [])}
        slug = getattr(m.id_magia, 'slug', '') or slugify(m.nome or '')
        if slug not in validos:
            return redirect(url + '&prep=invalida')
        limite = info.get('limite')
        atuais = p.magias.filter(nivel__gte=1, preparada=True, sempre_preparada=False).exclude(pk=m.pk).count()
        if limite is not None and atuais >= int(limite):
            return redirect(url + '&prep=limite')
    m.preparada = True
    m.save(update_fields=['preparada'])
    return redirect(url)


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
              'pele', 'aparencia', 'historia', 'anotacoes', 'foto_url', 'token_url',
              'banner_url', 'ficha_background_url']
    for c in campos:
        if c in request.POST:
            setattr(p, c, (request.POST.get(c) or '').strip()[:5000] or None)
    # Upload real de imagens do personagem — precedência sobre a URL. Kinds:
    # foto/token (8MB) e banner/background (12MB), em media/character_uploads/pers_<pk>/.
    upload_kinds = [
        ('foto_file', 'foto', 'foto_url', 8),
        ('token_file', 'token', 'token_url', 8),
        ('banner_file', 'banner', 'banner_url', 12),
        ('background_file', 'background', 'ficha_background_url', 12),
    ]
    try:
        for field_name, kind, attr, max_mb in upload_kinds:
            up = request.FILES.get(field_name)
            if up:
                url = _save_character_upload(p, up, kind, getattr(p, attr) or '', max_mb=max_mb)
                setattr(p, attr, url or None)
    except ValueError:
        # Arquivo inválido/grande: ignora o upload, mantém o que já havia (não quebra o save).
        pass
    dono = p.dono  # a carteira de cosméticos é do dono do personagem (escopo=ficha)
    p.ficha_theme = _appearance_validated(dono, 'theme', request.POST.get('ficha_theme'), 'ficha')
    p.ficha_theme_custom = _custom_theme_from_post(request)
    foto_frame = _appearance_validated(dono, 'frame', request.POST.get('foto_frame'), 'ficha')
    ficha_effect = _appearance_validated(dono, 'effect', request.POST.get('ficha_effect'), 'ficha')
    p.foto_frame = None if foto_frame == 'none' else foto_frame
    p.ficha_effect = None if ficha_effect == 'none' else ficha_effect
    campos += ['ficha_theme', 'ficha_theme_custom', 'foto_frame', 'ficha_effect']
    p.save(update_fields=campos)
    if is_ajax(request):
        return JsonResponse({
            'ok': True,
            'msg': 'informacoes_salvas',
            'imagens': {
                'foto_url': p.foto_url or '',
                'token_url': p.token_url or '',
                'banner_url': p.banner_url or '',
                'background_url': p.ficha_background_url or '',
            },
        })
    return redirect(reverse('ficha_detail', args=[pk]) + '?aba=info')


def _criador_incoming_picks(data):
    """Normaliza as escolhas genéricas recebidas do criador para {(kind, tipo_norm): [valores]}.

    Aceita o formato novo `picks:[{kind,tipo,valores}]` (o que o editar-ficha já usa) E faz
    a PONTE dos campos legados (`maestrias`, `estilo_luta`) para o mesmo formato — assim os
    caminhos dedicados de Maestria/Estilo são substituídos pelo genérico sem quebrar clientes
    (ou testes) que ainda mandam os campos antigos."""
    from . import picks as _picks
    out = {}
    for pk in (data.get('picks') or []):
        if not isinstance(pk, dict):
            continue
        tipo = pk.get('tipo')
        key = (pk.get('kind'), _picks.normalize_slug(tipo) if tipo else None)
        out.setdefault(key, [])
        out[key] += list(pk.get('valores') or [])
    # ponte dos campos legados (só se o cliente não mandou o pick genérico correspondente)
    if data.get('maestrias') and ('arma', None) not in out:
        out[('arma', None)] = list(data.get('maestrias') or [])
    if data.get('estilo_luta'):
        k = ('opcao', _picks.normalize_slug('estilo_de_luta'))
        if k not in out:
            out[k] = [data.get('estilo_luta')]
    return out


def _criador_resolver(data):
    """Resolve e valida o payload do criador SEM persistir. Retorna (R, erros): R traz
    todos os objetos/valores já resolvidos para persistir; erros é a lista de pendências.
    Compartilhado por criar_personagem_view (que exige erros==[]) e pelo preview ao vivo
    (que ignora pendências de contagem e monta o subconjunto válido)."""
    from .models import (TbItemMundano, TbOpcaojogo, TbTracoracial,
                         TbRaca, TbLinhagem, TbEssencia, TbClasse, TbAntecedente, TbTalento)
    from .character_engine import (_SKILL_INFO, _norm_skill_slug,
                                    background_asi_values, background_grants, ASI_SHAPES)
    from . import point_buy

    erros = []
    SIG = point_buy.SIGLAS

    nome = (data.get('nome') or '').strip()
    if not nome:
        erros.append('Dê um nome ao personagem.')
    elif len(nome) > 150:
        # o campo do banco tem 150 — validar explicitamente em vez de truncar em silêncio.
        erros.append('Nome muito longo (máximo de 150 caracteres).')

    scores = data.get('scores') or {}
    # Exige os seis atributos: sem isso um POST incompleto criaria a ficha com 8 em
    # silêncio no atributo faltante (o JS deveria mandar todos).
    if any(s not in scores for s in SIG):
        erros.append('Distribua os seis atributos (point-buy incompleto).')
    base = {s: int(scores.get(s, 8) or 8) for s in SIG}
    _, e = point_buy.validar([base[s] for s in SIG]); erros += e
    asi = data.get('asi') or {}
    # ASI do antecedente em DUAS formas (regra de sistema): a nova {modo, attrs} e a legada
    # {mais2, mais1} (= forma '2/1'). O front pode mandar qualquer uma; o resolver normaliza.
    if asi.get('attrs') is not None or asi.get('modo'):
        asi_modo = asi.get('modo') or '2/1'
        asi_attrs = [str(a) for a in (asi.get('attrs') or []) if a]
    else:
        asi_modo = '2/1'
        asi_attrs = [a for a in (asi.get('mais2'), asi.get('mais1')) if a]
    _, e2 = point_buy.validar_asi(asi_modo, asi_attrs); erros += e2
    # pares (atributo, +valor): 2 no '2/1', 3 no '1/1/1'. O derive soma Σ TbPersonagemAtributoBonus.
    asi_shape = ASI_SHAPES.get(asi_modo) or []
    asi_bonus = list(zip(asi_attrs, asi_shape)) if len(asi_attrs) == len(asi_shape) else []
    # compat: mais2/mais1 alimentam _spell_count_nv1 (fórmula usa asi_bonus quando presente).
    mais2 = asi_attrs[0] if asi_attrs else None
    mais1 = asi_attrs[1] if len(asi_attrs) > 1 else None

    raca = TbRaca.objects.filter(slug=data.get('raca')).first()
    classe = TbClasse.objects.filter(slug=data.get('classe')).first()
    antec = TbAntecedente.objects.filter(slug=data.get('antecedente')).first()
    if not raca:
        erros.append('Escolha uma raça.')
    if not classe:
        erros.append('Escolha uma classe.')
    if not antec:
        erros.append('Escolha um antecedente.')
    bg_grants = background_grants(antec) if antec else background_grants()
    asi_major, asi_minor = background_asi_values(bg_grants)
    bg_skill_n = int(bg_grants.get('pericias') or 0)
    bg_langtool_n = int(bg_grants.get('idiomas_ou_ferramentas') or 0)

    # Talento de Origem: TODO antecedente concede 1 (talento_origem:1). É obrigatório —
    # antes o server só criava `if data.get('talento_origem')`, deixando a ficha nascer
    # sem o feat garantido pelo antecedente, em silêncio.
    to = None
    if antec and int(bg_grants.get('talento_origem') or 0) >= 1:
        to = TbTalento.objects.filter(
            id_talento=data.get('talento_origem'), tipo__iexact='origem').first()
        if not to:
            erros.append('Escolha o Talento de Origem concedido pelo antecedente.')

    # Cross-field raça×essência: só aceita essência se a raça a permitir.
    if data.get('essencia') and raca and not raca.permite_essencia:
        erros.append('Esta raça não permite escolher uma essência.')
    # Cross-field raça×linhagem: linhagem informada tem de pertencer à raça (antes era
    # descartada em silêncio quando não casava).
    if data.get('linhagem') and raca and not TbLinhagem.objects.filter(
            slug=data.get('linhagem'), id_raca=raca).exists():
        erros.append('A linhagem escolhida não pertence a esta raça.')

    # Escolhas genéricas via pick:* (kinds `arma` + `opcao`) — FONTE ÚNICA (home.picks).
    # Substitui os caminhos DEDICADOS de Maestria de Arma e Estilo de Luta: o resolvedor
    # descobre os grupos a partir das tags da classe/habilidades N1, valida contagem +
    # pertinência pelo REGISTRY, e o MESMO mecanismo cobre qualquer `pick:opcao:<tipo>:N`
    # novo (inclusive tipos sintéticos) sem tocar no código.
    from . import picks as _picks
    generic_groups = _picks.resolve_builder(classe, kinds={'arma', 'opcao'}) if classe else []
    incoming = _criador_incoming_picks(data)
    generic_picks = []
    for g in generic_groups:
        key = (g['kind'], _picks.normalize_slug(g['tipo']) if g['tipo'] else None)
        universo_slugs = {str(u.get('slug')) for u in g['universo']}
        universo_ids = {str(u.get('id')) for u in g['universo'] if u.get('id') is not None}
        # o pré-filtro descarta lixo antes do validate; a Maestria de Arma manda o valor
        # combinado `'<arma>|<maestria>'`, então casa a membresia pela PARTE-ARMA (antes do `|`).
        # A checagem da maestria (pertence à arma) e a contagem ficam no validate do REGISTRY.
        vals = [v for v in dict.fromkeys(incoming.get(key) or [])
                if str(v) in universo_slugs or str(v) in universo_ids
                or str(v).split('|', 1)[0] in universo_slugs]
        erros += _picks.registry_entry(g['kind'])['validate'](g, vals)
        generic_picks.append((g, vals))

    # Perícias: validar quantidade e pertinência no SERVIDOR (não confiar só no cliente).
    # Normaliza o slug ('_'→'-') para casar _SKILL_INFO mesmo se o cliente enviar cru.
    pc = list(dict.fromkeys(_norm_skill_slug(s) for s in (data.get('pericias_classe') or [])))
    pa = list(dict.fromkeys(_norm_skill_slug(s) for s in (data.get('pericias_antecedente') or [])))
    lt_sel = list(dict.fromkeys(data.get('idiomas_ferramentas') or []))
    if classe:
        pn, plista = _parse_skills_lvl1(classe.tags_json)
        pool = set(plista) if plista else set(_SKILL_INFO.keys())
        if len(pc) != pn or any(s not in pool for s in pc):
            erros.append('Escolha exatamente %d perícia(s) de classe válida(s).' % pn)
    if len(pa) != bg_skill_n or any(s not in _SKILL_INFO for s in pa):
        erros.append('Escolha exatamente %d perícia(s) de antecedente válida(s).' % bg_skill_n)
    # Bloqueio UNIVERSAL de perícia: a perícia do ANTECEDENTE não pode duplicar uma perícia
    # da classe — nem uma ESCOLHIDA (pc) nem uma GANHA fixa por feature de nível 1 (ex.:
    # Mago/Arcanismo via 'Estudo Arcano'). O cross-lock do cliente é só UI; um POST direto
    # (ou corrida de eventos) furaria e o servidor gravaria a proficiência em duplicidade.
    fixas_classe = _classe_pericias_fixas(classe) if classe else set()
    if set(pa) & (set(pc) | fixas_classe):
        erros.append('Perícia do antecedente duplicada com uma perícia da classe — escolha outra.')
    if len(lt_sel) != bg_langtool_n:
        erros.append('Escolha exatamente %d idioma(s)/ferramenta(s).' % bg_langtool_n)

    # Escolhas de classe nv1 remanescentes (não-migradas ainda): expertise (Ladino/Mago).
    # Estilo de Luta migrou para o resolvedor genérico (kind `opcao`, acima).
    esc1 = _classe_escolhas_nv1(classe) if classe else {'estilo_n': 0, 'expertise_n': 0, 'expertise_fixa': []}
    exp_sel = [s for s in dict.fromkeys(_norm_skill_slug(x) for x in (data.get('expertise') or []))
               if s in set(pc + pa)]
    if esc1['expertise_n'] and len(exp_sel) != esc1['expertise_n']:
        erros.append('Escolha %d perícia(s) para Especialização (entre as proficientes).' % esc1['expertise_n'])
    classe_prof_picks = _classe_prof_picks_nv1(classe) if classe else []
    classe_prof_sel = data.get('escolhas_classe_prof') or []
    if not isinstance(classe_prof_sel, list):
        classe_prof_sel = []
    classe_prof_validas = []
    for idx, pick in enumerate(classe_prof_picks):
        raw = classe_prof_sel[idx] if idx < len(classe_prof_sel) else {}
        vals = raw.get('valores') if isinstance(raw, dict) else []
        vals = list(dict.fromkeys(vals or []))
        allowed = _classe_prof_pick_options(pick['tipo'])
        vals = [v for v in vals if v in allowed]
        n_pick = int(pick.get('n') or 0)
        if len(vals) != n_pick:
            erros.append('Escolha %d proficiência(s) de classe em ferramenta/instrumento.' % n_pick)
        classe_prof_validas.append((pick, vals))

    # Conjuração nv1: truques + magias de 1º nível
    conj = _classe_conjuracao(classe) if classe else None
    truques_sel, magias_sel = [], []
    if conj:
        tslugs = {t['slug'] for t in conj['truques']}
        nslugs = {m['slug'] for m in conj['magias_nv1']}
        truques_sel = [s for s in dict.fromkeys(data.get('truques') or []) if s in tslugs]
        magias_sel = [s for s in dict.fromkeys(data.get('magias') or []) if s in nslugs]
        n_mag = _spell_count_nv1(conj, base, mais2, mais1, (asi_major, asi_minor), asi_bonus=asi_bonus)
        if conj['truques_n'] and len(truques_sel) != conj['truques_n']:
            erros.append('Escolha %d truque(s).' % conj['truques_n'])
        if len(magias_sel) != n_mag:
            erros.append('Escolha %d magia(s) de 1º nível.' % n_mag)

    linhagem = TbLinhagem.objects.filter(slug=data.get('linhagem'), id_raca=raca).first() if data.get('linhagem') else None
    essencia = TbEssencia.objects.filter(slug=data.get('essencia')).first() if (data.get('essencia') and raca and raca.permite_essencia) else None
    # Linhagem e Essência são MUTUAMENTE EXCLUSIVAS (regra do sistema: o personagem tem
    # uma OU outra, nunca as duas). O JS já desmarca uma ao escolher a outra, mas isso é
    # só UI — um POST direto (ou uma corrida de eventos) pode mandar as duas preenchidas,
    # e sem este guard o servidor persistiria as duas em silêncio.
    if linhagem and essencia:
        erros.append('Escolha linhagem ou essência — não os dois.')
    # Sub-escolha da essência (vertente elemental OU clã/herança do Vampirismo) é obrigatória
    # quando a essência a define, e o valor precisa ser uma opção real — senão a ficha nasceria
    # sem a herança (traços de clã não aplicam) ou com um clã inválido.
    if essencia:
        sub = _essencia_subescolha(essencia)
        opcoes_slugs = {o['slug'] for o in sub['opcoes']}
        if opcoes_slugs:
            if not data.get('vertente'):
                erros.append('Escolha %s da essência.' % sub['label'])
            elif data.get('vertente') not in opcoes_slugs:
                erros.append('%s inválido para esta essência.' % sub['label'])

    # Cross-lock de IDIOMA no SERVIDOR (espelha o de perícias e o bloqueio do criador.js):
    # um idioma já CONCEDIDO pela raça/traços — grant fixo `prof:idioma{X}` de um traço da
    # raça/linhagem/essência escolhidas OU pick racial de idioma da PRÓPRIA submissão
    # (escolhas_raca.idiomas) — NÃO pode ser re-escolhido na lista idioma/ferramenta do
    # antecedente: senão o jogador gastaria um slot do antecedente num idioma que já tem.
    # Antes isso só era barrado no cliente (applyLangToolRules), então um POST direto passava.
    idiomas_raciais = set()
    if raca:
        _prof_idioma_re = re.compile(r'(?<![a-z_-])prof:idioma\{([^}]+)\}')
        _menu_mk = ('define{', 'list{', 'table{', 'while_active', 'while{',
                    'cast{', 'instant{', 'trigger=', 'action=')
        trait_q = Q(id_raca=raca, id_linhagem__isnull=True, id_essencia__isnull=True)
        if linhagem:
            trait_q |= Q(id_linhagem=linhagem)
        if essencia:
            trait_q |= Q(id_essencia=essencia)
        for t in TbTracoracial.objects.filter(trait_q, talento_racial=False, nivel_requisito__lte=1):
            for tag in (t.tags_json or []):
                s = str(tag)
                if any(mk in s.lower() for mk in _menu_mk):
                    continue
                for m in _prof_idioma_re.finditer(s):
                    idiomas_raciais.add(m.group(1).strip())
    for nm in ((data.get('escolhas_raca') or {}).get('idiomas') or []):
        if isinstance(nm, str) and nm.strip():
            idiomas_raciais.add(nm.strip())
    dup_idiomas = sorted({x.strip() for x in lt_sel
                          if isinstance(x, str) and x.strip() in idiomas_raciais})
    if dup_idiomas:
        erros.append('Idioma(s) já concedido(s) pela raça/traços: %s. '
                     'Escolha outro(s) na lista do antecedente.' % ', '.join(dup_idiomas))

    R = {
        'nome': nome, 'base': base, 'mais2': mais2, 'mais1': mais1, 'asi_bonus': asi_bonus,
        'asi_major': asi_major, 'asi_minor': asi_minor, 'bg_grants': bg_grants,
        'raca': raca, 'linhagem': linhagem, 'essencia': essencia, 'antec': antec, 'classe': classe,
        'to': to, 'generic_picks': generic_picks, 'pc': pc, 'pa': pa,
        'lt_sel': lt_sel, 'bg_langtool_n': bg_langtool_n, 'esc1': esc1, 'exp_sel': exp_sel,
        'classe_prof_validas': classe_prof_validas, 'conj': conj,
        'truques_sel': truques_sel, 'magias_sel': magias_sel,
    }
    return R, erros


def _criador_persistir(user, data, R):
    """Cria o TbPersonagem + relacionados a partir de R (já resolvido por _criador_resolver).
    DEVE rodar dentro de transaction.atomic(). Retorna o personagem criado."""
    from .models import (TbPersonagem, TbPersonagemClasse, TbPersonagemPericia,
                         TbPersonagemProficiencia, TbPersonagemItem, TbPersonagemTalento,
                         TbPersonagemAtributoBonus, TbPersonagemEscolha, TbItemMundano, TbOpcaojogo,
                         TbPersonagemMagia, TbMagia)
    from .character_engine import _SKILL_INFO, _norm_skill_slug, _tracos_raciais
    from . import point_buy
    SIG = point_buy.SIGLAS
    nome = R['nome']; base = R['base']; mais2 = R['mais2']; mais1 = R['mais1']
    asi_major = R['asi_major']; asi_minor = R['asi_minor']; bg_grants = R['bg_grants']
    asi_bonus = R.get('asi_bonus') or []
    raca = R['raca']; linhagem = R['linhagem']; essencia = R['essencia']
    antec = R['antec']; classe = R['classe']; to = R['to']
    generic_picks = R['generic_picks']; pc = R['pc']; pa = R['pa']
    lt_sel = R['lt_sel']; bg_langtool_n = R['bg_langtool_n']; esc1 = R['esc1']
    exp_sel = R['exp_sel']; classe_prof_validas = R['classe_prof_validas']
    conj = R['conj']; truques_sel = R['truques_sel']; magias_sel = R['magias_sel']
    campo = {'FOR': 'forca', 'DES': 'destreza', 'CON': 'constituicao',
             'INT': 'inteligencia', 'SAB': 'sabedoria', 'CAR': 'carisma'}

    p = TbPersonagem.objects.create(
        dono=user, nome=nome[:150], nivel=1,
        id_raca=raca, id_linhagem=linhagem, id_essencia=essencia, id_antecedente=antec,
        **{campo[s]: base[s] for s in SIG})
    TbPersonagemClasse.objects.create(id_personagem=p, id_classe=classe, nivel=1, principal=True)
    # ASI do antecedente: uma linha por par (atributo, +valor) — 2 no '2/1', 3 no '1/1/1'.
    # O derive soma Σ TbPersonagemAtributoBonus sem supor quantidade fixa (nenhuma mudança lá).
    for atributo, valor in asi_bonus:
        TbPersonagemAtributoBonus.objects.create(id_personagem=p, atributo=atributo, valor=valor,
                                                 origem='Antecedente %s' % antec.nome, origem_tipo='antecedente')
    if essencia and data.get('vertente'):
        TbPersonagemEscolha.objects.create(id_personagem=p, origem='Essência %s' % essencia.nome,
                                           tipo='vertente', valor=data['vertente'])
    # Escolhas genéricas via pick:* (arma=Maestria, opcao=Estilo de Luta e quaisquer
    # pick:opcao:<tipo>:N do N1) — persistidas pelo REGISTRY (home.picks), FONTE ÚNICA.
    from . import picks as _picks
    for g, vals in generic_picks:
        _picks.registry_entry(g['kind'])['persist'](p, g, vals)
    for sl in set(pc + pa):
        info = _SKILL_INFO.get(sl)
        if info:
            TbPersonagemPericia.objects.get_or_create(
                id_personagem=p, nome=info[0], defaults={'atributo': info[1], 'proficiente': True})
    idioma_fixo = (bg_grants.get('idioma_fixo') or '').strip()
    if idioma_fixo:
        TbPersonagemProficiencia.objects.create(id_personagem=p, tipo='idioma', nome=idioma_fixo, origem='regra')
    ferr_nomes = set(TbItemMundano.objects.filter(categoria='ferramenta').values_list('nome', flat=True))
    for esc in lt_sel[:bg_langtool_n]:
        tipo = 'ferramenta' if esc in ferr_nomes else 'idioma'
        TbPersonagemProficiencia.objects.create(id_personagem=p, tipo=tipo, nome=esc, origem='antecedente')
    # Escolhas de RAÇA (perícias/idiomas/ferramentas extras da raça/linhagem/essência)
    esc_raca = data.get('escolhas_raca') or {}
    esc_per = [_norm_skill_slug(sl) for sl in (esc_raca.get('pericias') or [])
               if _SKILL_INFO.get(_norm_skill_slug(sl))]
    for sl in esc_per:
        info = _SKILL_INFO.get(sl)
        if info:
            TbPersonagemPericia.objects.get_or_create(
                id_personagem=p, nome=info[0], defaults={'atributo': info[1], 'proficiente': True})
    # Espelha os picks raciais de perícia como TbPersonagemEscolha(tipo='pericia') via o
    # REGISTRY — senão o traço-base (ex.: Humano 'Habilidoso' pick:pericia:2) reaparece como
    # pendência não-resolvida no level-up ("duas perícias extras"). origem = nome do traço,
    # casando o readback de resolve_personagem (_tracos_raciais → _build_group → origem=nome).
    # Reconstrói grupo por-fonte (não via resolve_groups global, que dedup-aria vários traços
    # pick:pericia num só grupo) e distribui a lista plana na ordem raça→linhagem→essência.
    if esc_per:
        _i = 0
        for _src in [obj for (_o, _f, obj, _cl) in _tracos_raciais(p)]:
            for _g in _picks.resolve_groups([_src], classe=None, subclasse=None, nivel=1,
                                            personagem=None, kinds={'pericia'}):
                _n = int(_g.get('n') or 0)
                _vals = esc_per[_i:_i + _n]
                _i += _n
                if _vals:
                    _picks.registry_entry('pericia')['persist'](p, _g, _vals)
    for nm in (esc_raca.get('idiomas') or []):
        TbPersonagemProficiencia.objects.get_or_create(
            id_personagem=p, tipo='idioma', nome=nm, defaults={'origem': 'racial'})
    for nm in (esc_raca.get('ferramentas') or []):
        TbPersonagemProficiencia.objects.get_or_create(
            id_personagem=p, tipo='ferramenta', nome=nm, defaults={'origem': 'racial'})
    # Dinheiro inicial vai para a carteira (PC) conforme as grants do antecedente.
    carteira = int(bg_grants.get('po_inicial') or 0) * 100
    equip_txt = (classe.equipamento or '').strip()
    ouro_alt = int(bg_grants.get('equip_gold_alt') or 0)
    if data.get('equip_classe') == 'inicial' and equip_txt:
        TbPersonagemItem.objects.create(id_personagem=p, qtd=1,
                                        nome='Equipamento inicial da classe: %s' % equip_txt[:170])
    else:
        carteira += ouro_alt * 100
        # BUG-2: 10/13 classes não têm kit cadastrado. Se o jogador escolheu
        # "equipamento inicial" e não há texto, a escolha vira ouro — antes isso
        # acontecia em silêncio (ficava parecendo que pegou itens). Registra o
        # ouro alternativo explicitamente no inventário para não enganar.
        if data.get('equip_classe') == 'inicial' and not equip_txt:
            TbPersonagemItem.objects.create(
                id_personagem=p, qtd=1,
                nome='Ouro inicial (+%d PO) — classe sem kit de equipamento cadastrado' % ouro_alt)
    # Sem armadura inicial: o jogador compra e equipa a armadura na própria ficha,
    # e a CA é derivada do equipamento equipado (não se pré-equipa nada no criador).
    p.carteira_pc = carteira
    p.save(update_fields=['carteira_pc'])
    # `to` já foi resolvido e validado como obrigatório na fase de validação acima.
    if to:
        TbPersonagemTalento.objects.create(id_personagem=p, id_talento=to, categoria='origem', nivel=1, nome=to.nome)
    if data.get('talento_raca'):
        TbPersonagemTalento.objects.create(id_personagem=p, categoria='racial', nivel=1, nome=data['talento_raca'])
    # (Estilo de Luta migrou para o loop genérico `generic_picks` acima — kind `opcao`.)
    # Perícia-Especializada (expertise) escolhida — marca nas perícias proficientes
    for sl in exp_sel[:esc1['expertise_n']]:
        info = _SKILL_INFO.get(sl)
        if info:
            TbPersonagemPericia.objects.filter(id_personagem=p, nome=info[0]).update(expertise=True)
    for pick, vals in classe_prof_validas:
        for nm in vals[:int(pick.get('n') or 0)]:
            TbPersonagemProficiencia.objects.get_or_create(
                id_personagem=p, tipo='ferramenta', nome=nm,
                defaults={'origem': 'classe'})
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
    _refresh_vitais_derivados(p, refill=True)
    return p


def _criador_preview_resumo(ficha):
    """Extrai do derive só o que o painel de preview mostra (PV/CA/atributos/saves/
    proficiências), no formato que o front consome."""
    at = ficha.get('atributos') or {}
    saves = ficha.get('saves') or {}
    ordem = ['FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR']
    atributos = []
    for sig in ordem:
        a = at.get(sig) or {}
        s = saves.get(sig) or {}
        atributos.append({'sig': sig, 'valor': a.get('valor'), 'mod': a.get('mod', 0),
                          'save_bonus': s.get('bonus'), 'save_prof': bool(s.get('proficiente'))})
    pericias = [{'nome': p['nome'], 'atributo': p['atributo'], 'bonus': p['bonus'],
                 'proficiente': p['proficiente'], 'expertise': p['expertise']}
                for p in (ficha.get('pericias') or []) if p.get('proficiente') or p.get('expertise')]
    pv = ficha.get('pv') or {}
    return {
        'nivel': ficha.get('nivel_total'),
        'pb': ficha.get('bonus_proficiencia'),
        'pv': pv.get('maximo_calculado'),
        'pv_completo': pv.get('pv_completo', True),
        'ca': ficha.get('ca'),
        'iniciativa': ficha.get('iniciativa'),
        'velocidade': ficha.get('velocidade'),
        'atributos': atributos,
        'pericias': pericias,
        'idiomas': ficha.get('idiomas') or [],
        'ferramentas': ficha.get('ferramentas') or [],
        'prof_armadura': ficha.get('proficiencias_armadura') or [],
        'prof_arma': ficha.get('proficiencias_arma') or [],
        'n_features': len([f for f in (ficha.get('features') or [])]),
        'n_magias': len(ficha.get('magias') or []),
    }


@require_POST
def criar_personagem_preview_view(request):
    """Preview AO VIVO da ficha: monta o personagem numa transação REVERTIDA, roda o MESMO
    derive do servidor e devolve o resumo — garante que o preview BATE com a ficha final.
    Aceita subconjunto válido (ignora pendências de contagem) p/ atualizar a cada escolha."""
    from .character_engine import derive
    from django.contrib.auth import get_user_model
    data = _json_body(request)
    R, _erros = _criador_resolver(data)
    if not (R['raca'] and R['classe'] and R['antec']):
        return JsonResponse({'ok': True, 'ready': False})
    # Linhagem×Essência é violação ESTRUTURAL (não uma pendência de contagem que o
    # preview deva tolerar) — mesmo guard de _criador_resolver, aqui barrando o "ready"
    # em vez de aparecer só na lista de erros (que este endpoint ignora de propósito).
    if R['linhagem'] and R['essencia']:
        return JsonResponse({'ok': True, 'ready': False})
    dono = request.user if request.user.is_authenticated else get_user_model().objects.order_by('id').first()
    if dono is None:
        return JsonResponse({'ok': True, 'ready': False})
    try:
        with transaction.atomic():
            p = _criador_persistir(dono, data, R)
            ficha = derive(p)
            transaction.set_rollback(True)
    except Exception:
        return JsonResponse({'ok': True, 'ready': False})
    return JsonResponse({'ok': True, 'ready': True, 'preview': _criador_preview_resumo(ficha)})


@login_required(login_url='/login/')
@require_POST
def criar_personagem_view(request):
    """Persiste a ficha criada (point-buy + escolhas) -> TbPersonagem + relacionados."""
    from . import permissions as perms

    data = _json_body(request)

    if not perms.pode_criar(request.user):
        return JsonResponse({'ok': False, 'erros': ['Limite de fichas ativas atingido — guarde uma no cofre.']}, status=400)

    R, erros = _criador_resolver(data)
    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)

    with transaction.atomic():
        p = _criador_persistir(request.user, data, R)

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

    # Seed and ensure default 4 layers
    default_layers = [
        (0, "Cinéria", "assets/cineria.jpg", True),
        (1, "Grande Metrópole Subterrânea", None, False),
        (2, "Zona Proibida", None, False),
        (3, "Câmaras Abissais", None, False),
    ]
    for id_l, name_l, img_l, pub_l in default_layers:
        layer_obj, created = TbMapLayer.objects.get_or_create(
            id_layer=id_l,
            defaults={'nome': name_l, 'imagem_url': img_l, 'ordem': id_l, 'publica': pub_l}
        )
        if not created:
            # Force exact requested name/defaults
            if layer_obj.nome != name_l:
                layer_obj.nome = name_l
                layer_obj.save()

    layers_qs = TbMapLayer.objects.all().order_by('ordem')
    public_layers = list(TbMapLayer.objects.filter(publica=True).values_list('id_layer', flat=True))

    def _layer_url(val):
        if not val:
            return ""
        if val.startswith(('http://', 'https://', '/')):
            return val
        from django.templatetags.static import static
        return static(val)

    # Get main layer image URL for fallback
    main_layer_img = ""
    main_layer = TbMapLayer.objects.filter(id_layer=0).first()
    if main_layer and main_layer.imagem_url:
        main_layer_img = _layer_url(main_layer.imagem_url)

    # Placeholder das camadas subterrâneas sem imagem própria: a arte da
    # SUPERFÍCIE ESCURECIDA (o front aplica brightness-50 via is_placeholder).
    # Cada camada com imagem própria mostra a SUA (upload por camada é isolado);
    # só cai no png dedicado como último recurso, se nem a superfície tiver arte.
    from django.templatetags.static import static as _static
    underground_placeholder_img = _static('assets/subterraneo_placeholder.png')

    layers_lista = []
    for l in layers_qs:
        is_placeholder = (l.id_layer != 0 and not l.imagem_url)
        if l.imagem_url:
            img = _layer_url(l.imagem_url)
        elif l.id_layer != 0:
            # superfície escurecida (is_placeholder → brightness-50 no front)
            img = main_layer_img or underground_placeholder_img
        else:
            img = main_layer_img
        layers_lista.append({
            'id_layer': l.id_layer,
            'nome': l.nome,
            'imagem_url': img,
            'ordem': l.ordem,
            'publica': l.publica,
            'is_placeholder': is_placeholder,
        })

    if not request.user.is_staff:
        layers_lista = [l for l in layers_lista if l['publica']]

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

    desenhos_lista = [desenho_payload(d) for d in TbMapDesenho.objects.filter(ativo=True)]

    if not request.user.is_staff:
        marcadores_lista = [m for m in marcadores_lista if m.get('camada', 0) in public_layers]
        regioes_lista = [r for r in regioes_lista if r.get('camada', 0) in public_layers]
        territorios_lista = [t for t in territorios_lista if t.get('camada', 0) in public_layers]
        desenhos_lista = [d for d in desenhos_lista if d.get('camada', 0) in public_layers]

    context = {
        'json_markers': marcadores_lista,
        'json_regions': regioes_lista,
        'json_territories': territorios_lista,
        'json_layers': layers_lista,
        'json_desenhos': desenhos_lista,
        'can_edit_wiki': request.user.is_staff,
    }
    return render(request, 'home/pages/mapa.html', context)


def mundo_regioes_view(request):
    territory_slug = request.GET.get('territory')
    if territory_slug:
        territory_obj = TbTerritorio.objects.filter(slug=territory_slug).first()
        if territory_obj:
            return redirect('territorio_detail', slug=territory_obj.slug)

    default_layers = [
        (0, "Cinéria", "assets/cineria.jpg", True),
        (1, "Grande Metrópole Subterrânea", None, False),
        (2, "Zona Proibida", None, False),
        (3, "Câmaras Abissais", None, False),
    ]
    for id_l, name_l, img_l, pub_l in default_layers:
        layer_obj, created = TbMapLayer.objects.get_or_create(
            id_layer=id_l,
            defaults={'nome': name_l, 'imagem_url': img_l, 'ordem': id_l, 'publica': pub_l}
        )
        if not created:
            if layer_obj.nome != name_l:
                layer_obj.nome = name_l
                layer_obj.save()

    layer_options = _world_layer_options(request)
    active_layer = _active_world_layer(request, layer_options, default_layer=0)
    visible_layers = [layer.id_layer for layer in layer_options] or [0]

    regioes = TbRegiao.objects.filter(camada__in=visible_layers).order_by('territorio', 'nome')
    territorios_qs = TbTerritorio.objects.filter(camada__in=visible_layers)
    regioes = regioes.filter(camada=active_layer)
    territorios_qs = territorios_qs.filter(camada=active_layer)

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
            'camada': r.camada,
        })

    territories_by_name = {t.nome: t for t in territorios_qs}
    grouped = {}
    for region in regioes_lista:
        key = region['territorio'] or 'Sem território'
        grouped.setdefault(key, []).append(region)

    territorios_cards = []
    for territory_name, regions in sorted(grouped.items(), key=lambda item: item[0]):
        territory = territories_by_name.get(territory_name) or next((t for t in territories_by_name.values() if _normalize_text(t.nome) == _normalize_text(territory_name)), None)
        if not territory:
            # TbRegiao.territorio é um CharField solto (sem FK) — quando o território é
            # apagado do banco, regiões que ainda apontam pro nome antigo ficam órfãs.
            # Elas não devem ressuscitar um card na listagem (o território não existe mais).
            # A região órfã continua acessível normalmente via regiao_detail_view.
            continue
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
        territorios_cards.append({
            'nome': territory_name,
            'display_nome': display_nome,
            'slug': territory.slug if territory else slugify(territory_name),
            'url': reverse('territorio_detail', kwargs={'slug': territory.slug}),
            'imagem_url': image_url,
            'descricao_breve': description,
            'color': color,
            'display_color': display_color,
            'contrast': _get_contrast_color(color),
            'locais_count': len(regions),
            'regioes': regions,
            'tags': tags,
            'camada': territory.camada,
        })

    listed_territory_ids = {card['slug'] for card in territorios_cards}
    for territory in sorted(territories_by_name.values(), key=lambda item: item.nome):
        if territory.slug in listed_territory_ids:
            continue
        territory_name = territory.nome
        image_url = _asset_url(territory.imagem_url) if territory.imagem_url else _asset_url(None)
        color = territory.cor_hex if territory.cor_hex else _territory_color(territory_name)
        display_color = _get_display_color(color)
        display_nome = _display_territory(territory_name)
        territorios_cards.append({
            'nome': territory_name,
            'display_nome': display_nome,
            'slug': territory.slug,
            'url': reverse('territorio_detail', kwargs={'slug': territory.slug}),
            'imagem_url': image_url,
            'descricao_breve': (territory.descricao_breve or '') or f"{_display_territory(territory_name)} ainda não tem regiões cadastradas.",
            'color': color,
            'display_color': display_color,
            'contrast': _get_contrast_color(color),
            'locais_count': 0,
            'regioes': [],
            'tags': [],
            'camada': territory.camada,
        })

    all_territories_list = list(TbTerritorio.objects.values_list('nome', flat=True).order_by('nome'))
    # "Locais conhecidos" do cabeçalho deve bater com a soma dos cards exibidos
    # (regiões órfãs, sem território existente, não entram nos cards nem nessa soma).
    total_locais_visiveis = sum(card['locais_count'] for card in territorios_cards)
    return render(request, 'home/pages/regioes.html', {
        'regioes': regioes_lista,
        'territorios_cards': territorios_cards,
        'total_territorios': len(territorios_cards),
        'total_locais': total_locais_visiveis,
        'can_edit_wiki': request.user.is_staff,
        'categoria_choices': TbMapMarker.PIN_ICON_CHOICES,
        'all_territories_list': all_territories_list,
        'layer_options': layer_options,
        'active_layer': active_layer,
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
        for document in _site_docs('organizations', [('Nome', 1)]):
            payload = _organization_payload(document)
            region_matches = _slug_match_values(payload['regioes'])
            territory_matches = _slug_match_values(payload['territorios'])
            if region_keys.intersection(region_matches) or territory_keys.intersection(territory_matches):
                organizations.append(payload)
    except SiteDataUnavailable:
        return []
    return organizations


def _world_layer_options(request):
    layer_options_qs = TbMapLayer.objects.all().order_by('ordem', 'id_layer')
    if not request.user.is_staff:
        layer_options_qs = layer_options_qs.filter(publica=True)
    return list(layer_options_qs)


def _active_world_layer(request, layer_options, default_layer=0):
    active_layer_raw = request.GET.get('camada', '')
    available_layers = {layer.id_layer for layer in layer_options}
    if active_layer_raw in ('', None):
        if default_layer in available_layers:
            return default_layer
        return layer_options[0].id_layer if layer_options else 0
    try:
        candidate_layer = int(active_layer_raw)
    except (TypeError, ValueError):
        candidate_layer = None
    if candidate_layer in available_layers:
        return candidate_layer
    if default_layer in available_layers:
        return default_layer
    return layer_options[0].id_layer if layer_options else 0


@ensure_csrf_cookie  # edição inline (wiki) lê o csrftoken do cookie
def regiao_detail_view(request, slug):
    regiao = get_object_or_404(TbRegiao, slug=slug)
    if request.user.is_staff:
        public_layers = list(TbMapLayer.objects.values_list('id_layer', flat=True)) or [0]
    else:
        public_layers = list(TbMapLayer.objects.filter(publica=True).values_list('id_layer', flat=True)) or [0]
    if regiao.camada not in public_layers and not request.user.is_staff:
        raise Http404("Região não encontrada")
    layer_options = _world_layer_options(request)
    active_layer = _active_world_layer(request, layer_options, default_layer=regiao.camada)

    
    marker = TbMapMarker.objects.filter(nome=regiao.nome).first()

    
    if not request.user.is_staff:
        all_regioes = TbRegiao.objects.filter(camada__in=public_layers).order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.filter(camada__in=public_layers).order_by('nome')}
    else:
        all_regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.all().order_by('nome')}
    territorios = {}
    for r in all_regioes:
        terr = r.territorio or 'Sem território'
        territorios.setdefault(terr, []).append(r)
    for territory_name in territory_objects:
        territorios.setdefault(territory_name, [])
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
            'camada': territory_obj.camada if territory_obj else (items[0].camada if items else None),
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
            'camada': territory_obj.camada if territory_obj else (items[0].camada if items else None),
        })
        for item in items:
            client_regions.append({
                'type': 'region',
                'id': item.id_regiao,
                'nome': item.nome,
                'slug': item.slug,
                'camada': item.camada,
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

    all_territories_list = list(TbTerritorio.objects.values_list('nome', flat=True).order_by('nome'))
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
        'current_territory_slug': '',
        'current_territory_name': regiao.territorio or 'Sem território',
        'organizations': _organizations_for_location(regiao.nome, regiao.territorio or ''),
        'can_edit_wiki': request.user.is_staff,
        'categoria_choices': TbMapMarker.PIN_ICON_CHOICES,
        'all_territories_list': all_territories_list,
        'is_territory': False,
        'layer_options': layer_options,
        'active_layer': active_layer,
    }
    return render(request, 'home/pages/regiao_detail.html', context)


@ensure_csrf_cookie
def territorio_detail_view(request, slug):
    territory = get_object_or_404(TbTerritorio, slug=slug)
    if request.user.is_staff:
        public_layers = list(TbMapLayer.objects.values_list('id_layer', flat=True)) or [0]
    else:
        public_layers = list(TbMapLayer.objects.filter(publica=True).values_list('id_layer', flat=True)) or [0]
    if territory.camada not in public_layers and not request.user.is_staff:
        raise Http404("Territorio nao encontrado")
    layer_options = _world_layer_options(request)
    active_layer = _active_world_layer(request, layer_options, default_layer=territory.camada)

    regiao = SimpleNamespace(
        id_regiao=None,
        nome=territory.nome,
        slug=territory.slug,
        camada=territory.camada,
        territorio=territory.nome,
        brasao_url=territory.imagem_url or '',
        mapa_url='',
        lore_markdown=territory.lore_markdown or '',
        categoria='territorio',
        etiquetas_adicionais='',
    )

    if not request.user.is_staff:
        all_regioes = TbRegiao.objects.filter(camada__in=public_layers).order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.filter(camada__in=public_layers).order_by('nome')}
    else:
        all_regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
        territory_objects = {t.nome: t for t in TbTerritorio.objects.all().order_by('nome')}

    territorios = {}
    for r in all_regioes:
        terr = r.territorio or 'Sem território'
        territorios.setdefault(terr, []).append(r)
    for territory_name in territory_objects:
        territorios.setdefault(territory_name, [])

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
            'camada': territory_obj.camada if territory_obj else (items[0].camada if items else None),
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
            'is_current': name == territory.nome,
            'camada': territory_obj.camada if territory_obj else (items[0].camada if items else None),
        })
        for item in items:
            client_regions.append({
                'type': 'region',
                'id': item.id_regiao,
                'nome': item.nome,
                'slug': item.slug,
                'camada': item.camada,
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

    color = territory.cor_hex or _territory_color(territory.nome)
    display_color = _get_display_color(color)
    image_url = _asset_url(territory.imagem_url) if territory.imagem_url else _asset_url(None)
    all_territories_list = list(TbTerritorio.objects.values_list('nome', flat=True).order_by('nome'))
    context = {
        'regiao': regiao,
        'imagem_url': image_url,
        'brasao_url': image_url if territory.imagem_url else None,
        'side_image_url': image_url,
        'territory_image_url': image_url,
        'display_territory': _display_territory(territory.nome),
        'territory_color': color,
        'territory_display_color': display_color,
        'territory_contrast': _get_contrast_color(color),
        'marker': None,
        'territorios': territorios,
        'territory_groups': territory_groups,
        'lore_topics': _parse_lore_topics(territory.lore_markdown or ''),
        'client_regions': client_regions,
        'client_territories': client_territories,
        'current_region_slug': '',
        'current_territory_slug': territory.slug,
        'current_territory_name': territory.nome,
        'organizations': _organizations_for_location('', territory.nome),
        'can_edit_wiki': request.user.is_staff,
        'categoria_choices': TbMapMarker.PIN_ICON_CHOICES,
        'all_territories_list': all_territories_list,
        'is_territory': True,
        'layer_options': layer_options,
        'active_layer': active_layer,
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
        'camada': region.camada,
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


def _unique_slug_for_model(model, value, field='slug', pk=None):
    base = slugify(value) or 'unnamed'
    candidate = base
    counter = 2
    qs = model.objects.filter(**{field: candidate})
    if pk is not None:
        qs = qs.exclude(pk=pk)
    while qs.exists():
        candidate = f"{base}-{counter}"
        counter += 1
        qs = model.objects.filter(**{field: candidate})
        if pk is not None:
            qs = qs.exclude(pk=pk)
    return candidate


def _map_conflict_error(model, nome, pk=None, label='registro'):
    if not nome:
        return None
    qs = model.objects.filter(nome__iexact=nome)
    if pk is not None:
        qs = qs.exclude(pk=pk)
    if qs.exists():
        return f'Ja existe {label} com este nome.'
    return None


def _parse_map_layer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@staff_member_required
@require_POST
def wiki_create_region(request):
    data = _json_body(request)
    validate_no_sql_danger(data, 'regiao')

    nome = (data.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'error': 'Nome é obrigatório.'}, status=400)

    conflict = _map_conflict_error(TbRegiao, nome, label='uma regiao')
    if conflict:
        return JsonResponse({'ok': False, 'error': conflict}, status=400)
    conflict = _map_conflict_error(TbMapMarker, nome, label='um marcador')
    if conflict:
        return JsonResponse({'ok': False, 'error': conflict}, status=400)

    territorio = (data.get('territorio') or '').strip() or None
    if territorio:
        from .models import TbTerritorio
        if not TbTerritorio.objects.filter(nome__iexact=territorio).exists():
            return JsonResponse({'ok': False, 'error': f'O território "{territorio}" não existe. Por favor, crie-o primeiro no painel de administração.'}, status=400)

    slug = slugify(nome)
    if not slug:
        return JsonResponse({'ok': False, 'error': 'Não foi possível gerar slug do nome.'}, status=400)

    
    slug = _unique_slug_for_model(TbRegiao, nome)

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
        camada=_parse_map_layer(data.get('camada'), 0),
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

    new_nome = (data.get('nome') or region.nome).strip()
    if not new_nome:
        return JsonResponse({'ok': False, 'error': 'Nome e obrigatorio.'}, status=400)
    conflict = _map_conflict_error(TbRegiao, new_nome, pk=region.pk, label='uma regiao')
    if conflict:
        return JsonResponse({'ok': False, 'error': conflict}, status=400)
    marker_conflicts = TbMapMarker.objects.filter(nome__iexact=new_nome).exclude(nome__iexact=region.nome)
    if marker_conflicts.exists():
        return JsonResponse({'ok': False, 'error': 'Ja existe um marcador com este nome.'}, status=400)
    name_changed = _normalize_text(new_nome) != _normalize_text(region.nome)
    region.nome = new_nome
    if name_changed:
        region.slug = _unique_slug_for_model(TbRegiao, new_nome, pk=region.pk)


    region.lore_markdown = data.get('lore_markdown') if 'lore_markdown' in data else region.lore_markdown
    
    if 'territorio' in data:
        territorio_val = (data.get('territorio') or '').strip() or None
        if territorio_val:
            from .models import TbTerritorio
            if not TbTerritorio.objects.filter(nome__iexact=territorio_val).exists():
                return JsonResponse({'ok': False, 'error': f'O território "{territorio_val}" não existe. Por favor, crie-o primeiro no painel de administração.'}, status=400)
        region.territorio = territorio_val

    region.categoria = data.get('categoria') if data.get('categoria') in valid_categorias else region.categoria
    if 'camada' in data:
        region.camada = _parse_map_layer(data.get('camada'), region.camada)
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
    return JsonResponse({
        'ok': True,
        'region': _region_payload(region),
        'redirect': reverse('regiao_detail', kwargs={'slug': region.slug}),
    })

@staff_member_required
@require_POST
def wiki_create_territory(request):
    data = _json_body(request)
    validate_no_sql_danger(data, 'territorio')

    nome = (data.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'error': 'Nome é obrigatório.'}, status=400)

    slug = slugify(nome)
    if not slug:
        return JsonResponse({'ok': False, 'error': 'Não foi possível gerar slug do nome.'}, status=400)

    if TbTerritorio.objects.filter(Q(slug=slug) | Q(nome__iexact=nome)).exists():
        return JsonResponse({'ok': False, 'error': 'Um território com este nome já existe.'}, status=400)

    cor_hex = (data.get('cor_hex') or '#ffffff').strip()
    camada = int(data.get('camada') or 0)

    territory = TbTerritorio.objects.create(
        nome=nome,
        slug=slug,
        cor_hex=cor_hex,
        camada=camada,
    )

    _log_wiki_creation(request, territory, f"Criação inline de território: {territory.nome}")

    return JsonResponse({
        'ok': True,
        'territory': {
            'id': territory.id_territorio,
            'nome': territory.nome,
            'slug': territory.slug,
            'cor_hex': territory.cor_hex,
            'camada': territory.camada,
        }
    })


@staff_member_required
@require_POST
def wiki_update_territory(request, territory_id):
    data = _json_body(request)
    validate_no_sql_danger(data, 'territorio')
    territory = get_object_or_404(TbTerritorio, pk=territory_id)

    new_nome = (data.get('nome') or territory.nome).strip()
    if not new_nome:
        return JsonResponse({'ok': False, 'error': 'Nome e obrigatorio.'}, status=400)
    conflict = _map_conflict_error(TbTerritorio, new_nome, pk=territory.pk, label='um territorio')
    if conflict:
        return JsonResponse({'ok': False, 'error': conflict}, status=400)
    territory.nome = new_nome
    territory.imagem_url = (data.get('imagem_url') or '').strip() or None
    territory.descricao_breve = (data.get('descricao_breve') or '').strip() or None
    territory.lore_markdown = (data.get('lore_markdown') or '').strip() or None
    if 'cor_hex' in data:
        territory.cor_hex = (data.get('cor_hex') or territory.cor_hex or '#ffffff').strip()
    if 'camada' in data:
        territory.camada = _parse_map_layer(data.get('camada'), territory.camada)
    
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
    return JsonResponse({'ok': True, 'redirect': reverse('territorio_detail', kwargs={'slug': territory.slug})})


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
            
            valid_categorias = dict(TbMapMarker.PIN_ICON_CHOICES)
            for m_data in data.get('markers', []):
                m_id = m_data.get('id')
                if m_id in ['undefined', 'null', '']:
                    m_id = None
                nome = (m_data.get('nome') or '').strip()
                if not nome:
                    continue

                lat = float(m_data.get('lat', 0))
                lng = float(m_data.get('lng', 0))
                categoria = m_data.get('categoria') if m_data.get('categoria') in valid_categorias else 'cidade'
                territorio = (m_data.get('territorio') or '').strip() or None
                camada = _parse_map_layer(m_data.get('camada'), 0)

                if territorio and not TbTerritorio.objects.filter(nome__iexact=territorio).exists():
                    return JsonResponse({'ok': False, 'error': f'O territorio "{territorio}" nao existe.'}, status=400)

                marker = None
                original_name = None
                if m_id:
                    marker = TbMapMarker.objects.select_for_update().filter(pk=m_id).first()
                    if marker is None:
                        return JsonResponse({'ok': False, 'error': 'Marcador nao encontrado para edicao.'}, status=404)
                    original_name = marker.nome
                else:
                    if TbMapMarker.objects.filter(nome__iexact=nome).exists() or TbRegiao.objects.filter(nome__iexact=nome).exists():
                        return JsonResponse({'ok': False, 'error': 'Ja existe uma regiao ou marcador com este nome.'}, status=400)
                    marker = TbMapMarker.objects.create(
                        nome=nome,
                        lat=lat,
                        lng=lng,
                        categoria=categoria,
                        territorio=territorio,
                        camada=camada,
                    )

                search_name = original_name or nome
                region = TbRegiao.objects.select_for_update().filter(nome__iexact=search_name).first()

                if original_name and _normalize_text(original_name) != _normalize_text(nome):
                    if TbMapMarker.objects.filter(nome__iexact=nome).exclude(pk=marker.pk).exists():
                        return JsonResponse({'ok': False, 'error': 'Ja existe um marcador com este nome.'}, status=400)
                    region_conflicts = TbRegiao.objects.filter(nome__iexact=nome)
                    if region is not None:
                        region_conflicts = region_conflicts.exclude(pk=region.pk)
                    if region_conflicts.exists():
                        return JsonResponse({'ok': False, 'error': 'Ja existe uma regiao com este nome.'}, status=400)

                marker.nome = nome
                marker.lat = lat
                marker.lng = lng
                marker.categoria = categoria
                marker.territorio = territorio
                marker.camada = camada
                marker.save()
                _log_wiki_edit(request, marker, f"Marcador de mapa salvo via lote: {marker.nome}")

                if region is None:
                    region = TbRegiao.objects.create(
                        nome=nome,
                        slug=_unique_slug_for_model(TbRegiao, nome),
                        categoria=categoria,
                        territorio=territorio,
                        camada=camada,
                    )
                    _log_wiki_edit(request, region, f"Regiao de mapa criada via lote: {region.nome}")
                else:
                    if _normalize_text(region.nome) != _normalize_text(nome):
                        region.slug = _unique_slug_for_model(TbRegiao, nome, pk=region.pk)
                    region.nome = nome
                    region.categoria = categoria
                    region.territorio = territorio
                    region.camada = camada
                    region.save()
                    _log_wiki_edit(request, region, f"Regiao de mapa salva via lote: {region.nome}")
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
        talentos_docs = _site_docs('talents', [('Nome', 1)])
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
    except SiteDataUnavailable:
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
        opcoes_docs = _site_docs('options', [('Nome', 1)])
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
    except SiteDataUnavailable:
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
        documents = _site_docs(key, [(sort_field, 1)])
    except SiteDataUnavailable as exc:
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
    items, db_error = _catalog_list(key, mapper)
    return render(request, 'home/pages/catalogo.html', {
        'title': title,
        'subtitle': subtitle,
        'kind': kind,
        'items': items,
        'db_error': db_error,
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
        
    return render(request, 'home/pages/catalogo.html', {
        'title': 'Antecedentes',
        'subtitle': 'Origens, ofícios, vínculos e escolhas de história para personagens.',
        'kind': 'antecedentes',
        'items': items,
        'db_error': None,
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
    return render(request, 'home/pages/catalogo.html', {
        'title': 'Idiomas',
        'subtitle': 'Línguas de Bonfire Tales — basais, derivadas e exóticas.',
        'kind': 'idiomas',
        'items': items,
        'db_error': '',
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
    return render(request, 'home/pages/catalogo.html', {
        'title': 'Escolas de Magia',
        'subtitle': 'As oito escolas de magia e as magias que pertencem a cada uma.',
        'kind': 'escolas',
        'items': items,
        'db_error': '',
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


def _sb_text(v):
    if v is None:
        return ''
    if isinstance(v, str):
        return _clean_statblock_text(v)
    if isinstance(v, dict):
        for key in ('name', 'entry', 'entries', 'type', 'special'):
            if key in v:
                return _sb_text(v.get(key))
        return _clean_statblock_text(str(v))
    if isinstance(v, (list, tuple)):
        return ', '.join(_sb_text(x) for x in v if _sb_text(x))
    return _clean_statblock_text(str(v))


def _sb_size_text(sb, criatura=None):
    size = sb.get('size') if isinstance(sb, dict) else ''
    if isinstance(size, list):
        size = size[0] if size else ''
    value = _SB_TAM.get(size, size or getattr(criatura, 'tamanho', '') or '')
    return _clean_statblock_text(value)


def _sb_type_text(sb, criatura=None):
    tp = sb.get('type') if isinstance(sb, dict) else ''
    if isinstance(tp, dict):
        tp = tp.get('type') or tp.get('name') or ''
    return _clean_statblock_text(_sb_tipo_pt(tp or getattr(criatura, 'tipo', '') or ''))


def _sb_alignment_text(sb, criatura=None):
    alin = sb.get('alignment') if isinstance(sb, dict) else ''
    if isinstance(alin, list):
        return ', '.join(_SB_ALIN.get(a, str(a)) for a in alin if a)
    return _clean_statblock_text(alin or getattr(criatura, 'alinhamento', '') or '')


def _sb_sections(sb, *keys):
    out = []
    for key in keys:
        value = sb.get(key) if isinstance(sb, dict) else None
        if isinstance(value, list):
            out.extend(value)
    return out


def _sb_section_groups(sb):
    return [
        ('Tracos', _sb_sections(sb, 'trait', 'traits')),
        ('Conjuracao', _spellcasting_blocks(sb)),
        ('Acoes', _sb_sections(sb, 'action', 'actions')),
        ('Acoes bonus', _sb_sections(sb, 'bonus', 'bonus_actions')),
        ('Reacoes', _sb_sections(sb, 'reaction', 'reactions')),
        ('Acoes lendarias', _sb_sections(sb, 'legendary', 'legendary_actions')),
        ('Acoes miticas', _sb_sections(sb, 'mythic', 'mythic_actions')),
        ('Acoes de covil', _sb_sections(sb, 'lair', 'lair_actions')),
        ('Efeitos regionais', _sb_sections(sb, 'regional', 'regional_effects')),
    ]


def _spellcasting_blocks(sb):
    blocks = []
    for section in ('trait', 'traits', 'action', 'actions', 'bonus', 'bonus_actions', 'reaction', 'reactions'):
        for block in _sb_sections(sb, section):
            if not isinstance(block, dict):
                continue
            uses = block.get('spell_uses') or []
            refs = block.get('spell_refs') or []
            name = (block.get('name') or block.get('name_en') or '').lower()
            if uses or ('spellcasting' in name) or ('conjuracao' in name) or refs:
                blocks.append(block)
    return blocks


def _spellcasting_display(sb):
    out = []
    for block in _spellcasting_blocks(sb):
        rows = []
        for use in block.get('spell_uses') or []:
            label = use.get('label') or use.get('label_en') or ''
            spells = use.get('spells') or []
            rows.append({
                'label': _clean_statblock_text(label),
                'spells': [{'nome': s.get('name') or s.get('name_en') or s.get('slug'), 'slug': s.get('slug')} for s in spells if isinstance(s, dict)],
            })
        if not rows and block.get('spell_refs'):
            rows.append({
                'label': 'Referencias',
                'spells': [{'nome': s.get('name') or s.get('name_en') or s.get('slug'), 'slug': s.get('slug')} for s in block.get('spell_refs') if isinstance(s, dict)],
            })
        if rows:
            out.append({'nome': _clean_statblock_text(block.get('name') or block.get('name_en') or 'Conjuracao'), 'rows': rows})
    return out


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


def _statblock_display_full(sb, criatura=None):
    sb = sb or {}
    base = _statblock_display(sb, criatura)
    ability_map = sb.get('abilities') if isinstance(sb.get('abilities'), dict) else {}
    if ability_map:
        base['abilities'] = []
        for en, sig in _SB_AB:
            sc = ability_map.get(en)
            if sc is None:
                continue
            mod = _sb_mod(sc)
            base['abilities'].append({'sig': sig, 'score': sc, 'mod': _sb_sgn(mod), 'save': _sb_sgn(mod)})

    if sb.get('ac_text'):
        base['ca'] = sb.get('ac_text')
    if isinstance(sb.get('speed'), str):
        base['desloc'] = sb.get('speed')
    if sb.get('saving_throws'):
        base['saves'] = _clean_statblock_text(sb.get('saving_throws'))
    if isinstance(sb.get('skills'), list):
        base['skills'] = ', '.join(_clean_statblock_text(x) for x in sb.get('skills'))

    def _join_any(*keys):
        for key in keys:
            value = sb.get(key)
            if value:
                return _sb_text(value)
        return ''

    alignment = _sb_alignment_text(sb, criatura)
    base['cabecalho'] = ('%s %s%s' % (
        _sb_size_text(sb, criatura),
        _sb_type_text(sb, criatura),
        (', ' + alignment) if alignment else '',
    )).strip()
    base['resist'] = _join_any('damage_resistances', 'resist')
    base['immune'] = _join_any('damage_immunities', 'immune')
    base['vuln'] = _join_any('damage_vulnerabilities', 'vulnerable')
    base['cond_immune'] = _join_any('condition_immunities', 'conditionImmune')
    base['traits'] = _sb_bloco(_sb_sections(sb, 'trait', 'traits'))
    base['actions'] = _sb_bloco(_sb_sections(sb, 'action', 'actions'))
    base['bonus'] = _sb_bloco(_sb_sections(sb, 'bonus', 'bonus_actions'))
    base['reactions'] = _sb_bloco(_sb_sections(sb, 'reaction', 'reactions'))
    base['legendary'] = _sb_bloco(_sb_sections(sb, 'legendary', 'legendary_actions'))
    base['mythic'] = _sb_bloco(_sb_sections(sb, 'mythic', 'mythic_actions'))
    base['lair'] = _sb_bloco(_sb_sections(sb, 'lair', 'lair_actions'))
    base['regional'] = _sb_bloco(_sb_sections(sb, 'regional', 'regional_effects'))
    base['spellcasting'] = _spellcasting_display(sb)
    return base


def bestiario_view(request):
    """Bestiário: criaturas oficiais + da comunidade, com statblock 5e renderizado.
    Filtros: origem (todas/oficial/comunidade), ND, e ordenação alfabética A→Z/Z→A."""
    from .models import TbBestiario
    from . import permissions as perms
    filtro = request.GET.get('f', '')
    nd_sel = request.GET.get('nd', '')
    tipo_sel = request.GET.get('tipo', '')
    tam_sel = request.GET.get('tam', '')
    ordem = request.GET.get('ord', 'az')
    is_staff = perms.is_staff_user(request.user)
    qs = TbBestiario.objects.select_related('autor')
    if filtro == 'oficial':
        qs = qs.filter(comunidade=False)
    elif filtro == 'comunidade':
        qs = qs.filter(comunidade=True)
    if nd_sel:
        qs = qs.filter(nd=nd_sel)
    if tipo_sel:
        qs = qs.filter(tipo=tipo_sel)
    if tam_sel:
        qs = qs.filter(tamanho=tam_sel)
    criaturas = []
    for b in qs:
        criaturas.append({
            'id': b.id_criatura, 'nome': b.nome, 'slug': b.slug,
            'tipo': _sb_tipo_pt(b.tipo), 'nd': b.nd or '', 'tamanho': _SB_TAM.get(b.tamanho, b.tamanho or ''),
            'comunidade': b.comunidade, 'autor': b.autor.username if b.autor_id else None,
            'imagem': b.imagem_url or '',
            'busca': ' '.join([b.nome or '', b.slug or '', b.tipo or '', b.tamanho or '', b.nd or '']).lower(),
            'nd_valor': _nd_valor(b.nd),
            'sb': _statblock_display_full(b.statblock_json if isinstance(b.statblock_json, dict) else {}, b),
            'descricao': _clean_5et(b.descricao_markdown or ''),
            'pode_editar': is_staff or (b.comunidade and b.autor_id == request.user.id),
        })
    if ordem == 'za':
        criaturas.sort(key=lambda c: c['nome'].lower(), reverse=True)
    elif ordem == 'nd_desc':
        criaturas.sort(key=lambda c: (c['nd_valor'], c['nome'].lower()), reverse=True)
    elif ordem == 'nd_asc':
        criaturas.sort(key=lambda c: (c['nd_valor'], c['nome'].lower()))
    else:
        criaturas.sort(key=lambda c: c['nome'].lower())
    all_qs = TbBestiario.objects.all()
    nds_all = sorted({(x.nd or '').strip() for x in all_qs if (x.nd or '').strip()}, key=_nd_valor)
    tipos_all = sorted({(x.tipo or '').strip() for x in all_qs if (x.tipo or '').strip()})
    tamanhos_all = sorted({(x.tamanho or '').strip() for x in all_qs if (x.tamanho or '').strip()})
    return render(request, 'home/pages/bestiario.html', {
        'page_title': 'Bestiário',
        'criaturas': criaturas, 'filtro': filtro, 'nd_sel': nd_sel, 'tipo_sel': tipo_sel,
        'tam_sel': tam_sel, 'ordem': ordem, 'nds': nds_all,
        'tipos': tipos_all, 'tamanhos': tamanhos_all,
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
            ca=str(num('ca', 10)), pv=str(num('pv', 1)),
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
            document_to_save = dict(document)
            document_to_save['CreatedAt'] = document_to_save.get('CreatedAt') or datetime.now(datetime_timezone.utc)
            _upsert_site_document('organizations', 'Slug', document['Slug'], document_to_save)
        except SiteDataUnavailable as exc:
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
        opcoes_docs = _site_docs('options', [('Nome', 1)], query=query if tipo_filter else None)
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
    except SiteDataUnavailable:
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
    from django.utils.html import escape as esc
    from home.models import (
        TbClasse, TbSubclasse, TbClassehabilidade, TbTalento, TbRaca, TbRegiao,
        TbTerritorio, TbOrganizacao, TbMagia, TbBestiario
    )

    table = request.GET.get('table', '').strip().lower()
    args_str = request.GET.get('args', '').strip()
    args = [arg.strip() for arg in args_str.split(',') if arg.strip()]

    title = ""
    subtitle = ""
    kind = "generic"
    description = ""
    read_more_url = ""
    card_html = ""
    card_width = 360

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
            if ability.id_subclasse:
                subtitle = f"Subclasse: {ability.id_subclasse.nome} · Classe: {ability.id_classe.nome} lvl {ability.niveladquirido}"
            else:
                subtitle = f"Classe: {ability.id_classe.nome} lvl {ability.niveladquirido}"
            kind = "ability"
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
            subtitle = "Classe"
            kind = "class"
            description = classe.tagline or ""
            read_more_url = f"/jogador/classes/{classe.slug}/"

    # 3. Subclasse
    elif table in ['tbsubclasse', 'subclasses', 'subclasse']:
        p1 = args[0]
        sub = TbSubclasse.objects.filter(slug=p1).first()
        if sub:
            title = sub.nome
            subtitle = f"Subclasse: {sub.id_classe.nome}"
            kind = "subclass"
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
            subtitle = "Talento"
            kind = "talent"
            description = tal.descricao or ""
            read_more_url = f"/jogador/talentos/#{slugify_py(tal.nome)}"

    # 5. Raça
    elif table in ['tbraca', 'raca', 'racas']:
        p1 = args[0]
        raca = TbRaca.objects.filter(slug=p1).first()
        if raca:
            title = raca.nome
            subtitle = f"Raca: {raca.nome}"
            kind = "race"
            description = raca.tagline or ""
            read_more_url = f"/jogador/raca/{raca.slug}/"

    # 6. Região
    elif table in ['tbregiao', 'regiao', 'regioes']:
        p1 = args[0]
        reg = TbRegiao.objects.filter(slug=p1).first()
        if reg:
            title = reg.nome
            subtitle = "Regiao" + (f" - {reg.territorio}" if reg.territorio else "")
            kind = "region"
            description = reg.lore_markdown or ""
            card_width = 420
            read_more_url = f"/mundo/regioes/{reg.slug}/"

    # 7. Territorio
    elif table in ['tbterritorio', 'territorio', 'territorios']:
        p1 = args[0]
        territorio = TbTerritorio.objects.filter(slug=p1).first()
        if territorio:
            title = territorio.nome
            subtitle = "Territorio"
            kind = "territory"
            description = territorio.lore_markdown or territorio.descricao_breve or ""
            card_width = 420
            read_more_url = f"/mundo/territorios/{territorio.slug}/"

    # 8. Organizacao
    elif table in ['tborganizacao', 'organizacao', 'organizacoes', 'organization', 'organizations']:
        p1 = args[0]
        organizacao = TbOrganizacao.objects.filter(slug=p1).first()
        if organizacao:
            title = organizacao.nome
            subtitle = organizacao.tipo or "Organizacao"
            if organizacao.sede:
                subtitle += f" - Sede: {organizacao.sede}"
            kind = "organization"
            description = organizacao.descricao or ""
            card_width = 420
            read_more_url = f"/mundo/organizacoes/#{organizacao.slug}"

    # 9. Magia
    elif table in ['tbmagia', 'magia', 'magias']:
        p1 = args[0]
        mag = None
        for m in TbMagia.objects.all():
            if slugify_py(m.nome) == p1 or m.slug == p1:
                mag = m
                break
        if mag:
            title = mag.nome
            subtitle = "%s · %s" % ("Truque" if mag.nivel == 0 else f"Nivel {mag.nivel}", mag.escola or "Magia")
            kind = "spell"
            meta_lines = [
                f"**Tempo de conjuracao:** {mag.casting_time or '-'}",
                f"**Alcance:** {mag.alcance or '-'}",
                f"**Componentes:** {mag.componentes or '-'}",
                f"**Duracao:** {mag.duracao or '-'}",
                f"**Escola:** {mag.escola or '-'}",
                f"**Nivel:** {'Truque' if mag.nivel == 0 else mag.nivel}",
                f"**Ritual:** {'Sim' if mag.ritual else 'Nao'}",
                f"**Concentracao:** {'Sim' if mag.concentracao else 'Nao'}",
            ]
            description = "\n".join(meta_lines) + "\n\n" + (mag.descricao or "")
            if mag.em_niveis_superiores:
                description += "\n\n### Em niveis superiores\n" + mag.em_niveis_superiores
            if mag.classes:
                description += "\n\n**Classes:** " + mag.classes
            card_width = 400
            read_more_url = f"/magias/listas/#{slugify_py(mag.nome)}"

    # 10. Criatura / Bestiario
    elif table in ['tbbestiario', 'bestiario', 'criatura', 'creature', 'monster']:
        p1 = args[0]
        cr = TbBestiario.objects.filter(slug=p1).first()
        if not cr:
            for item in TbBestiario.objects.all():
                if slugify_py(item.nome) == p1:
                    cr = item
                    break
        if cr:
            title = cr.nome
            subtitle = "Criatura: %s%s" % (cr.tipo or "", (" · ND " + cr.nd) if cr.nd else "")
            kind = "monster"
            card_width = 540
            card_html = _render_creature_statblock_full(cr)
            if cr.descricao_markdown:
                card_html += '<div class="bonfire-creature-desc bonfire-markdown">%s</div>' % esc(cr.descricao_markdown)
            read_more_url = f"/mestre/bestiario/#monster-{cr.id_criatura}"

    if title:
        return JsonResponse({
            'success': True,
            'title': title,
            'subtitle': subtitle,
            'kind': kind,
            'description': description,
            'card_html': card_html,
            'card_width': card_width,
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


def _render_creature_statblock_full(cr):
    from django.utils.html import escape as esc
    sb = cr.statblock_json if isinstance(cr.statblock_json, dict) else {}
    display = _statblock_display_full(sb, cr)
    parts = []

    def line(label, value):
        if not value:
            return ''
        return '<div class="bonfire-creature-line"><b>%s</b> %s</div>' % (esc(label), esc(str(value)))

    parts.append('<div class="bonfire-creature-card-sheet">')
    parts.append('<div class="bonfire-creature-meta">%s%s%s</div>' % (
        '<span><b>CA</b> %s</span>' % esc(str(display.get('ca'))) if display.get('ca') else '',
        '<span><b>PV</b> %s</span>' % esc(str(display.get('pv'))) if display.get('pv') else '',
        '<span><b>Deslocamento</b> %s</span>' % esc(str(display.get('desloc'))) if display.get('desloc') else '',
    ))
    if display.get('abilities'):
        parts.append('<div class="bonfire-creature-attrs">')
        for a in display['abilities']:
            parts.append('<div><span class="ab">%s</span><span class="sc">%s (%s)</span></div>' % (
                esc(a.get('sig', '')), esc(str(a.get('score', ''))), esc(str(a.get('mod', '')))
            ))
        parts.append('</div>')

    for label, key in [
        ('Salvaguardas', 'saves'), ('Pericias', 'skills'), ('Vulnerabilidades', 'vuln'),
        ('Resistencias', 'resist'), ('Imunidades a dano', 'immune'), ('Imunidades a condicao', 'cond_immune'),
        ('Sentidos', 'sentidos'), ('Idiomas', 'idiomas'), ('Nivel de Desafio', 'cr'),
    ]:
        parts.append(line(label, display.get(key)))

    if display.get('spellcasting'):
        parts.append('<div class="bonfire-creature-section"><h4>Conjuracao</h4>')
        for cast in display['spellcasting']:
            parts.append('<div class="bonfire-creature-trait"><strong>%s.</strong>' % esc(cast.get('nome') or 'Conjuracao'))
            for row in cast.get('rows') or []:
                spell_links = []
                for spell in row.get('spells') or []:
                    nome = esc(spell.get('nome') or spell.get('slug') or '')
                    slug = spell.get('slug')
                    if slug:
                        spell_links.append('<a href="#" class="bonfire-card-trigger" data-table="tbMagia" data-args="%s">%s</a>' % (esc(slug), nome))
                    else:
                        spell_links.append(nome)
                parts.append('<div><b>%s</b> %s</div>' % (esc(row.get('label') or ''), ', '.join(spell_links)))
            parts.append('</div>')
        parts.append('</div>')

    for label, key in [
        ('Tracos', 'traits'), ('Acoes', 'actions'), ('Acoes bonus', 'bonus'),
        ('Reacoes', 'reactions'), ('Acoes lendarias', 'legendary'), ('Acoes miticas', 'mythic'),
        ('Acoes de covil', 'lair'), ('Efeitos regionais', 'regional'),
    ]:
        blocks = display.get(key) or []
        if not blocks:
            continue
        parts.append('<div class="bonfire-creature-section"><h4>%s</h4>' % esc(label))
        for block in blocks:
            parts.append('<div class="bonfire-creature-trait"><strong>%s.</strong> %s</div>' % (
                esc(block.get('nome') or ''), esc(block.get('texto') or '')
            ))
        parts.append('</div>')

    parts.append('</div>')
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
        'statblock_html': _render_creature_statblock_full(cr),
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
        mec = mecanica_de_tags(i.tags_json, i.subcategoria)
        i.mec_dano = dano_display(mec)
        i.mec_ca = ca_display(mec)
        i.mec_propriedades = propriedades_display(mec)
        i.mec_maestrias = ", ".join(mec.get("maestrias") or [])
        i.mec_forca_minima = mec.get("forca_minima")
        i.mec_furtividade = mec.get("furtividade_desvantagem")
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
    itens = list(TbItemMagico.objects.all().order_by('raridade', 'nome'))
    # Preço da loja para exibição: item sem preço OU preço <= 0 é recompensa de missão
    # (não comercializável) — o template mostra "Recompensa de missão" no lugar do número.
    for i in itens:
        i.preco_loja = ('%g PO' % float(i.preco)) if (i.preco is not None and float(i.preco) > 0) else None

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


from django.core.files.storage import default_storage
import os

@login_required
def wiki_add_layer(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acesso negado. Apenas superusuários podem gerenciar camadas.'}, status=403)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        ordem_raw = request.POST.get('ordem', '0')
        publica = request.POST.get('publica') in ('true', 'on', '1')
        file_obj = request.FILES.get('imagem')
        
        if not nome:
            return JsonResponse({'error': 'O nome da camada é obrigatório.'}, status=400)
        if not file_obj:
            return JsonResponse({'error': 'A imagem de fundo é obrigatória.'}, status=400)
            
        try:
            ordem = int(ordem_raw)
        except ValueError:
            ordem = 0
            
        # Save file to default_storage (saves in MEDIA_ROOT/map_layers)
        name = default_storage.save(os.path.join('map_layers', file_obj.name), file_obj)
        imagem_url = default_storage.url(name)
        
        # Get next ID
        from django.db.models import Max
        max_id = TbMapLayer.objects.aggregate(Max('id_layer'))['id_layer__max']
        next_id = (max_id or 0) + 1
        if next_id < 2:  # 0 and 1 are reserved for Surface and Subterraneo Lvl 1
            next_id = 2
            
        TbMapLayer.objects.create(
            id_layer=next_id,
            nome=nome,
            imagem_url=imagem_url,
            ordem=ordem,
            publica=publica
        )
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
def wiki_edit_layer(request, layer_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acesso negado. Apenas superusuários podem gerenciar camadas.'}, status=403)
        
    layer = get_object_or_404(TbMapLayer, id_layer=layer_id)
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        ordem_raw = request.POST.get('ordem', str(layer.ordem))
        publica = request.POST.get('publica') in ('true', 'on', '1')
        file_obj = request.FILES.get('imagem')
        
        if not nome:
            return JsonResponse({'error': 'O nome da camada é obrigatório.'}, status=400)
            
        try:
            ordem = int(ordem_raw)
        except ValueError:
            ordem = layer.ordem
            
        layer.nome = nome
        layer.ordem = ordem
        # Layer 0 (Surface) must remain public to prevent lockout
        if layer_id == 0:
            layer.publica = True
        else:
            layer.publica = publica
            
        if file_obj:
            name = default_storage.save(os.path.join('map_layers', file_obj.name), file_obj)
            layer.imagem_url = default_storage.url(name)
            
        layer.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'Método não permitido.'}, status=405)


@login_required
@require_POST
def wiki_delete_layer(request, layer_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Acesso negado. Apenas superusuários podem gerenciar camadas.'}, status=403)
        
    if layer_id == 0:
        return JsonResponse({'error': 'Não é possível excluir a camada principal (Superfície).'}, status=400)
        
    layer = get_object_or_404(TbMapLayer, id_layer=layer_id)
    
    # Reassociate markers, regions, and territories belonging to this layer to layer 0
    TbMapMarker.objects.filter(camada=layer_id).update(camada=0)
    TbRegiao.objects.filter(camada=layer_id).update(camada=0)
    TbTerritorio.objects.filter(camada=layer_id).update(camada=0)
    TbMapDesenho.objects.filter(camada=layer_id).update(camada=0)

    layer.delete()
    return JsonResponse({'ok': True})


# ===========================================================================
# Desenhos do mapa (WP1): imagens e linhas livres desenhadas pela staff.
# Contrato (dados_json por tipo):
#   linha:  { pontos: [[lat,lng],...], cor: '#rrggbb', espessura: 1..12,
#             tracejado: bool, liga_marker_inicio: <id|null>,
#             liga_marker_fim: <id|null>, descricao: '<texto plano, <=300>' }
#   imagem: { url: '<media/static/http>', bounds: [[lat,lng],[lat,lng]],
#             opacidade: 0.1..1.0, descricao: '<texto plano, <=300>' }
# Campo `nome` (WP2) mora no modelo (TbMapDesenho.nome), não no dados_json;
# `descricao` complementa o nome e é opcional para os dois tipos.
# Toda validação é server-side em sanitize_desenho(); os endpoints só
# persistem o que passa pela sanitização.
# ===========================================================================

_HEX_COR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

# Extensões e limite próprios do upload de imagem de mapa (independente do
# perfil): PNG/JPG/JPEG/WEBP/GIF, até ~8MB.
MAP_IMAGE_UPLOAD_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
MAP_IMAGE_UPLOAD_MAX_MB = 8


def _clamp_num(val, minimo, maximo, padrao):
    """Converte para float e limita a [minimo, maximo]; usa padrao se inválido."""
    try:
        n = float(val)
    except (TypeError, ValueError):
        return padrao
    if n != n:  # NaN
        return padrao
    return max(minimo, min(maximo, n))


def _ponto_valido(p):
    """Um ponto = par [lat, lng] numérico finito."""
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        return None
    try:
        lat = float(p[0])
        lng = float(p[1])
    except (TypeError, ValueError):
        return None
    if lat != lat or lng != lng:  # NaN
        return None
    if lat in (float('inf'), float('-inf')) or lng in (float('inf'), float('-inf')):
        return None
    return [lat, lng]


def _url_imagem_segura(url):
    """Aceita só /media/, /static/ ou http(s). Bloqueia javascript:, data:, etc."""
    url = (url or '').strip()
    if not url:
        return ''
    baixo = url.lower()
    if baixo.startswith(('http://', 'https://')):
        return url
    if url.startswith(('/media/', '/static/')):
        return url
    return ''


def _descricao_segura(valor):
    """Descrição plana opcional (linha/imagem): remove tags HTML, colapsa espaços
    e corta em 300 chars. Nunca retorna HTML — texto puro."""
    if valor in (None, ''):
        return ''
    texto = str(valor)
    # Remove qualquer marcação HTML/tag (inclui <script>, <b>, etc.) — sobra só texto.
    texto = re.sub(r'<[^>]*>', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto[:300]


def _marker_id_valido(valor):
    """Retorna o id do marker se ele existir no banco; senão None."""
    if valor in (None, '', 'null', 'undefined'):
        return None
    try:
        mid = int(valor)
    except (TypeError, ValueError):
        return None
    if TbMapMarker.objects.filter(pk=mid).exists():
        return mid
    return None


def sanitize_desenho(tipo, dados):
    """Valida/normaliza o dados_json de um desenho conforme o tipo.

    Retorna (tipo_normalizado, dados_limpos). Levanta ValueError se o payload
    for irrecuperável (tipo inválido, poucos pontos, imagem sem url/bounds).
    Função pura e testável — não toca no banco a não ser para validar a
    existência dos markers de ligação (liga_marker_*)."""
    tipo = (tipo or '').strip().lower()
    if tipo not in ('linha', 'imagem'):
        raise ValueError('Tipo de desenho inválido (use "linha" ou "imagem").')

    if not isinstance(dados, dict):
        raise ValueError('dados_json deve ser um objeto.')

    if tipo == 'linha':
        pontos_raw = dados.get('pontos')
        if not isinstance(pontos_raw, (list, tuple)):
            raise ValueError('Linha requer uma lista de pontos.')
        pontos = []
        for p in pontos_raw:
            pv = _ponto_valido(p)
            if pv is not None:
                pontos.append(pv)
        if len(pontos) < 2:
            raise ValueError('Linha requer no mínimo 2 pontos válidos.')

        cor = (dados.get('cor') or '').strip()
        if not _HEX_COR_RE.match(cor):
            cor = '#ffffff'

        espessura = int(_clamp_num(dados.get('espessura'), 1, 12, 3))

        return 'linha', {
            'pontos': pontos,
            'cor': cor,
            'espessura': espessura,
            'tracejado': bool(dados.get('tracejado')),
            'liga_marker_inicio': _marker_id_valido(dados.get('liga_marker_inicio')),
            'liga_marker_fim': _marker_id_valido(dados.get('liga_marker_fim')),
            'descricao': _descricao_segura(dados.get('descricao')),
        }

    # tipo == 'imagem'
    url = _url_imagem_segura(dados.get('url'))
    if not url:
        raise ValueError('Imagem requer uma url válida (/media/, /static/ ou http[s]).')

    bounds_raw = dados.get('bounds')
    if not isinstance(bounds_raw, (list, tuple)) or len(bounds_raw) != 2:
        raise ValueError('Imagem requer bounds = [[lat,lng],[lat,lng]].')
    b0 = _ponto_valido(bounds_raw[0])
    b1 = _ponto_valido(bounds_raw[1])
    if b0 is None or b1 is None:
        raise ValueError('Bounds da imagem inválidos.')

    opacidade = _clamp_num(dados.get('opacidade'), 0.1, 1.0, 1.0)

    return 'imagem', {
        'url': url,
        'bounds': [b0, b1],
        'opacidade': opacidade,
        'descricao': _descricao_segura(dados.get('descricao')),
    }


def desenho_payload(d):
    """Serializa um TbMapDesenho para o front (mesmo padrão de markers)."""
    return {
        'id': d.id_desenho,
        'tipo': d.tipo,
        'camada': d.camada,
        'nome': d.nome or '',
        'ordem': d.ordem,
        'dados_json': d.dados_json or {},
    }


@staff_member_required
@require_POST
def wiki_save_desenho(request):
    """Cria ou atualiza um desenho do mapa. JSON:
    { id?, tipo, camada, nome, dados_json }. Retorna {ok, id}."""
    data = _json_body(request)

    desenho_id = data.get('id')
    if desenho_id in ('', 'null', 'undefined'):
        desenho_id = None

    existente = None
    if desenho_id is not None:
        try:
            existente = TbMapDesenho.objects.filter(pk=int(desenho_id)).first()
        except (TypeError, ValueError):
            existente = None
        if existente is None:
            return JsonResponse({'ok': False, 'error': 'Desenho não encontrado.'}, status=404)

    # Tipo: no update usa o enviado, senão preserva o existente.
    tipo = data.get('tipo') if 'tipo' in data else (existente.tipo if existente else None)
    dados = data.get('dados_json') if 'dados_json' in data else (existente.dados_json if existente else {})

    try:
        tipo_norm, dados_limpos = sanitize_desenho(tipo, dados)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    if existente is None:
        desenho = TbMapDesenho(criado_por=request.user)
    else:
        desenho = existente

    desenho.tipo = tipo_norm
    desenho.dados_json = dados_limpos

    # Update parcial: só sobrescreve os campos enviados no payload.
    if 'camada' in data or existente is None:
        try:
            desenho.camada = int(data.get('camada') or 0)
        except (TypeError, ValueError):
            desenho.camada = desenho.camada if existente else 0
    if 'nome' in data or existente is None:
        desenho.nome = (data.get('nome') or '').strip()[:150]
    if 'ordem' in data:
        try:
            desenho.ordem = int(data.get('ordem') or 0)
        except (TypeError, ValueError):
            pass
    if 'ativo' in data:
        desenho.ativo = bool(data.get('ativo'))

    desenho.save()
    acao = 'Criação' if existente is None else 'Edição'
    _log_wiki_edit(request, desenho, f"{acao} inline de desenho do mapa: {desenho}")
    return JsonResponse({'ok': True, 'id': desenho.id_desenho})


@staff_member_required
@require_POST
def wiki_delete_desenho(request):
    """Remove um desenho do mapa. JSON: { id }. Retorna {ok}."""
    data = _json_body(request)
    desenho_id = data.get('id')
    try:
        desenho = TbMapDesenho.objects.filter(pk=int(desenho_id)).first()
    except (TypeError, ValueError):
        desenho = None
    if desenho is None:
        return JsonResponse({'ok': False, 'error': 'Desenho não encontrado.'}, status=404)
    desenho.delete()
    return JsonResponse({'ok': True})


@staff_member_required
@require_POST
def wiki_upload_map_image(request):
    """Recebe um upload de imagem (multipart) para overlay do mapa, salvo em
    MEDIA 'map_uploads/'. Retorna {ok, url}. PNG/JPG/JPEG/WEBP/GIF, até ~8MB."""
    uploaded = request.FILES.get('imagem') or request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'ok': False, 'error': 'Nenhum arquivo enviado.'}, status=400)

    if uploaded.size > MAP_IMAGE_UPLOAD_MAX_MB * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'A imagem deve ter no máximo %d MB.' % MAP_IMAGE_UPLOAD_MAX_MB}, status=400)

    nome_orig = uploaded.name or ''
    ext = ('.' + nome_orig.split('.')[-1].lower()) if '.' in nome_orig else ''
    content_type = (getattr(uploaded, 'content_type', '') or '').lower()
    if not ext and content_type.startswith('image/'):
        ext = '.' + content_type.split('/', 1)[1].replace('jpeg', 'jpg')
    if ext not in MAP_IMAGE_UPLOAD_EXTENSIONS or not content_type.startswith('image/'):
        return JsonResponse({'ok': False, 'error': 'Envie uma imagem PNG, JPG, WEBP ou GIF.'}, status=400)

    # Nome único por conteúdo+timestamp pra não colidir entre uploads.
    stamp = hashlib.md5(('%s-%s' % (nome_orig, timezone.now().isoformat())).encode('utf-8')).hexdigest()[:12]
    path = 'map_uploads/%s%s' % (stamp, ext)
    saved = default_storage.save(path, ContentFile(uploaded.read()))
    return JsonResponse({'ok': True, 'url': default_storage.url(saved)})
