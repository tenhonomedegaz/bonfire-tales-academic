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
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import escape, format_html, format_html_join
from django.utils import timezone
from django.db import transaction
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .bot_mongo import BotMongoUnavailable, find_published_quests, serialize_document
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
)
from .security import validate_no_sql_danger


SITE_COLLECTIONS = {
    'classes': settings.SITE_MONGO_COLLECTIONS.get('classes', 'site_sqlite_TB_Classe'),
    'subclasses': settings.SITE_MONGO_COLLECTIONS.get('subclasses', 'site_sqlite_TB_Subclasse'),
    'class_features': settings.SITE_MONGO_COLLECTIONS.get('class_features', 'site_sqlite_TB_ClasseHabilidade'),
    'class_resources': settings.SITE_MONGO_COLLECTIONS.get('class_resources', 'site_sqlite_TB_RecursoClasse'),
    'races': settings.SITE_MONGO_COLLECTIONS.get('races', 'site_sqlite_TB_Raca'),
    'lineages': settings.SITE_MONGO_COLLECTIONS.get('lineages', 'site_sqlite_TB_Linhagem'),
    'essences': settings.SITE_MONGO_COLLECTIONS.get('essences', 'site_sqlite_TB_Essencia'),
    'racial_traits': settings.SITE_MONGO_COLLECTIONS.get('racial_traits', 'site_sqlite_TB_TracoRacial'),
    'map_markers': settings.SITE_MONGO_COLLECTIONS.get('map_markers', 'site_sqlite_TB_MapMarker'),
    'regions': settings.SITE_MONGO_COLLECTIONS.get('regions', 'site_sqlite_TB_Regiao'),
    'territories': settings.SITE_MONGO_COLLECTIONS.get('territories', 'site_sqlite_TB_Territorio'),
    'talents': settings.SITE_MONGO_COLLECTIONS.get('talents', 'site_sqlite_TB_Talento'),
    'options': settings.SITE_MONGO_COLLECTIONS.get('options', 'site_sqlite_TB_OpcaoJogo'),
    'backgrounds': settings.SITE_MONGO_COLLECTIONS.get('backgrounds', 'backgrounds'),
    'spells': settings.SITE_MONGO_COLLECTIONS.get('spells', 'spells'),
    'bestiary': settings.SITE_MONGO_COLLECTIONS.get('bestiary', 'bestiary'),
    'organizations': settings.SITE_MONGO_COLLECTIONS.get('organizations', 'organizations'),
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


def _mongo_collection(key):
    raise BotMongoUnavailable("Acesso Mongo legado foi removido; use PostgreSQL.")


def _mongo_docs(key, sort=None, query=None):
    cursor = _mongo_collection(key).find(query or {})
    if sort:
        cursor = cursor.sort(sort)
    return [serialize_document(document) for document in cursor]


def _mongo_one(key, query):
    document = _mongo_collection(key).find_one(query)
    return serialize_document(document) if document else None


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
            return redirect("home")
    else:
        form = StaffSignupForm()

    return render(request, "home/register.html", {
        "form": form,
    })


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
            new_avatar = request.POST.get('avatar_url', '').strip()

            if new_username and new_username != user.username:
                User = get_user_model()
                if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                    errors.append('Esse nome de usuário já está em uso.')
                elif len(new_username) < 3:
                    errors.append('O nome de usuário deve ter pelo menos 3 caracteres.')
                elif len(new_username) > 30:
                    errors.append('O nome de usuário deve ter no máximo 30 caracteres.')
                else:
                    user.username = new_username
                    user.save()
                    messages.append('Nome de usuário atualizado!')

            profile.avatar_url = new_avatar or None
            profile.save()
            if not errors:
                messages.append('Perfil salvo com sucesso!')

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

    return render(request, 'home/pages/perfil.html', {
        'profile': profile,
        'success_messages': messages,
        'error_messages': errors,
    })


def classes_view(request):
    return _sqlite_classes_view(request)


def _sqlite_classes_view(request):
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


def classe_detail_view(request, slug):
    return _sqlite_classe_detail_view(request, slug)


def _sqlite_classe_detail_view(request, slug):
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
        ('Ferramentas', classe.multiclass_ferramentas),
        ('Armaduras', classe.multiclass_armaduras),
    ]
    multiclass_traits = [{'label': label, 'value': value} for label, value in multiclass_traits if value]

    columns = []
    seen_columns = set()
    recursos = TbRecursoclasse.objects.filter(
        id_classe=classe,
    ).select_related('id_subclasse').order_by('id_subclasse_id', 'id_recurso')

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

    habilidades_para_tabela = list(base_habilidades_qs)
    habilidades_para_tabela.extend(list(subclass_habilidades_qs))

    habilidades_por_nivel = {}
    for habilidade in habilidades_para_tabela:
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

    progression_table = []
    for nivel in range(1, 21):
        recs_nivel = {}
        subclass_recs_nivel = {}
        for nome, valor in TbRecursoclasse.objects.filter(
            id_classe=classe,
            id_subclasse__isnull=True,
            nivel=nivel,
        ).values_list('nome', 'valor'):
            recs_nivel.setdefault(nome, valor)

        for nome, valor, subclasse_slug in TbRecursoclasse.objects.filter(
            id_classe=classe,
            id_subclasse__isnull=False,
            nivel=nivel,
        ).select_related('id_subclasse').values_list('nome', 'valor', 'id_subclasse__slug'):
            subclass_recs_nivel.setdefault(nome, []).append((valor, subclasse_slug))

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
    return _sqlite_racas_view(request)


