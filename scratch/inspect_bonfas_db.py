import sqlite3

db_path = r"C:\Users\helio\Desktop\Projetos Bonfas\Bonfas\bonfas.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get list of tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables in bonfas.db: {tables}")

# Let's inspect schemas of interesting tables
for table in tables:
    if any(k in table.lower() for k in ['habilidade', 'feature', 'tag', 'classe', 'subclasse']):
        cursor.execute(f"PRAGMA table_info({table});")
        info = cursor.fetchall()
        print(f"\nSchema of {table}:")
        for col in info:
            print(f"  {col[1]} ({col[2]})")

conn.close()
