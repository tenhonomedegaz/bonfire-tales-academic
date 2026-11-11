import sqlite3

db_bonfas_path = r"C:\Users\helio\Desktop\Projetos Bonfas\Bonfas\bonfas.db"
conn = sqlite3.connect(db_bonfas_path)
cursor = conn.cursor()

# Inspect TB_Subclasse tags
cursor.execute("SELECT Nome, TagsJSON FROM TB_Subclasse WHERE TagsJSON IS NOT NULL AND TagsJSON != '' LIMIT 5")
print("=== TB_Subclasse TagsJSON sample ===")
for name, tags in cursor.fetchall():
    print(f"Subclass: {name}")
    print(f"  Raw: {tags}")

# Inspect TB_ClasseHabilidade tags
cursor.execute("SELECT Nome, TagsJSON FROM TB_ClasseHabilidade WHERE TagsJSON IS NOT NULL AND TagsJSON != '' LIMIT 5")
print("\n=== TB_ClasseHabilidade TagsJSON sample ===")
for name, tags in cursor.fetchall():
    print(f"Ability: {name}")
    print(f"  Raw: {tags}")

conn.close()
