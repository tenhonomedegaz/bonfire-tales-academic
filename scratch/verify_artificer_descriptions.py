import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbClassehabilidade

# Find abilities matching names
habs = TbClassehabilidade.objects.filter(id_classe__slug='artifice', nome__icontains='infus')
print(f"Total matching abilities: {habs.count()}")
for h in habs:
    print(f"Ability: {h.nome} (Subclass: {h.id_subclasse.nome if h.id_subclasse else 'None'})")
    print(f"Description snippet:")
    lines = h.descricao.split('\n')
    for line in lines:
        if "::options" in line or "::click" in line or "::opcoes" in line:
            print(f"  {line}")
    print("-" * 50)
