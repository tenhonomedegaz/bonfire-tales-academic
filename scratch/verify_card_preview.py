import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from django.test import RequestFactory
from home.views import api_card_preview
import json

factory = RequestFactory()

def test_preview(table, args):
    req = factory.get('/api/card-preview/', {'table': table, 'args': args})
    res = api_card_preview(req)
    print(f"Table: {table}, Args: {args} -> Status: {res.status_code}")
    if res.status_code == 200:
        data = json.loads(res.content)
        print(f"  Title: {data.get('title')}")
        print(f"  URL: {data.get('url')}")
        print(f"  Desc snippet: {data.get('description', '')[:100]}...")
    else:
        print(f"  Error: {res.content}")
    print("-" * 50)

# Test class ability
test_preview("tbHabilidade de classe", "artifice, infusoes")
# Test subclass ability
test_preview("tbHabilidade de classe", "alquimista, elixires-alquimicos")
# Test class
test_preview("tbClasse", "artifice")
# Test talent (let's check a talent slug)
from home.models import TbTalento
first_tal = TbTalento.objects.first()
if first_tal:
    test_preview("tbTalento", first_tal.slug)
