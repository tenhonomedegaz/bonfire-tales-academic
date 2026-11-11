import os
import bs4
from bs4 import BeautifulSoup

file_path = r"c:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\Classes\Artificer in Bonfire Tales RPG _ World Anvil.html"
content = open(file_path, "r", encoding="utf-8").read()
soup = BeautifulSoup(content, "html.parser")

def inspect_div(target_id):
    div = soup.find(id=target_id)
    if not div:
        print(f"Div {target_id} not found")
        return
    print(f"=== INSPECTING DIV {target_id} ===")
    
    # Recursively find headings and tables
    for child in div.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "table"]):
        print(f"Tag: {child.name}")
        if child.name.startswith("h"):
            print(f"  Content: {child.text.strip()}")
        elif child.name == "table":
            rows = child.find_all("tr")
            print(f"  Table rows count: {len(rows)}")
            for r in rows[:3]:
                cells = [c.text.strip() for c in r.find_all(["td", "th"])]
                print(f"    Row: {cells}")

inspect_div("spoiler-1OSxq9")
inspect_div("spoiler-10v8JW")
