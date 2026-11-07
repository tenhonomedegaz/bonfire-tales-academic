import os
import sys
import re
import docx
import django

# Set up Django environment
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bonfire.settings")
django.setup()

from home.models import TbRegiao

docx_path = r"ref/agrabbar.docx"
if not os.path.exists(docx_path):
    docx_path = r"../ref/agrabbar.docx"

print("Parsing docx at:", os.path.abspath(docx_path))
doc = docx.Document(docx_path)

# List of metadata keys we want to split from paragraph text
METADATA_KEYS = [
    "Função", "Sede", "Símbolo", "Protocolos-chave", "Usar 5e", "Habitat", "Comportamento",
    "Atuação", "Função declarada das Casas", "Função real de parte delas",
    "Protocolos-chave do submundo", "Templo principal", "Comandante atual"
]

keys_regex = r'\b(' + '|'.join(re.escape(k) for k in METADATA_KEYS) + r'):\s*'

def parse_paragraph_metadata(text):
    match = re.search(keys_regex, text, re.IGNORECASE)
    if not match:
        return text.strip(), []
    
    desc = text[:match.start()].strip()
    metadata_part = text[match.start():]
    
    pairs = []
    pattern = r'\b(' + '|'.join(re.escape(k) for k in METADATA_KEYS) + r'):\s*(.*?)(?=\b(?:' + '|'.join(re.escape(k) for k in METADATA_KEYS) + r'):|$)'
    for m in re.finditer(pattern, metadata_part, re.IGNORECASE):
        key = m.group(1).strip()
        val = m.group(2).strip()
        # Clean trailing periods or spaces if followed by another key
        if val.endswith('.') and m.end() < len(metadata_part):
            # If there is another key following, the match might include a dot at the end
            pass
        pairs.append((key, val))
        
    return desc, pairs

markdown_lines = []
current_h1 = None
current_h2 = None

# We can group categories like "Criaturas Comuns", "Criaturas Incomuns", "Criaturas Muito Raras", "Criatura Lendária"
CREATURE_CATEGORIES = {
    "Criaturas Comuns", "Criaturas Incomuns", "Criaturas Muito Raras", "Criatura Lendária", "Criaturas Raras", "Criatura Rara", "Notas para Mestre"
}

for p in doc.paragraphs:
    text = p.text.strip()
    if not text:
        continue
    
    style_name = p.style.name if p.style else "Normal"
    
    if style_name.startswith("Heading 1"):
        current_h1 = text
        current_h2 = None
        markdown_lines.append(f"\n## {text}\n")
    elif style_name.startswith("Heading 2"):
        current_h2 = text
        markdown_lines.append(f"\n### {text}\n")
    else:
        # Standard paragraph
        if current_h1 == "Criaturas Presentes":
            if text in CREATURE_CATEGORIES:
                # This is a creature category header
                markdown_lines.append(f"\n### {text}\n")
            elif ":" in text and len(text.split(":", 1)[0]) <= 40:
                # This is a creature title paragraph (e.g. "Leões Secos: ...")
                name, body = text.split(":", 1)
                markdown_lines.append(f"\n#### {name.strip()}\n")
                desc, pairs = parse_paragraph_metadata(body.strip())
                markdown_lines.append(desc)
                if pairs:
                    markdown_lines.append("")
                    for k, v in pairs:
                        markdown_lines.append(f"- **{k}:** {v}")
                markdown_lines.append("")
            else:
                # Just normal paragraph under creatures
                markdown_lines.append(text)
        else:
            # Normal section
            desc, pairs = parse_paragraph_metadata(text)
            markdown_lines.append(desc)
            if pairs:
                markdown_lines.append("")
                for k, v in pairs:
                    markdown_lines.append(f"- **{k}:** {v}")
            markdown_lines.append("")

# Combine into a single markdown string
markdown_content = "\n".join(markdown_lines).strip()

# Normalize multiple blank lines to a single one
markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)

print("Markdown extraction complete! Sample preview:")
print("\n".join(markdown_content.splitlines()[:50]))
print("...")
print("\n".join(markdown_content.splitlines()[-30:]))

# Update database record
try:
    reg = TbRegiao.objects.filter(slug='nova-regiao').first() or TbRegiao.objects.filter(nome='Agrabbar').first()
    if reg:
        print(f"Found region record: {reg.nome} (id={reg.id_regiao}, slug={reg.slug})")
        reg.nome = "Agrabbar"
        reg.slug = "agrabbar"
        reg.lore_markdown = markdown_content
        reg.save()
        print("Region Agrabbar successfully updated in the database!")
    else:
        print("ERROR: Could not find region record with slug 'nova-regiao' or name 'Agrabbar'.")
except Exception as e:
    print("Database update failed:", e)
