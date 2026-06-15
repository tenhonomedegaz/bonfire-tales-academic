import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbOpcaojogo

def test_query(tipo, subclass_slug):
    qs = TbOpcaojogo.objects.all().order_by('nome')
    if tipo:
        qs = qs.filter(tipo__iexact=tipo)
    if subclass_slug:
        if subclass_slug.lower() == 'null':
            qs = qs.filter(tbacessoopcao__id_subclasse__isnull=True)
        else:
            qs = qs.filter(tbacessoopcao__id_subclasse__slug=subclass_slug)
        qs = qs.distinct()
    
    print(f"Tipo: {tipo}, Subclass: {subclass_slug} -> Count: {qs.count()}")
    for op in qs[:5]:
        print(f"  - {op.nome}")
    if qs.count() > 5:
        print("  ...")

test_query("Infusões do Artífice", "null")
test_query("Infusões do Artífice", "alquimista")
test_query("Infusões do Artífice", "magiduelista")
