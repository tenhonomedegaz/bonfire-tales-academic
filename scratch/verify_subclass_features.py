import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbClassehabilidade, TbSubclasse

art_subs = TbSubclasse.objects.filter(id_classe__slug='artifice')
print(f"Subclasses found: {[s.nome for s in art_subs]}")

for sub in art_subs:
    habs = TbClassehabilidade.objects.filter(id_subclasse=sub)
    print(f"\nSubclass: {sub.nome} ({sub.slug}) - {habs.count()} features:")
    for h in habs:
        print(f"  - {h.nome} (Level {h.niveladquirido})")
        # Check if description has options
        lines = h.descricao.split('\n')
        for line in lines:
            if "::options" in line or "::click" in line:
                print(f"    {line}")