def _sqlite_racas_view(request):
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


def raca_detail_view(request, slug):
    return _sqlite_raca_detail_view(request, slug)


def _sqlite_raca_detail_view(request, slug):
    raca = get_object_or_404(TbRaca, slug=slug)
    racas = TbRaca.objects.all().order_by('nome')
    tracos_base = raca.tracos.all().order_by('nivel_requisito', 'nome')
    linhagens = raca.linhagens.all().prefetch_related('tracos_linhagem').order_by('nome')

    context = {
        'raca': raca,
        'all_racas': racas,
        'selected_raca_id': raca.id_raca,
        'tracos_base': tracos_base,
        'linhagens': linhagens,
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

    mongo_error = ''
    quests = []
    try:
        raw_quests = find_published_quests(search=search, status=status)
    except BotMongoUnavailable as exc:
        mongo_error = str(exc)
        raw_quests = []

    for quest in raw_quests:
        subscribed_players = quest.get('subscribedPlayers') or []
        quest_players = quest.get('questPlayers') or []
        players_amount = quest.get('playersAmount') or 0
        quest_date = _parse_mongo_date(quest.get('questDate'))
        quests.append({
            'id': quest.get('_id'),
            'name': quest.get('name') or 'Missao sem nome',
            'description': quest.get('description') or '',
            'quest_date': quest_date,
            'players_amount': players_amount,
            'filled_slots': len(quest_players),
            'queue_amount': len(subscribed_players),
            'status': quest.get('status') or 'idle',
            'type': quest.get('type') or '',
            'tags': quest.get('tags') or [],
            'quest_master': quest.get('questMaster') or '',
            'table_url': quest.get('tableUrl') or '',
            'discord_url': _quest_discord_url(quest),
            'is_full': bool(players_amount and len(quest_players) >= players_amount),
        })

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
    talent.pre_requisito = (data.get('pre_requisito') or '').strip() or None
    talent.descricao = data.get('descricao') or ''
    for attr in ('atrib_forca', 'atrib_destreza', 'atrib_constituicao', 'atrib_inteligencia', 'atrib_sabedoria', 'atrib_carisma'):
        setattr(talent, attr, bool(data.get(attr)))
    talent.save()
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
    opcao.pre_requisito = (data.get('pre_requisito') or '').strip() or None
    opcao.descricao = data.get('descricao') or ''
    opcao.save()
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
    feature.save()
    return JsonResponse({
        'ok': True,
        'feature': {
            'id': feature.id_habilidade,
            'nome': feature.nome,
            'niveladquirido': feature.niveladquirido,
            'descricao': feature.descricao,
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
    trait.save()
    return JsonResponse({
        'ok': True,
        'trait': {
            'id': trait.id_traco,
            'nome': trait.nome,
            'nivel_requisito': trait.nivel_requisito,
            'talento_racial': trait.talento_racial,
            'pre_requisito': trait.pre_requisito or '',
            'descricao': trait.descricao,
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
                'lore_url': _marker_lore_url(marker.get('Nome') or '', ''),
            }
            for marker in marcadores_docs
        ]
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
            'lore_url': _marker_lore_url(m.nome, ''),
        })

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

    regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
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

    territories_by_name = {t.nome: t for t in TbTerritorio.objects.all()}
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
        territorios_cards.append({
            'nome': territory_name,
            'display_nome': _display_territory(territory_name),
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


def regiao_detail_view(request, slug):
    regiao = get_object_or_404(TbRegiao, slug=slug)

    
    marker = TbMapMarker.objects.filter(nome=regiao.nome).first()

    
    all_regioes = TbRegiao.objects.all().order_by('territorio', 'nome')
    territorios = {}
    for r in all_regioes:
        terr = r.territorio or 'Sem território'
        territorios.setdefault(terr, []).append(r)
    territory_objects = {t.nome: t for t in TbTerritorio.objects.all()}
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
                        marker = TbMapMarker.objects.create(nome=nome, lat=lat, lng=lng, categoria=categoria, territorio=territorio)
                        
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
                                territorio=territorio
                            )
                
                
                marker.nome = nome 
                marker.lat = lat
                marker.lng = lng
                marker.categoria = categoria
                marker.territorio = territorio
                marker.save()
                _mongo_upsert_site_document('map_markers', 'Id_Marker', marker.id_marker, {
                    'Nome': marker.nome,
                    'Latitude': marker.lat,
                    'Longitude': marker.lng,
                    'Categoria': marker.categoria,
                    'Territorio': marker.territorio,
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
                    region.save()
                    _mongo_upsert_site_document('regions', 'Id_Regiao', region.id_regiao, {
                        'Nome': region.nome,
                        'Slug': region.slug,
                        'Categoria': region.categoria,
                        'Territorio': region.territorio,
                        'LoreMarkdown': region.lore_markdown,
                        'BrasaoUrl': region.brasao_url,
                        'MapaUrl': region.mapa_url,
                        'EtiquetasAdicionais': region.etiquetas_adicionais,
                    })
                else:
                    
                    r_obj = TbRegiao.objects.filter(nome=nome).first()
                    if not r_obj:
                        new_slug = slugify(nome) or 'unnamed'
                        if TbRegiao.objects.filter(slug=new_slug).exists():
                            import uuid
                            new_slug += f"-{uuid.uuid4().hex[:6]}"
                        r_obj = TbRegiao.objects.create(nome=nome, slug=new_slug)
                    r_obj.categoria = categoria
                    r_obj.territorio = territorio
                    r_obj.save()
                    _mongo_upsert_site_document('regions', 'Id_Regiao', r_obj.id_regiao, {
                        'Nome': r_obj.nome,
                        'Slug': r_obj.slug,
                        'Categoria': r_obj.categoria,
                        'Territorio': r_obj.territorio,
                        'LoreMarkdown': r_obj.lore_markdown,
                        'BrasaoUrl': r_obj.brasao_url,
                        'MapaUrl': r_obj.mapa_url,
                        'EtiquetasAdicionais': r_obj.etiquetas_adicionais,
                    })
                    
            
            for t_data in data.get('territories', []):
                t_id = t_data.get('id')
                if not t_id or t_id in ['undefined', 'null', '']: continue
                territory = get_object_or_404(TbTerritorio, pk=t_id)
                if 'coordenadas_poligono' in t_data:
                    territory.coordenadas_poligono = t_data.get('coordenadas_poligono')
                    territory.save()
                    _mongo_upsert_site_document('territories', 'Id_Territorio', territory.id_territorio, {
                        'Nome': territory.nome,
                        'Slug': territory.slug,
                        'DescricaoBreve': territory.descricao_breve,
                        'ImagemUrl': territory.imagem_url,
                        'CoordenadasPoligono': territory.coordenadas_poligono,
                        'CorHex': territory.cor_hex,
                        'LoreMarkdown': territory.lore_markdown,
                    })
                    
        return JsonResponse({'ok': True})
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        with open('batch_save_error.log', 'w') as f:
            f.write(error_msg)
        print("ERROR IN BATCH SAVE:", error_msg)
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)




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
        'tags': [level_label] + _split_catalog_list(_doc_value(document, ['Classes', 'classes'])) + _split_catalog_list(_doc_value(document, ['Subclasses', 'subclasses'])),
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
    return _render_catalog(
        request,
        'Antecedentes',
        'Origens, oficios, vinculos e escolhas de historia para personagens.',
        'antecedentes',
        'backgrounds',
        _background_payload,
    )


def magias_view(request):
    return _render_catalog(
        request,
        'Magias',
        'Lista de magias com nivel, escola, componentes, ritual e concentracao.',
        'magias',
        'spells',
        _spell_payload,
    )


def bestiario_view(request):
    return _render_catalog(
        request,
        'Bestiario',
        'Criaturas, monstros, adversarios e blocos de estatistica para mestres.',
        'bestiario',
        'bestiary',
        _bestiary_payload,
    )


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
    armas = [i for i in itens if i.categoria == 'arma']
    armaduras = [i for i in itens if i.categoria == 'armadura']
    ferramentas = [i for i in itens if i.categoria == 'ferramenta']
    pacotes = [i for i in itens if i.categoria == 'pacote']
    equipamentos = [i for i in itens if i.categoria == 'equipamento_aventura']
    
    context = {
        'title': 'Itens Mundanos',
        'armas': armas,
        'armaduras': armaduras,
        'ferramentas': ferramentas,
        'pacotes': pacotes,
        'equipamentos': equipamentos,
    }
    
    if is_ajax(request):
        return render(request, 'home/partials/itens_mundanos_content.html', context)
    return render(request, 'home/pages/itens_mundanos.html', context)


def itens_magicos_view(request):
    itens = TbItemMagico.objects.all().order_by('raridade', 'nome')
    
    context = {
        'title': 'Itens Mágicos',
        'itens': itens,
    }
    
    if is_ajax(request):
        return render(request, 'home/partials/itens_magicos_content.html', context)
    return render(request, 'home/pages/itens_magicos.html', context)
