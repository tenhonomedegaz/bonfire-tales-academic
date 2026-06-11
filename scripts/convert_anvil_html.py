import os
import re
import bs4
from bs4 import BeautifulSoup

def clean_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def next_element_skipping_descendants(tag):
    if tag.next_sibling:
        return tag.next_sibling
    parent = tag.parent
    while parent:
        if parent.next_sibling:
            return parent.next_sibling
        parent = parent.parent
    return None

def extract_section_elements(start_element):
    """Collects paragraphs/lists in document order until a heading or hr is reached."""
    elements = []
    curr = start_element.next_element
    while curr:
        if not isinstance(curr, bs4.element.Tag):
            curr = curr.next_element
            continue
        if curr.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr']:
            break
        if curr.name in ['p', 'ul', 'ol', 'blockquote']:
            text = clean_text(curr.text)
            if text:
                if curr.name in ['ul', 'ol']:
                    bullets = []
                    for li in curr.find_all('li'):
                        li_text = clean_text(li.text)
                        if li_text:
                            bullets.append(f"- {li_text}")
                    if bullets:
                        elements.append("\n".join(bullets))
                else:
                    if text not in elements:
                        elements.append(text)
            curr = next_element_skipping_descendants(curr)
        else:
            curr = curr.next_element
    return elements

