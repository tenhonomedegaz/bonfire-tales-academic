"""Loopback-only demo using the real lab endpoints and ephemeral fictional data.

Never loads project settings, .env, a saved login or a configured project DB.
Run: py -3.14 home/js_tests/vtt_lab_fixture.py --port 8901
"""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from types import SimpleNamespace
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from django.conf import settings
settings.configure(
    SECRET_KEY='fictional-local-vtt-fixture-not-a-project-key', DEBUG=False, USE_TZ=True,
    VTT_LAB_ENABLED=True, ROOT_URLCONF=__name__, ALLOWED_HOSTS=['127.0.0.1', 'localhost'],
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'home'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}],
    MIDDLEWARE=[__name__ + '.FixtureAdminMiddleware', 'django.middleware.csrf.CsrfViewMiddleware'],
    STATIC_URL='/static/', CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.urls import path, re_path
from django.views.static import serve
from home import vtt_lab as lab
from home.models import TbPersonagem
from home.test_vtt_lab import bootstrap_isolated_schema
from home.tag_engine.library import Library

ADMIN = None

class FixtureAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = ADMIN
        return self.get_response(request)

urlpatterns = [
    path('vtt/laboratorio/', lab.laboratory, name='vtt_lab'),
    path('vtt/laboratorio/api/sessoes/', lab.sessions, name='vtt_lab_sessions'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/', lab.session_snapshot, name='vtt_lab_session'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/medir/', lab.measure, name='vtt_lab_measure'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/caminho/', lab.movement_preview, name='vtt_lab_movement_preview'),
    path('vtt/laboratorio/api/sessoes/<uuid:session_id>/comandos/', lab.commands, name='vtt_lab_commands'),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': ROOT / 'home/static'}),
    path('favicon.ico', lambda request: HttpResponse(status=204)),
]

def fictional_export(character):
    return {'versao_contrato': 1, 'versao_menor': 1,
        'personagem': {'pk': character.pk, 'nome': character.nome, 'nivel_total': 5, 'classes': []},
        'derive': {'ca': 16, 'pv_max': 42, 'pb': 3, 'atributos': {},
                   'movimento': {'schema': 1, 'unit': 'ft', 'speeds': {'walk': 30}, 'warnings': []}},
        'estado_mesa': {'pv_atual': 42, 'pv_temp': 0, 'morte_s': 0, 'morte_f': 0},
        'habilidades': [], 'magias': [],
        'acesso_magias': {'schema':1,'catalogo':{'tipo':'atual','identidade':'spell-catalog'},
            'conjuracao_automatica':False,'avisos':[], 'magias':[
                {'magia_pk':1,'slug':'fulgor-de-teste','nome':'Fulgor de teste','circulo':1,
                 'preparada':True,'sempre_preparada':True,'concedida':True,'persistida':False,
                 'fontes':[{'tipo':'concedida','fonte':'Fonte de teste','sempre_preparada':True}],
                 'tags_disponiveis':True,'tags':['instant{dmg:1d6(fogo)}']}]},
        'recursos': [
            {'id_fonte': 'tag:foco', 'nome': 'Foco', 'max': 2, 'reset': 'long-rest'}],
        'avisos': ['Dados ficticios da previa local. Acerto e dano declarados manualmente.']}

def fictional_rules(character, exported):
    return {'defensive_tags': [], 'offensive_tags': [], 'tag_context': {},
        'actions': [{'id': 'manual', 'nome': 'Ataque declarado', 'tags': []},
                    {'id': 'focused', 'nome': 'Golpe concentrado', 'tags': ['instant{resource_cost:foco:1}']}],
        'warnings': ['Cobertura parcial: acerto, dano e distancia sao declarados na mesa.']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8901)
    args = parser.parse_args()
    bootstrap_isolated_schema()
    ADMIN = get_user_model().objects.create(username='Admin de demonstracao', is_superuser=True, is_staff=True)
    # bulk_create bypasses profile/character save hooks; every record is fictional.
    character = TbPersonagem(nome='Sentinela de teste', dono=ADMIN, foto_url='/static/brand/human.webp')
    TbPersonagem.objects.bulk_create([character])
    creature = SimpleNamespace(pk=1, nome='Guardiao da brasa', slug='guardiao-de-teste', escala_com_dono=False,
        pv='30', ca='13', tags_json=['always_active', 'resist:fogo'],
        statblock_json={'hp': {'average': 30}, 'speed': {'walk': 30}, 'actions': [{'name': 'Golpe', 'tags_json': []}]},
        imagem_url='/static/brand/draconic.webp')
    with ExitStack() as stack:
        stack.enter_context(patch.object(lab, 'exportar_personagem', side_effect=fictional_export))
        stack.enter_context(patch.object(lab, 'character_rules', side_effect=fictional_rules))
        stack.enter_context(patch.object(lab.TbBestiario.objects, 'get', return_value=creature))
        stack.enter_context(patch.object(lab, 'Library', side_effect=lambda: Library(prefer_db=False)))
        with make_server('127.0.0.1', args.port, get_wsgi_application()) as server:
            print(json.dumps({'url': f'http://127.0.0.1:{args.port}/vtt/laboratorio/',
                              'fixture_character_id': character.pk, 'database': 'SQLite memory only'}), flush=True)
            server.serve_forever()
