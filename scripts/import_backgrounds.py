import os
import sys
import re
import django
from bs4 import BeautifulSoup

# Configure Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

from home.models import TbAntecedente
from django.utils.text import slugify

html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ref', 'Antecedentes in Bonfire Tales RPG.html')

if not os.path.exists(html_path):
    print(f"Erro: Arquivo {html_path} não encontrado!")
    sys.exit(1)

print("Iniciando importação de antecedentes...")

with open(html_path, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

table = soup.find('table', class_='table-striped')
if not table:
    print("Erro: Tabela com classe 'table-striped' não encontrada no HTML!")
    sys.exit(1)

rows = table.find_all('tr')
print(f"Total de linhas encontradas: {len(rows)} (incluindo cabeçalho).")

# Limpa antecedentes antigos
print("Limpando tabela backgrounds no PostgreSQL...")
deleted_count = TbAntecedente.objects.all().delete()[0]
print(f"{deleted_count} antecedentes antigos deletados.")

imported_count = 0

for row in rows:
    cols = row.find_all('td')
    if not cols:
        continue # Pula cabeçalho ou linhas vazias
    
    nome = cols[0].get_text(strip=True)
    slug = slugify(nome)
    
    # 1. Habilidade
    hab_div = cols[1].find(class_='spoiler-content') or cols[1].find(class_='card-body')
    habilidade = hab_div.get_text(strip=True) if hab_div else cols[1].get_text(strip=True)
    
    # 2. Lore/Descrição
    desc_div = cols[2].find(class_='spoiler-content') or cols[2].find(class_='card-body')
    desc_html = desc_div.decode_contents() if desc_div else cols[2].decode_contents()
    desc_soup = BeautifulSoup(desc_html, 'html.parser')
    
    quote = ""
    b_tag = desc_soup.find('b')
    if b_tag and '"' in b_tag.get_text():
        quote = b_tag.get_text(strip=True)
        b_tag.decompose()
        
    lore_text = desc_soup.get_text(separator='\n').strip()
    lore_text = re.sub(r'\n+', '\n', lore_text)
    
    # Montar a descrição formatada em Markdown
    markdown_content = []
    if quote:
        markdown_content.append(f'*{quote}*')
        markdown_content.append('') # linha em branco
    
    if lore_text:
        markdown_content.append(lore_text)
        markdown_content.append('') # linha em branco
        
    markdown_content.append('### Habilidade do Antecedente')
    markdown_content.append(habilidade)
    
    final_descricao = '\n'.join(markdown_content)
    
    # Criar objeto
    TbAntecedente.objects.create(
        nome=nome,
        slug=slug,
        tipo='Antecedente',
        descricao=final_descricao,
        resumo=quote or (lore_text[:200] + '...' if len(lore_text) > 200 else lore_text),
    )
    imported_count += 1

print(f"Importação concluída com sucesso! {imported_count} antecedentes criados.")
