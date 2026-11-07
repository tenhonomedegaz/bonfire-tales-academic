"""Render real profile partials over fictional data without a project database."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from django.conf import settings
settings.configure(SECRET_KEY='profile-wall-local-fixture', STATIC_URL='/static/', ROOT_URLCONF=__name__,
    SITE_POSTGRES_TABLES={}, INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'home'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}], USE_TZ=True)
import django
django.setup()
from django import forms
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import path
from home.cosmetic_packages import load_package

def empty(request, **kwargs):
    pass

urlpatterns = [path('jogadores/', empty, name='jogadores'), path('login/', empty, name='login'),
    path('perfil/<str:username>/', empty, name='public_profile'),
    path('perfil/<str:username>/comentarios/', empty, name='perfil_comentar'),
    path('perfil/comentarios/<int:comment_id>/curtir/', empty, name='perfil_comentario_curtir'),
    path('perfil/comentarios/<int:comment_id>/remover/', empty, name='perfil_comentario_remover'),
    path('personagem/<int:pk>/', empty, name='ficha_detail'), path('ficha/<int:pk>/', empty, name='ficha_publica')]

class Composer(forms.Form):
    chave_operacao = forms.UUIDField(widget=forms.HiddenInput, initial='c76ddc09-0d88-4011-b56a-7e86113ad89a')
    texto = forms.CharField(required=True)

owner = NS(username='Aventureiro', pk=1, is_staff=False, is_superuser=False, is_active=True)
visitor = NS(username='Viajante', pk=2, is_authenticated=True, is_active=True)
character = NS(nome='Scar de Cristal', id_personagem=1, publico=True, foto_url='/static/brand/draconic.webp', dono=owner)
rank = {'nome': 'Topázio', 'key': 'topazio', 'icone_url': '/static/icons/ranks/topazio-metal-v1.png', 'open_frame_key': 'elo-topazio-aberta'}
comments = []
for pk, name, message, frame in [
    (1, 'Viajante', 'Que venham as próximas aventuras! **Aquela última mesa** foi inesquecível. 🔥\n\n[Uma lembrança](https://example.com)', 'verdant'),
    (2, 'Contadora de Histórias', '> A fogueira espera novas vozes.\n\nJá estou preparando a próxima sessão! ✨', 'ember-ring'),
    (3, 'Ferreiro', '![Uma lembrança da mesa](/static/brand/world.webp)\n\nUma lembrança de Cinéria para o mural.', 'arcane-pulse')]:
    author = NS(username=name, pk=pk+2)
    comments.append(NS(pk=pk, autor=author, texto=message, criado_em=datetime(2026, 11, 2, 18+pk, 30, tzinfo=timezone.utc),
        avatar_url='/static/brand/human.webp', frame_class='', frame_package=load_package('moldura', frame),
        like_count=3-pk, liked_by_viewer=False, can_like=True, can_remove=pk==1))
context = {'viewed_user': owner, 'request': NS(user=visitor, path='/perfil/Aventureiro/', GET={}),
    'profile': NS(avatar_url='/static/brand/human.webp', banner_url='/static/brand/world.webp', bio='Histórias, amizades e um lugar ao redor da fogueira.'),
    'appearance': {'theme_class': 'theme-bonfire', 'theme_key': 'bonfire', 'frame_key': 'none', 'effect_key': 'none'},
    'community': {'is_master': False}, 'personagens': [{'obj': character, 'raca': 'Orc', 'classe': 'Bárbaro', 'nivel': 12, 'rank': rank, 'frame_package': load_package('moldura', 'elo-topazio-aberta', 'ficha')}],
    'profile_wall': {'comments_page': Paginator(comments, 10).get_page(1), 'comment_form': Composer(), 'can_comment': True},
    'csrf_token': 'local-fixture-token', 'conquistas': {}, 'social': {}}
with patch('home.templatetags.cosmetic_packages.get_package', side_effect=lambda user, kind, key, scope='perfil': load_package(kind, key, scope)):
    hero = render_to_string('home/partials/_perfil_publico_hero.html', context)
styles = ['css/brand.css', 'css/pages/perfil.css', 'css/pages/perfil-fx.css',
    'css/components/cosmetic-presentation.css', 'css/components/character-card.css', 'css/pages/profile-wall.css']
html = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
html += ''.join('<link rel="stylesheet" href="/static/'+css+'">' for css in styles)
html += '<title>Bonfire | Mural do perfil</title><style>body{background:#0c0d0d;color:#f1e5d5;margin:0;font:14px Arial;--text:#f1e5d5;--muted:#b9aaa5;--stroke:#53403f;--bg1:#1b1718;--ember:#efaa72}main{max-width:1050px;margin:32px auto;padding:0 24px}.public-profile-page{margin:0!important;max-width:none!important}*{box-sizing:border-box}@media(max-width:600px){main{padding:0 14px;margin:18px auto}}</style></head><body><main>'+hero+'</main>'
html += '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js" defer></script><script src="/static/js/markdown.js" defer></script><script src="/static/cosmetics/renderer.js" defer></script><script src="/static/js/profile-wall.js" defer></script></body></html>'
print(json.dumps({'html': html}))
