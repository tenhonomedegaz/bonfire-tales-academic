import bs4

content = open("ref/Vampirismo in Bonfire Tales RPG _ World Anvil.html", "r", encoding="utf-8").read()
soup = bs4.BeautifulSoup(content, "html.parser")

h3 = soup.find(lambda t: t.name == "h3" and "Traços da Maldição" in t.text)
if h3:
    print("Found h3:", h3)
    
    print("\nNext tags in document order:")
    curr = h3.next_element
    count = 0
    while curr and count < 30:
        if isinstance(curr, bs4.element.Tag):
            print(f" - Tag: {curr.name}, class: {curr.get('class')}, text preview: {repr(curr.text.strip()[:60])}")
            count += 1
        curr = curr.next_element
else:
    print("Could not find h3 containing 'Traços da Maldição'")
