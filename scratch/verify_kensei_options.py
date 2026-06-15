import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbOpcaojogo, TbAcessoopcao

kensei_opts = TbOpcaojogo.objects.filter(tipo__iexact='Estilos Kensei')
print(f"Total 'Estilos Kensei' options: {kensei_opts.count()}")
for op in kensei_opts:
    acessos = TbAcessoopcao.objects.filter(id_opcao=op)
    info = [f"[Classe: {ac.id_classe.nome if ac.id_classe else 'None'}, Sub: {ac.id_subclasse.nome if ac.id_subclasse else 'None'}]" for ac in acessos]
    print(f"- {op.nome} -> {', '.join(info)}")
