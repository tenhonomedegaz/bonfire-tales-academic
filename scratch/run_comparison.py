import sqlite3
import json
import collections

db_site_path = r"C:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\db.sqlite3"
db_bonfas_path = r"C:\Users\helio\Desktop\Projetos Bonfas\Bonfas\bonfas.db"

def get_db_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get classes mapping
    cursor.execute("SELECT Id_Classe, Nome, Slug FROM TB_Classe")
    classes = {row[0]: {'nome': row[1], 'slug': row[2]} for row in cursor.fetchall()}
    
    # Get subclasses mapping
    cursor.execute("SELECT Id_Subclasse, Id_Classe, Nome, Slug FROM TB_Subclasse")
    subclasses = {row[0]: {'id_classe': row[1], 'nome': row[2], 'slug': row[3]} for row in cursor.fetchall()}
    
    # Get abilities
    cursor.execute("SELECT Id_Classe, Id_Subclasse, Nome, NivelAdquirido FROM TB_ClasseHabilidade")
    abilities = []
    for row in cursor.fetchall():
        cls_id, sub_id, name, level = row
        cls_info = classes.get(cls_id, {'nome': 'Unknown', 'slug': ''})
        sub_info = subclasses.get(sub_id, {'nome': 'None', 'slug': ''}) if sub_id else {'nome': 'None', 'slug': ''}
        abilities.append({
            'class': cls_info['nome'],
            'class_slug': cls_info['slug'],
            'subclass': sub_info['nome'],
            'subclass_slug': sub_info['slug'],
            'name': name,
            'level': level
        })
        
    conn.close()
    return abilities

def analyze_tags(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find all columns containing 'tag' in any table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    tag_data = collections.defaultdict(list)
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [col[1] for col in cursor.fetchall()]
        
        # Check for tags column
        tag_cols = [c for c in cols if 'tag' in c.lower() and 'tagline' not in c.lower()]
        if tag_cols:
            for col in tag_cols:
                cursor.execute(f"SELECT [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL AND [{col}] != ''")
                for (val,) in cursor.fetchall():
                    # Parse JSON or clean string
                    tags = []
                    val_str = str(val).strip()
                    if val_str.startswith('[') and val_str.endswith(']'):
                        try:
                            tags = json.loads(val_str)
                        except Exception:
                            # Split by comma as fallback
                            tags = [t.strip() for t in val_str.strip('[]').split(',') if t.strip()]
                    else:
                        # Split by comma or semicolon
                        tags = [t.strip() for t in val_str.replace(';', ',').split(',') if t.strip()]
                    
                    for t in tags:
                        if isinstance(t, dict):
                            # Handle structured tag dictionary if any
                            tag_data[f"{table}.{col}"].append(str(t))
                        else:
                            tag_data[f"{table}.{col}"].append(str(t).strip())
                            
    conn.close()
    
    # Remove duplicates and sort
    final_tags = {}
    for key, val in tag_data.items():
        final_tags[key] = sorted(list(set(val)))
    return final_tags

print("Reading site database...")
site_abs = get_db_data(db_site_path)
print(f"Loaded {len(site_abs)} abilities from site database.")

print("Reading bonfas database...")
bonfas_abs = get_db_data(db_bonfas_path)
print(f"Loaded {len(bonfas_abs)} abilities from bonfas.db.")

print("Analyzing tags in bonfas.db...")
tags_map = analyze_tags(db_bonfas_path)
print("Finished analyzing tags.")

# Compare abilities
site_keys = {}
for ab in site_abs:
    key = (ab['class'].lower(), ab['subclass'].lower(), ab['name'].lower(), ab['level'])
    site_keys[key] = ab

bonfas_keys = {}
for ab in bonfas_abs:
    key = (ab['class'].lower(), ab['subclass'].lower(), ab['name'].lower(), ab['level'])
    bonfas_keys[key] = ab

all_keys = sorted(list(set(site_keys.keys() | bonfas_keys.keys())))

# Group compared abilities by class/subclass
grouped_comparison = collections.defaultdict(list)
for key in all_keys:
    in_site = key in site_keys
    in_bonfas = key in bonfas_keys
    
    info = site_keys[key] if in_site else bonfas_keys[key]
    grp_key = (info['class'], info['subclass'])
    
    status = ""
    if in_site and in_bonfas:
        status = "Both"
    elif in_site:
        status = "Site Only"
    else:
        status = "Bonfas Only"
        
    grouped_comparison[grp_key].append({
        'name': info['name'],
        'level': info['level'],
        'status': status
    })

# Format comparison as Markdown
output_md = []
output_md.append("# Database Abilities & Tags Comparison Report\n")
output_md.append(f"- **Site Database:** `{db_site_path}`")
output_md.append(f"- **Bonfas Project Database:** `{db_bonfas_path}`\n")

output_md.append("## 1. Class Abilities Mapping\n")
output_md.append("Below is the mapping of class and subclass abilities. It compares what exists on the current site vs. the `bonfas.db` project database.\n")

for (cls_name, sub_name), items in sorted(grouped_comparison.items()):
    output_md.append(f"### {cls_name} - Subclass: {sub_name}")
    output_md.append("| Ability Name | Level | Status |")
    output_md.append("| :--- | :---: | :--- |")
    for item in sorted(items, key=lambda x: (x['level'], x['name'])):
        status_label = item['status']
        if status_label == "Both":
            status_text = "✅ Both DBs"
        elif status_label == "Site Only":
            status_text = "🌐 Site Only"
        else:
            status_text = "📦 Bonfas Only"
        output_md.append(f"| {item['name']} | {item['level']} | {status_text} |")
    output_md.append("\n")

output_md.append("## 2. Tags Mapping in Bonfas Project\n")
output_md.append("Below are all the tags found in `bonfas.db` grouped by Table and Column:\n")

for field, tags in sorted(tags_map.items()):
    output_md.append(f"### Table & Column: `{field}`")
    if not tags:
        output_md.append("*No tags found or column is empty.*\n")
        continue
    # Render tags as a bullet list
    for tag in tags:
        output_md.append(f"- `{tag}`")
    output_md.append("\n")

# Write report to file
report_path = r"C:\Users\helio\.gemini\antigravity\brain\e44df8ce-ba28-4796-9714-9e8e4ffa1ba2\db_comparison_report.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_md))

print(f"Report written to {report_path}")
