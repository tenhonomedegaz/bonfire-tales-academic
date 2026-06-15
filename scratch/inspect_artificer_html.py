import os
from bs4 import BeautifulSoup

file_path = r"c:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\Classes\Artificer in Bonfire Tales RPG _ World Anvil.html"
content = open(file_path, "r", encoding="utf-8").read()
soup = BeautifulSoup(content, "html.parser")

# Find references to Elixir and Varinha options
for btn in soup.find_all("a", class_="spoiler-button"):
    btn_text = btn.text.strip()
    if "infus" in btn_text.lower() or "elixir" in btn_text.lower() or "varinha" in btn_text.lower():
        print(f"Button: {btn_text}")
        href = btn.get("href") or ""
        target = btn.get("data-bs-target") or btn.get("data-target") or ""
        target_id = href.split("#")[-1] if "#" in href else target.replace("#", "")
        print(f"Target ID: {target_id}")
        target_div = soup.find(id=target_id)
        if target_div:
            # Print headings inside target_div
            headings = target_div.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            print(f"  Headings: {[h.name + ': ' + h.text.strip() for h in headings[:10]]}")
            tables = target_div.find_all("table")
            print(f"  Tables count: {len(tables)}")
            # Let's print some preview text
            print(f"  Snippet: {target_div.text.strip()[:300]}")
        else:
            print("  Target div NOT found!")
        print("-" * 50)
