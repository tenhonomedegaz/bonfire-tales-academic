"""Render the installed package/partial without loading .env or a project DB."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from django.conf import settings
settings.configure(SECRET_KEY='isolated-cosmetic-fixture',STATIC_URL='/static/',
    INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','home'],
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}},
    TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}])
import django
django.setup()
from home.cosmetic_packages import load_package
from django.template.loader import get_template

if '--test' in sys.argv:
    from django.test.runner import DiscoverRunner
    sys.exit(bool(DiscoverRunner(verbosity=1).run_tests([
        'home.test_cosmetic_sequences','home.test_cosmetic_rigs',
        'home.test_cosmetic_masks','home.test_cosmetic_backdrop_timing'])))

pack=load_package('efeito','vigilia-das-lanternas')
assert pack,'The approved production package must pass the real validator'
assert len(pack['banner'])==8
print(json.dumps({'package':pack,'html':get_template('home/partials/_cosmetic_preview.html').render({'layers':pack['banner'],'slot':'banner'})}))
