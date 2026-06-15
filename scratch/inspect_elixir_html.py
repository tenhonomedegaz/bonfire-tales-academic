import os
from bs4 import BeautifulSoup

file_path = r"c:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\Classes\Artificer in Bonfire Tales RPG _ World Anvil.html"
content = open(file_path, "r", encoding="utf-8").read()
soup = BeautifulSoup(content, "html.parser")

div = soup.find(id="spoiler-1OSxq9")
print(div.prettify()[:3000])
