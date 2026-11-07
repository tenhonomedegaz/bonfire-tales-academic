"""Isolated presentation fixture: no .env, project database, grants or sales."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from django.conf import settings
settings.configure(SECRET_KEY='rank-metal-presentation-fixture', STATIC_URL='/static/', SITE_POSTGRES_TABLES={},
    INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
    TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
if '--test' in sys.argv:
    from django.test.runner import DiscoverRunner
    sys.exit(bool(DiscoverRunner(verbosity=1).run_tests(['home.test_rank_metal_presentation','home.test_collaborator_icons','home.test_cosmetic_packages','home.test_cosmetic_retraction'])))
from home.cosmetic_packages import load_package
from home.character_engine import rank_icone_url
root=Path(__file__).resolve().parents[2]
catalog=json.loads((root/'docs/cosmetics/rank-metal-catalog.json').read_text(encoding='utf-8'))
for row in catalog['cosmetics']:
    key=row['slug'].removeprefix('tema-rank-')
    row['icon']=rank_icone_url(row['nome'].removeprefix('Rank '))
    row['open']=load_package('moldura',f'elo-{key}-aberta')
    row['closed']=load_package('moldura',f'elo-{key}-fechada')
print(json.dumps(catalog))
