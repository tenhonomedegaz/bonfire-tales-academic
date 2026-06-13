import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import django

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbSubclasse, TbRecursoclasse, TbClassehabilidade
from django.db import transaction

def main():
    print("Iniciando o patch do Trapaceiro Arcano...")
    
    # 1. Obter Subclasse
    try:
        subclass = TbSubclasse.objects.get(id_subclasse=48)
        print(f"Subclasse encontrada: {subclass.nome} (Classe ID: {subclass.id_classe_id})")
    except TbSubclasse.DoesNotExist:
        print("[ERRO] Subclasse 'Trilha do Trapaceiro Arcano' (ID 48) nao encontrada!")
        return

    # 2. Dados de Progressao do Trapaceiro Arcano (Niveis 3 a 20)
    # Formato: nivel -> {nome_recurso: valor}
    progression = {
        3:  {"Truques": "2", "Magias Preparadas": "4", "1º": "3"},
        4:  {"Truques": "2", "Magias Preparadas": "5", "1º": "3"},
        5:  {"Truques": "2", "Magias Preparadas": "6", "1º": "4", "2º": "2"},
        6:  {"Truques": "2", "Magias Preparadas": "7", "1º": "4", "2º": "2"},
        7:  {"Truques": "2", "Magias Preparadas": "8", "1º": "4", "2º": "3"},
        8:  {"Truques": "2", "Magias Preparadas": "9", "1º": "4", "2º": "3"},
        9:  {"Truques": "2", "Magias Preparadas": "10", "1º": "4", "2º": "3", "3º": "2"},
        10: {"Truques": "3", "Magias Preparadas": "10", "1º": "4", "2º": "3", "3º": "2"},
        11: {"Truques": "3", "Magias Preparadas": "11", "1º": "4", "2º": "3", "3º": "3"},
        12: {"Truques": "3", "Magias Preparadas": "11", "1º": "4", "2º": "3", "3º": "3"},
        13: {"Truques": "3", "Magias Preparadas": "12", "1º": "4", "2º": "3", "3º": "3", "4º": "1"},
        14: {"Truques": "4", "Magias Preparadas": "12", "1º": "4", "2º": "3", "3º": "3", "4º": "1"},
        15: {"Truques": "4", "Magias Preparadas": "13", "1º": "4", "2º": "3", "3º": "3", "4º": "2"},
        16: {"Truques": "4", "Magias Preparadas": "13", "1º": "4", "2º": "3", "3º": "3", "4º": "2"},
        17: {"Truques": "4", "Magias Preparadas": "14", "1º": "4", "2º": "3", "3º": "3", "4º": "3", "5º": "1"},
        18: {"Truques": "4", "Magias Preparadas": "14", "1º": "4", "2º": "3", "3º": "3", "4º": "3", "5º": "1"},
        19: {"Truques": "4", "Magias Preparadas": "15", "1º": "4", "2º": "3", "3º": "3", "4º": "3", "5º": "2"},
        20: {"Truques": "4", "Magias Preparadas": "15", "1º": "4", "2º": "3", "3º": "3", "4º": "3", "5º": "2"},
    }

    # Slugs correspondentes para cada recurso
    slugs = {
        "Truques": "truques",
        "Magias Preparadas": "magias-preparadas",
        "1º": "1o",
        "2º": "2o",
        "3º": "3o",
        "4º": "4o",
        "5º": "5o",
    }

    with transaction.atomic():
        # 3. Remover recursos antigos do Trapaceiro Arcano (se existirem)
        deleted_count, _ = TbRecursoclasse.objects.filter(id_subclasse=subclass).delete()
        print(f"Limpando recursos antigos: {deleted_count} removidos.")

        # 4. Inserir novos recursos
        resources_to_create = []
        for level, recs in progression.items():
            for name, val in recs.items():
                resources_to_create.append(
                    TbRecursoclasse(
                        id_classe=subclass.id_classe,
                        id_subclasse=subclass,
                        nome=name,
                        slug=slugs[name],
                        nivel=level,
                        valor=val
                    )
                )
        TbRecursoclasse.objects.bulk_create(resources_to_create)
        print(f"Inseridos {len(resources_to_create)} novos recursos para a progressao do Trapaceiro Arcano.")

        # 5. Limpar a tabela Markdown da descricao da habilidade "Magia do Trapaceiro" (ID 1268)
        try:
            feature = TbClassehabilidade.objects.get(id_habilidade=1268)
            original_desc = feature.descricao
            if "|" in original_desc:
                new_desc = original_desc.split("|")[0].strip()
                feature.descricao = new_desc
                feature.save()
                print("Descricao da habilidade 'Magia do Trapaceiro' atualizada (tabela Markdown removida).")
            else:
                print("A habilidade 'Magia do Trapaceiro' ja nao possuia tabela Markdown na descricao.")
        except TbClassehabilidade.DoesNotExist:
            print("[AVISO] Habilidade 'Magia do Trapaceiro' (ID 1268) nao encontrada. Ignorando esta etapa.")

    print("Patch concluido com sucesso!")

if __name__ == "__main__":
    main()
