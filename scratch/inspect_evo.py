import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbEssencia, TbTracoracial

for ess in TbEssencia.objects.all():
    print(f"\nESSENCIA: {ess.nome} ({ess.slug})")
    print("Base Traits (talento_racial=False):")
    for t in ess.tracos.filter(talento_racial=False):
        print(f"  - {t.nome} (Nivel {t.nivel_requisito})")
    print("Talents (talento_racial=True):")
    for t in ess.tracos.filter(talento_racial=True):
        print(f"  - {t.nome} (Nivel {t.nivel_requisito})")
