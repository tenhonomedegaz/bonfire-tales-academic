import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbRaca, TbLinhagem, TbEssencia, TbTracoracial

humano = TbRaca.objects.filter(slug='humano').first()
if humano:
    print("HUMANO:")
    print("Nome:", humano.nome)
    print("Slug:", humano.slug)
    print("Tagline:", humano.tagline)
    print("Lore Presentation:", repr(humano.lore_presentation))
    print("Lore Roleplay:", repr(humano.lore_roleplay))
    print("Lore Society:", repr(humano.lore_society))
    print("Permite Essência:", humano.permite_essencia)
    
    print("\nLINHAGENS:")
    for l in humano.linhagens.all():
        print(f"- {l.nome} ({l.slug})")
        print("  Description:", repr(l.descricao))
        
    print("\nTRAÇOS BASE (not talents):")
    for t in humano.tracos.filter(talento_racial=False):
        print(f"- {t.nome} (Nivel {t.nivel_requisito}) (Linhagem: {t.id_linhagem}) (Essencia: {t.id_essencia})")
        
    print("\nTALENTOS:")
    for t in TbTracoracial.objects.filter(id_raca=humano, talento_racial=True):
        print(f"- {t.nome} (Nivel {t.nivel_requisito}) (Linhagem: {t.id_linhagem}) (Essencia: {t.id_essencia})")
else:
    print("Raça humana não encontrada.")
