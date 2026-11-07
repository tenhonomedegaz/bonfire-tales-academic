import os
import sys
import re
import django

# Configure Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbRaca, TbLinhagem, TbEssencia, TbTracoracial

def parse_import_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split blocks by '---'
    blocks_raw = content.split('---')
    blocks = []
    for b in blocks_raw:
        b = b.strip()
        if not b:
            continue
        
        # Parse key-value lines
        lines = b.split('\n')
        data = {}
        current_key = None
        current_value = []
        
        for line in lines:
            # Check if line starts with key:
            match = re.match(r'^([A-Za-zÀ-ÿ\s]+):\s*(.*)$', line)
            if match:
                # Save previous key if any
                if current_key:
                    data[current_key] = '\n'.join(current_value).strip()
                current_key = match.group(1).strip()
                val = match.group(2).strip()
                current_value = [val] if val else []
            else:
                if current_key:
                    current_value.append(line)
        
        if current_key:
            data[current_key] = '\n'.join(current_value).strip()
            
        blocks.append(data)
    return blocks

def import_races_and_essences():
    races_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ref', 'raças')
    
    files = {
        'dwarf': 'Anão in Bonfire Tales RPG _ World Anvil_import.txt',
        'elf': 'Elfo in Bonfire Tales RPG _ World Anvil_import.txt',
        'orc': 'Orc in Bonfire Tales RPG _ World Anvil_import.txt',
        'humano': 'Humanos in Bonfire Tales RPG _ World Anvil_import.txt',
        'nephilim': 'Nephilim in Bonfire Tales RPG _ World Anvil_import.txt',
        'vampirismo': 'Vampirismo in Bonfire Tales RPG _ World Anvil_import.txt',
        'draconica': 'Essência Dracônica in Bonfire Tales RPG _ World Anvil_import.txt',
        'elemental': 'Essência Elemental in Bonfire Tales RPG _ World Anvil_import.txt'
    }
    
    # Check that all files exist
    for k, name in files.items():
        path = os.path.join(races_dir, name)
        if not os.path.exists(path):
            print(f"Erro: Arquivo {path} não encontrado!")
            sys.exit(1)
            
    print("Iniciando importação de raças e essências...")
    
    # 1. Limpar registros antigos para evitar duplicidade
    # A deleção em cascata do Django cuidará de apagar linhagens e traços correspondentes.
    print("Removendo raça Folken (folken) antiga...")
    TbRaca.objects.filter(slug='folken').delete()

    print("Removendo raças antigas (Anão, Elfo, Orc, Humano)...")
    TbRaca.objects.filter(slug__in=['anao', 'elfo', 'orc', 'humano']).delete()
    
    print("Removendo essências antigas (Nephilim, Vampirismo, Dracônica, Elemental)...")
    TbEssencia.objects.filter(slug__in=['nephilim', 'vampirismo', 'draconica', 'elemental']).delete()
    
    # 2. Importar os arquivos
    for key_name, file_name in files.items():
        path = os.path.join(races_dir, file_name)
        print(f"\nProcessando arquivo: {file_name}")
        blocks = parse_import_file(path)
        print(f"Encontrados {len(blocks)} blocos de dados.")
        
        for idx, block in enumerate(blocks):
            # Check Tipo
            tipo = block.get('Tipo')
            
            if tipo == 'Raca':
                print(f"Criando Raça: {block.get('Nome')}")
                raca = TbRaca.objects.create(
                    nome=block.get('Nome'),
                    slug=block.get('Slug'),
                    tagline=block.get('Tagline', ''),
                    lore_presentation=block.get('Lore Apresentação'),
                    lore_roleplay=block.get('Lore Roleplay'),
                    lore_society=block.get('Lore Sociedade'),
                    permite_essencia=True
                )
            
            elif tipo == 'Essencia':
                print(f"Criando Essência: {block.get('Nome')}")
                ess = TbEssencia.objects.create(
                    nome=block.get('Nome'),
                    slug=block.get('Slug'),
                    lore_presentation=block.get('Lore Apresentação'),
                    lore_roleplay=block.get('Lore Roleplay'),
                    lore_society=block.get('Lore Sociedade')
                )
                
            elif tipo == 'Linhagem':
                print(f"Criando Linhagem: {block.get('Nome')}")
                raca_slug = block.get('Raça')
                raca = TbRaca.objects.get(slug=raca_slug)
                lin = TbLinhagem.objects.create(
                    id_raca=raca,
                    nome=block.get('Nome'),
                    slug=block.get('Slug'),
                    descricao=block.get('Descricao'),
                    lore_presentation=block.get('Lore Apresentação'),
                    lore_roleplay=block.get('Lore Roleplay'),
                    lore_society=block.get('Lore Sociedade')
                )
                
            else:
                # É um Traço Racial
                nome = block.get('Nome')
                raca_slug = block.get('Raca')
                lin_slug = block.get('Linhagem')
                ess_slug = block.get('Essencia')
                
                raca = TbRaca.objects.filter(slug=raca_slug).first() if raca_slug else None
                linhagem = TbLinhagem.objects.filter(slug=lin_slug).first() if lin_slug else None
                essencia = TbEssencia.objects.filter(slug=ess_slug).first() if ess_slug else None
                
                nivel = int(block.get('Nivel', 0))
                talento = block.get('Talento Racial', 'nao') in ('sim', 'yes', 'true', '1')
                pre_requisito = block.get('Pre Requisito')
                descricao = block.get('Descricao', '')

                # Force physical characteristics and variations to be base traits/lore (skip TbTracoracial creation)
                if nome in [
                    'Características Físicas', 'Variações de Vertente', 'Variações de Linhagem', 
                    'Variações de Clã', 'Características Físicas (Universal)', 'Variações de Clã (Universal)'
                ]:
                    if ess_slug:
                        ess = TbEssencia.objects.filter(slug=ess_slug).first()
                        if ess:
                            header = f"\n\n### {nome}\n"
                            ess.lore_presentation = (ess.lore_presentation or "") + header + descricao
                            ess.save()
                    elif raca_slug:
                        raca_obj = TbRaca.objects.filter(slug=raca_slug).first()
                        if raca_obj:
                            header = f"\n\n### {nome}\n"
                            raca_obj.lore_presentation = (raca_obj.lore_presentation or "") + header + descricao
                            raca_obj.save()
                    continue
                
                # Criar Traço Racial
                TbTracoracial.objects.create(
                    id_raca=raca,
                    id_linhagem=linhagem,
                    id_essencia=essencia,
                    nome=nome,
                    descricao=descricao,
                    nivel_requisito=nivel,
                    talento_racial=talento,
                    pre_requisito=pre_requisito
                )
                
    print("\nImportação de raças e essências concluída com sucesso!")

if __name__ == '__main__':
    import_races_and_essences()
