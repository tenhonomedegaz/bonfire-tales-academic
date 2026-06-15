import os
import sys
import django

# Add current working directory to python path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbOpcaojogo, TbAcessoopcao

# Find options of type "Infusões do Artífice"
infusoes = TbOpcaojogo.objects.filter(tipo__iexact='Infusões do Artífice')
print(f"Total options of type 'Infusões do Artífice': {infusoes.count()}")

for op in infusoes.order_by('nome'):
    acessos = TbAcessoopcao.objects.filter(id_opcao=op)
    acessos_info = []
    for ac in acessos:
        classe_nome = ac.id_classe.nome if ac.id_classe else "None"
        sub_nome = ac.id_subclasse.nome if ac.id_subclasse else "None"
        acessos_info.append(f"[Classe: {classe_nome}, Subclasse: {sub_nome}]")
    print(f"- {op.nome} (Req: {op.pre_requisito}) -> {', '.join(acessos_info)}")