def parse_anvil_html(filepath, is_essence=False):
    print(f"Parsing {filepath}...")
    content = open(filepath, "r", encoding="utf-8").read()
    soup = BeautifulSoup(content, "html.parser")
    
    title_el = soup.find("h1")
    title = clean_text(title_el.text) if title_el else os.path.basename(filepath).split(" ")[0]
    slug = "anao" if "Anão" in title else ("vampirismo" if "Vampirismo" in title else "nephilim")
    
    tagline = ""
    first_bq = soup.find("blockquote")
    if first_bq:
        tagline = clean_text(first_bq.text)
    
    lore_presentation = []
    lore_roleplay = []
    lore_society = []
    
    h3_headings = soup.find_all("h3")
    for h3 in h3_headings:
        h3_text = clean_text(h3.text)
        if "Interpretando" in h3_text:
            lore_roleplay.extend(extract_section_elements(h3))
        elif "Aparência" in h3_text or "Origem" in h3_text or "Os Dois Polos" in h3_text or "Velmourn" in h3_text:
            lore_presentation.extend(extract_section_elements(h3))
        elif "Relações" in h3_text or "Bastiões" in h3_text or "Nomes" in h3_text or "Sociedade" in h3_text:
            lore_society.extend(extract_section_elements(h3))
            
    lore_presentation_txt = "\n\n".join(lore_presentation).strip()
    lore_roleplay_txt = "\n\n".join(lore_roleplay).strip()
    lore_society_txt = "\n\n".join(lore_society).strip()
    
    output_blocks = []
    
    meta_block = []
    if not is_essence:
        meta_block.append("Tipo: Raca")
        meta_block.append(f"Slug: {slug}")
        meta_block.append(f"Nome: {title}")
        if tagline:
            meta_block.append(f"Tagline: {tagline}")
        if lore_presentation_txt:
            meta_block.append(f"Lore Apresentação:\n{lore_presentation_txt}")
        if lore_roleplay_txt:
            meta_block.append(f"Lore Roleplay:\n{lore_roleplay_txt}")
        if lore_society_txt:
            meta_block.append(f"Lore Sociedade:\n{lore_society_txt}")
    else:
        meta_block.append("Tipo: Essencia")
        meta_block.append(f"Slug: {slug}")
        meta_block.append(f"Nome: {title}")
        if lore_presentation_txt:
            meta_block.append(f"Lore Apresentação:\n{lore_presentation_txt}")
        if lore_roleplay_txt:
            meta_block.append(f"Lore Roleplay:\n{lore_roleplay_txt}")
        if lore_society_txt:
            meta_block.append(f"Lore Sociedade:\n{lore_society_txt}")
            
    output_blocks.append("\n".join(meta_block))
    
    # 3. Parse Traits (Base / Clã / Weakness)
    for h3 in h3_headings:
        h3_text = clean_text(h3.text)
        if "Traços da Raça Base" in h3_text or "Traços da Maldição" in h3_text or "Traços de Essência" in h3_text or "O Peso da Maldição" in h3_text:
            curr = h3.next_element
            while curr:
                if not isinstance(curr, bs4.element.Tag):
                    curr = curr.next_element
                    continue
                if curr.name in ['h1', 'h2', 'h3', 'h4', 'hr']:
                    break
                if curr.name == 'h5':
                    trait_name = clean_text(curr.text)
                    trait_elements = extract_section_elements(curr)
                    
                    prereq = ""
                    desc_paras = []
                    for el in trait_elements:
                        if el.startswith("Pré-requisito:") or el.startswith("Prerequisito:") or el.startswith("Requisito:"):
                            prereq = el.split(":", 1)[1].strip()
                        else:
                            desc_paras.append(el)
                            
                    desc_text = "\n\n".join(desc_paras).strip()
                    
                    trait_block = []
                    trait_block.append(f"Nome: {trait_name}")
                    if not is_essence:
                        trait_block.append(f"Raca: {slug}")
                    else:
                        trait_block.append(f"Essencia: {slug}")
                    trait_block.append("Nivel: 0")
                    trait_block.append("Talento Racial: nao")
                    if prereq:
                        trait_block.append(f"Pre Requisito: {prereq}")
                    trait_block.append(f"Descricao:\n{desc_text}")
                    
                    output_blocks.append("\n".join(trait_block))
                    curr = next_element_skipping_descendants(curr)
                else:
                    curr = curr.next_element

    # 4. Parse Option A: Lineages/Clãs
    for h3 in h3_headings:
        h3_text = clean_text(h3.text)
        # We also check for Heading 2 "Os Clãs Vampíricos" for essences
        is_clans_h2 = "Os Clãs Vampíricos" in h3_text
    
    # Let's search all headings (h2 and h3) for clãs/lineages
    all_headings = soup.find_all(['h2', 'h3'])
    for h in all_headings:
        h_text = clean_text(h.text)
        if "Linhagens Anãs" in h_text or "Os Clãs Vampíricos" in h_text or "Os Dois Polos" in h_text:
            curr = h.next_element
            while curr:
                if not isinstance(curr, bs4.element.Tag):
                    curr = curr.next_element
                    continue
                if curr.name in ['h1', 'h2', 'h3', 'hr']:
                    break
                if curr.name == 'h4':
                    lin_name = clean_text(curr.text)
                    lin_slug = lin_name.lower().replace("anão da ", "").replace("anão das ", "").split(" ")[0].split("(")[0].strip()
                    
                    lin_desc_elements = []
                    next_el = curr.next_element
                    while next_el:
                        if not isinstance(next_el, bs4.element.Tag):
                            next_el = next_el.next_element
                            continue
                        if next_el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'hr']:
                            break
                        if next_el.name in ['p', 'ul', 'ol', 'blockquote']:
                            txt = clean_text(next_el.text)
                            if txt:
                                lin_desc_elements.append(txt)
                            next_el = next_element_skipping_descendants(next_el)
                        else:
                            next_el = next_el.next_element
                        
                    lin_desc = "\n\n".join(lin_desc_elements).strip()
                    
                    if not is_essence:
                        lin_block = []
                        lin_block.append("Tipo: Linhagem")
                        lin_block.append(f"Slug: {lin_slug}")
                        lin_block.append(f"Raça: {slug}")
                        lin_block.append(f"Nome: {lin_name}")
                        lin_block.append(f"Descricao:\n{lin_desc}")
                        output_blocks.append("\n".join(lin_block))
                    
                    child_el = curr.next_element
                    while child_el:
                        if not isinstance(child_el, bs4.element.Tag):
                            child_el = child_el.next_element
                            continue
                        if child_el.name in ['h1', 'h2', 'h3', 'h4', 'hr']:
                            break
                        if child_el.name == 'h5':
                            trait_name = clean_text(child_el.text)
                            trait_elements = extract_section_elements(child_el)
                            
                            prereq = ""
                            desc_paras = []
                            for el in trait_elements:
                                if el.startswith("Pré-requisito:") or el.startswith("Prerequisito:") or el.startswith("Requisito:"):
                                    prereq = el.split(":", 1)[1].strip()
                                else:
                                    desc_paras.append(el)
                                    
                            desc_text = "\n\n".join(desc_paras).strip()
                            
                            trait_block = []
                            trait_block.append(f"Nome: {trait_name}")
                            if not is_essence:
                                trait_block.append(f"Raca: {slug}")
                                trait_block.append(f"Linhagem: {lin_slug}")
                            else:
                                trait_block.append(f"Essencia: {slug}")
                                prereq = f"Clã {lin_name}" + (f", {prereq}" if prereq else "")
                            trait_block.append("Nivel: 0")
                            trait_block.append("Talento Racial: nao")
                            if prereq:
                                trait_block.append(f"Pre Requisito: {prereq}")
                            trait_block.append(f"Descricao:\n{desc_text}")
                            
                            output_blocks.append("\n".join(trait_block))
                            child_el = next_element_skipping_descendants(child_el)
                        else:
                            child_el = child_el.next_element
                    
                    curr = next_element_skipping_descendants(curr)
                else:
                    curr = curr.next_element

    # 5. Parse Talents (Evolução...)
    for h3 in h3_headings:
        h3_text = clean_text(h3.text)
        if "Evolução" in h3_text:
            curr = h3.next_element
            while curr:
                if not isinstance(curr, bs4.element.Tag):
                    curr = curr.next_element
                    continue
                if curr.name in ['h1', 'h2', 'h3', 'hr']:
                    break
                if curr.name == 'h5':
                    talent_name = clean_text(curr.text)
                    talent_elements = extract_section_elements(curr)
                    
                    prereq = ""
                    desc_paras = []
                    for el in talent_elements:
                        if el.startswith("Pré-requisito:") or el.startswith("Prerequisito:") or el.startswith("Requisito:"):
                            prereq = el.split(":", 1)[1].strip()
                        else:
                            desc_paras.append(el)
                            
                    desc_text = "\n\n".join(desc_paras).strip()
                    
                    level = 1
                    if prereq:
                        lvl_match = re.search(r'(?:Nível|Nivel|level|Nvel)\s*(\d+)', prereq, re.IGNORECASE)
                        if lvl_match:
                            level = int(lvl_match.group(1))
                            
                    talent_block = []
                    talent_block.append(f"Nome: {talent_name}")
                    if not is_essence:
                        talent_block.append(f"Raca: {slug}")
                    else:
                        talent_block.append(f"Essencia: {slug}")
                    talent_block.append(f"Nivel: {level}")
                    talent_block.append("Talento Racial: sim")
                    if prereq:
                        talent_block.append(f"Pre Requisito: {prereq}")
                    talent_block.append(f"Descricao:\n{desc_text}")
                    
                    output_blocks.append("\n".join(talent_block))
                    curr = next_element_skipping_descendants(curr)
                else:
                    curr = curr.next_element
                
    output_filepath = filepath.replace(".html", "_import.txt")
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(output_blocks))
    print(f"Generated: {output_filepath}")

if __name__ == "__main__":
    parse_anvil_html("ref/Anão in Bonfire Tales RPG _ World Anvil.html", is_essence=False)
    parse_anvil_html("ref/Vampirismo in Bonfire Tales RPG _ World Anvil.html", is_essence=True)
    parse_anvil_html("ref/Nephilim in Bonfire Tales RPG _ World Anvil.html", is_essence=True)
