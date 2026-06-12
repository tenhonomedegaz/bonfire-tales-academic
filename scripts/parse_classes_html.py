import os
import sys
import re
import json
import django
from django.utils.text import slugify
from bs4 import BeautifulSoup
import bs4

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bonfire.settings")
django.setup()

from django.db import transaction
from home.models import TbClasse, TbSubclasse, TbClassehabilidade, TbRecursoclasse, TbOpcaojogo, TbAcessoopcao

classes_dir = r"ref/Classes"
output_imports_dir = r"ref/previous imports"
os.makedirs(output_imports_dir, exist_ok=True)

CLASS_SLUG_MAP = {
    "Artificer": "artifice",
    "Bardo": "bardo",
    "Bárbaro": "barbaro",
    "Caçador": "cacador",
    "Clérigo": "clerigo",
    "Druida": "druida",
    "Feiticeiro": "feiticeiro",
    "Guerreiro": "guerreiro",
    "Ladino": "ladino",
    "Mago": "mago",
    "Monge": "monge",
    "Místico": "mistico",
}

OPTION_TIPO_MAPPING = {
    "Manobras de Combate Disponíveis": {
        "tipo": "Manobras de Combate",
        "classe": "guerreiro",
        "nivel": 2
    },
    "Opções de Metamagia": {
        "tipo": "Metamagia",
        "classe": "feiticeiro",
        "nivel": 2
    },
    "Técnicas de Furtividade": {
        "tipo": "Técnicas de Furtividade",
        "classe": "ladino",
        "nivel": 1
    },
    "Estilos de Ki": {
        "tipo": "Estilos de Ki",
        "classe": "monge",
        "nivel": 2
    },
    "Estilos Kensei": {
        "tipo": "Estilos Kensei",
        "classe": "monge",
        "subclasse": "kensei",
        "nivel": 3
    },
    "Segredos Místicos de 1º Nível": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 1
    },
    "Segredos Místicos de 5º Nível": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 5
    },
    "Segredos Místicos de 7º Nível": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 7
    },
    "Segredos Místicos de 9º Nível": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 9
    },
    "Segredos Místicos de 15º Nível": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 15
    },
    "Segredos Místicos Marca Mística": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 1
    },
    "Segredos Místicos Arma Mística": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 3
    },
    "Segredos Místicos Livro Místico": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 3
    },
    "Segredos Místicos de Rajada Mística (Eldritch Blast)": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 1
    },
    "Segredos Místicos Contrato Místico": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 1
    },
    "Segredos Místicos de Maldições": {
        "tipo": "Segredos Místicos",
        "classe": "mistico",
        "nivel": 1
    },
    "Infusões do Artífice": {
        "tipo": "Infusões do Artífice",
        "classe": "artifice",
        "nivel": 2
    },
    "1º nível": {
        "tipo": "Infusões do Artífice",
        "classe": "artifice",
        "nivel": 2
    },
    "5º Nível": {
        "tipo": "Infusões do Artífice",
        "classe": "artifice",
        "nivel": 5
    },
    "11º Nível": {
        "tipo": "Infusões do Artífice",
        "classe": "artifice",
        "nivel": 11
    },
    "17º Nível": {
        "tipo": "Infusões do Artífice",
        "classe": "artifice",
        "nivel": 17
    },
    "Infusões de Varinha": {
        "tipo": "Infusões de Varinha",
        "classe": "artifice",
        "subclasse": "magiduelista",
        "nivel": 3
    },
    "Infusões de Elixir": {
        "tipo": "Infusões de Elixir",
        "classe": "artifice",
        "subclasse": "alquimista",
        "nivel": 3
    },
    "Segredos de Caçador": {
        "tipo": "Segredos de Caçador",
        "classe": "cacador",
        "nivel": 2
    },
    "Segredos de Caçador: Alquimia e Poções": {
        "tipo": "Segredos de Caçador",
        "classe": "cacador",
        "nivel": 2
    },
    "Segredos de Caçador: Armadilhas e Emboscadas": {
        "tipo": "Segredos de Caçador",
        "classe": "cacador",
        "nivel": 2
    },
    "Segredos de Caçador: Conhecimentos Ancestrais": {
        "tipo": "Segredos de Caçador",
        "classe": "cacador",
        "nivel": 2
    },
}

def clean_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def clean_inline_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    
    # Check if there was leading/trailing whitespace
    has_leading = len(text) > 0 and text[0].isspace()
    has_trailing = len(text) > 0 and text[-1].isspace()
    
    # Collapse consecutive spaces
    text = re.sub(r'[ \t\r\n]+', ' ', text)
    text = text.strip()
    
    if not text:
        return " " if (has_leading or has_trailing) else ""
        
    leading_space = " " if has_leading else ""
    trailing_space = " " if has_trailing else ""
    
    return leading_space + text + trailing_space

def next_element_skipping_descendants(tag):
    if tag.next_sibling:
        return tag.next_sibling
    parent = tag.parent
    while parent:
        if parent.next_sibling:
            return parent.next_sibling
        parent = parent.parent
    return None

def is_inline(node):
    if not isinstance(node, bs4.element.Tag):
        return True
    block_elements = {
        "p", "div", "ul", "ol", "li", "table", "tr", "td", "th", 
        "h1", "h2", "h3", "h4", "h5", "h6", "hr", "blockquote", 
        "pre", "section", "article", "aside", "header", "footer"
    }
    return node.name.lower() not in block_elements

def wrap_inline_siblings_in_p(parent, soup):
    children = list(parent.children)
    current_group = []
    
    def commit_group():
        nonlocal current_group
        if not current_group:
            return
        is_empty = True
        for node in current_group:
            if isinstance(node, bs4.element.Tag) or node.strip():
                is_empty = False
                break
        if not is_empty:
            p_tag = soup.new_tag("p")
            first_node = current_group[0]
            first_node.insert_before(p_tag)
            for node in current_group:
                p_tag.append(node)
        current_group = []
        
    for child in children:
        if isinstance(child, bs4.element.Comment):
            commit_group()
            continue
        if is_inline(child):
            current_group.append(child)
        else:
            commit_group()
            
    commit_group()

def clean_document_structure(soup):
    containers = soup.find_all(["div", "blockquote", "form"])
    containers.append(soup)
    for container in containers:
        has_inline = any(is_inline(c) and (isinstance(c, bs4.element.Tag) or c.strip()) for c in container.children)
        if has_inline:
            wrap_inline_siblings_in_p(container, soup)

def get_target_id(btn):
    href = btn.get("href") or ""
    target = btn.get("data-bs-target") or btn.get("data-target") or ""
    if "#" in href:
        return href.split("#")[-1]
    elif target:
        return target.replace("#", "")
    return ""

def get_option_group_info(target_id, button_text):
    btn_clean = clean_text(button_text)
    # Sort keys by length descending to match more specific terms first
    sorted_keys = sorted(OPTION_TIPO_MAPPING.keys(), key=len, reverse=True)
    for key in sorted_keys:
        info = OPTION_TIPO_MAPPING[key]
        if key.lower() in btn_clean.lower():
            widget_title = info["tipo"]
            return {
                "tipo": info["tipo"],
                "classe": info["classe"],
                "subclasse": info.get("subclasse"),
                "nivel": info["nivel"],
                "widget_title": widget_title
            }
    # Dynamic checks
    if "segredos místicos" in btn_clean.lower() or "invocações místicas" in btn_clean.lower():
        level = 1
        lvl_match = re.search(r'(\d+)', btn_clean)
        if lvl_match:
            level = int(lvl_match.group(1))
        return {
            "tipo": "Segredos Místicos",
            "classe": "mistico",
            "nivel": level,
            "widget_title": "Segredos Místicos"
        }
    if "infusões" in btn_clean.lower():
        level = 2
        lvl_match = re.search(r'(\d+)', btn_clean)
        if lvl_match:
            level = int(lvl_match.group(1))
        return {
            "tipo": "Infusões do Artífice",
            "classe": "artifice",
            "nivel": level,
            "widget_title": "Infusões do Artífice"
        }
    return None

def to_markdown_children(tag, options_to_skip=None):
    parts = []
    for child in tag.children:
        parts.append(to_markdown(child, options_to_skip))
    return "".join(parts)

def to_markdown(node, options_to_skip=None):
    if not node:
        return ""
    if isinstance(node, bs4.element.Comment):
        return ""
    if not isinstance(node, bs4.element.Tag):
        return clean_inline_text(str(node))
    
    name = node.name.lower()
    
    # Check if option button
    if name == "a" and "spoiler-button" in node.get("class", []):
        target_id = get_target_id(node)
        if target_id:
            opt_info = get_option_group_info(target_id, node.text)
            if opt_info:
                title = opt_info["widget_title"]
                return f"\n\n::click {title}\n::options={title}\n::endclick\n\n"
        return "" # Discard non-option spoiler buttons (like subclass collapsibles)
                
    if options_to_skip and id(node) in options_to_skip:
        return ""
                
    if name in ["b", "strong"]:
        content = to_markdown_children(node, options_to_skip)
        return f"**{content}**" if content else ""
    elif name in ["i", "em"]:
        content = to_markdown_children(node, options_to_skip)
        return f"*{content}*" if content else ""
    elif name == "a":
        content = to_markdown_children(node, options_to_skip)
        href = node.get("href", "")
        if "spoiler-button" in node.get("class", []):
            return ""
        return f"[{content}]({href})" if content else ""
    elif name == "p":
        content = to_markdown_children(node, options_to_skip).strip()
        return f"{content}\n\n" if content else ""
    elif name in ["ul", "ol"]:
        parts = []
        for child in node.children:
            if not isinstance(child, bs4.element.Tag):
                txt = clean_inline_text(str(child))
                if txt:
                    parts.append(txt)
            else:
                c_name = child.name.lower()
                if c_name == "li":
                    parts.append(f"\n- {to_markdown_children(child, options_to_skip).strip()}")
                elif c_name in ["ul", "ol"]:
                    # Indent sublists
                    sub_content = to_markdown(child, options_to_skip).strip()
                    indented = "\n".join("  " + line for line in sub_content.splitlines())
                    parts.append(f"\n{indented}")
                else:
                    parts.append(to_markdown(child, options_to_skip))
        content = "".join(parts).strip()
        return f"\n{content}\n\n" if content else ""
    elif name == "blockquote":
        content = to_markdown_children(node, options_to_skip).strip()
        return f"> {content}\n\n" if content else ""
    elif name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        level = int(name[1])
        content = to_markdown_children(node, options_to_skip).strip()
        return f"{'#' * level} {content}\n\n" if content else ""
    elif name == "table":
        rows = node.find_all("tr")
        if not rows:
            return ""
        md_lines = []
        for idx, r in enumerate(rows):
            cells = [clean_text(to_markdown_children(td, options_to_skip)) for td in r.find_all(["td", "th"])]
            if not cells:
                continue
            md_lines.append("| " + " | ".join(cells) + " |")
            if idx == 0:
                md_lines.append("| " + " | ".join([":---" for _ in cells]) + " |")
        return "\n" + "\n".join(md_lines) + "\n\n" if md_lines else ""
    elif name == "br":
        return "\n"
    elif name == "div" and any(c in node.get("class", []) for c in ["paragraph-align-center", "text-center"]):
        content = to_markdown_children(node, options_to_skip).strip()
        return f"::center\n{content}\n::\n\n" if content else ""
    else:
        return to_markdown_children(node, options_to_skip)

def extract_manifestation_markdown(target_div, options_to_skip):
    h3 = target_div.find("h3")
    parts = []
    if h3:
        curr = h3.next_sibling
        while curr:
            parts.append(to_markdown(curr, options_to_skip))
            curr = curr.next_sibling
    else:
        parts.append(to_markdown(target_div, options_to_skip))
    return "".join(parts).strip()

def get_subclass_for_heading(heading, classe, soup, btn_map=None, subclasses_cache=None):
    parent = heading.parent
    while parent:
        if parent.name == "div" and "collapse" in parent.get("class", []):
            div_id = parent.get("id")
            if div_id:
                btn = None
                if btn_map is not None:
                    btn = btn_map.get(div_id)
                else:
                    btn = soup.find(lambda t: t.name == "a" and "spoiler-button" in t.get("class", []) and (
                        div_id in (t.get("href") or "") or 
                        div_id in (t.get("data-bs-target") or "") or 
                        div_id in (t.get("data-target") or "")
                    ))
                if btn:
                    btn_text = clean_text(btn.text)
                    btn_slug = slugify(btn_text)
                    if subclasses_cache is not None:
                        subclasses = subclasses_cache
                    else:
                        subclasses = TbSubclasse.objects.filter(id_classe=classe)
                    for sub in subclasses:
                        if sub.slug == btn_slug or sub.slug in btn_slug or btn_slug in sub.slug:
                            return sub
                        if sub.nome.lower() in btn_text.lower() or btn_text.lower() in sub.nome.lower():
                            return sub
        parent = parent.parent
    return None

def parse_options_from_div(div, opt_info, soup):
    options_list = []
    inner_div = div.find(class_="card-body") or div
    
    # 1. Check if there are tables (Ladino, Místico)
    tables = inner_div.find_all("table")
    if tables and opt_info["classe"] in ["ladino", "mistico"]:
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            headers = [clean_text(th.text) for th in rows[0].find_all(["th", "td"])]
            
            name_idx = -1
            desc_idx = -1
            cost_idx = -1
            
            for idx, h in enumerate(headers):
                h_lower = h.lower()
                if "nome" in h_lower or "técnica" in h_lower or "tecnica" in h_lower:
                    name_idx = idx
                elif "descrição" in h_lower or "descricao" in h_lower or "efeito" in h_lower:
                    desc_idx = idx
                elif "custo" in h_lower:
                    cost_idx = idx
                    
            if name_idx == -1:
                if len(headers) >= 2:
                    name_idx = 0
                    desc_idx = 1
                    
            if name_idx != -1 and desc_idx != -1:
                table_cost_prefix = ""
                prev = table.find_previous(["h4", "h3", "h2"])
                if prev:
                    prev_text = prev.text.strip()
                    if "custo" in prev_text.lower():
                        c_match = re.search(r'custo:\s*([^)]+)', prev_text, re.IGNORECASE)
                        if c_match:
                            table_cost_prefix = c_match.group(1).strip()
                
                for r in rows[1:]:
                    cells = r.find_all("td")
                    if len(cells) <= max(name_idx, desc_idx):
                        continue
                    name = clean_text(cells[name_idx].text).strip("*").strip()
                    desc = to_markdown(cells[desc_idx]).strip()
                    
                    cost = ""
                    if cost_idx != -1 and len(cells) > cost_idx:
                        cost = clean_text(cells[cost_idx].text)
                    elif table_cost_prefix:
                        cost = table_cost_prefix
                        
                    if not name:
                        continue
                        
                    pre_req = f"Custo: {cost}" if cost else ""
                    
                    options_list.append({
                        "nome": name,
                        "tipo": opt_info["tipo"],
                        "pre_requisito": pre_req,
                        "descricao": desc,
                        "nivel_recebimento": opt_info["nivel"],
                        "classes": [opt_info["classe"]],
                        "subclasses": [opt_info["subclasse"]] if opt_info.get("subclasse") else []
                    })
        return options_list

    # 2. Check if there are h5 headings (Monge, Artífice, Caçador)
    h5_headings = inner_div.find_all("h5")
    if h5_headings:
        for h5 in h5_headings:
            name = clean_text(h5.text).strip()
            if not name:
                continue
                
            siblings = []
            curr = h5.next_sibling
            while curr:
                if isinstance(curr, bs4.element.Tag):
                    if curr.name in ["h5", "h4", "h3", "h2", "h1", "hr"]:
                        break
                siblings.append(curr)
                curr = curr.next_sibling
                
            desc = "".join([to_markdown(s) for s in siblings]).strip()
            
            pre_req = ""
            custo_match = re.search(r'\*\*(?:Custo|Pré-requisito|Prerequisito|Requisito)\*\*:\s*(.*)', desc, re.IGNORECASE)
            if custo_match:
                pre_req = custo_match.group(1).strip()
                
            options_list.append({
                "nome": name,
                "tipo": opt_info["tipo"],
                "pre_requisito": pre_req,
                "descricao": desc,
                "nivel_recebimento": opt_info["nivel"],
                "classes": [opt_info["classe"]],
                "subclasses": [opt_info["subclasse"]] if opt_info.get("subclasse") else []
            })
        return options_list

    # 3. Check for nested lists (Feiticeiro Metamagia)
    lis = inner_div.find_all("li")
    if lis and opt_info["classe"] == "feiticeiro":
        for li in lis:
            b_tag = li.find(["b", "strong"])
            if b_tag:
                name_raw = clean_text(b_tag.text).strip(":").strip()
                name = name_raw
                cost = ""
                m = re.search(r'^([^(]+)(?:\(([^)]+)\))?', name_raw)
                if m:
                    name = m.group(1).strip()
                    if m.group(2):
                        cost = m.group(2).strip()
                
                li_copy = BeautifulSoup(str(li), "html.parser").find("li")
                b_copy = li_copy.find(["b", "strong"])
                if b_copy:
                    b_copy.decompose()
                desc = to_markdown(li_copy).strip().strip(":").strip()
                
                options_list.append({
                    "nome": name,
                    "tipo": opt_info["tipo"],
                    "pre_requisito": cost,
                    "descricao": desc,
                    "nivel_recebimento": opt_info["nivel"],
                    "classes": [opt_info["classe"]],
                    "subclasses": []
                })
        return options_list
        
    return options_list

def parse_class_html_file(filename):
    filepath = os.path.join(classes_dir, filename)
    print(f"\n==========================================")
    print(f"PARSING CLASS HTML FILE: {filename}")
    print(f"==========================================")
    
    content = open(filepath, "r", encoding="utf-8").read()
    soup = BeautifulSoup(content, "html.parser")
    
    # Remove script and style tags
    for tag in list(soup.find_all(["style", "script"])):
        if tag.parent:
            tag.decompose()
            
    # Remove monster/creature sheets (statblocks)
    for tag in list(soup.find_all(class_=lambda x: x and ("statblock" in x or "template-bonfire" in x))):
        if tag.parent:
            tag.decompose()
            
    clean_document_structure(soup)
    
    # Identify class
    class_key = filename.split(" in ")[0].strip()
    class_slug = CLASS_SLUG_MAP.get(class_key)
    if not class_slug:
        print(f"Error: Unknown class for filename {filename}")
        return None
        
    classe = TbClasse.objects.get(slug=class_slug)
    print(f"Matched class: {classe.nome} ({classe.slug})")
    
    # Precompute caches for speed
    subclasses_cache = list(TbSubclasse.objects.filter(id_classe=classe))
    btn_map = {}
    for btn in soup.find_all(lambda t: t.name == "a" and "spoiler-button" in t.get("class", [])):
        target_id = get_target_id(btn)
        if target_id:
            btn_map[target_id] = btn
    
    # 1. Identify all option collapse divs and buttons to skip/ignore in general markdown
    options_divs_to_skip = set()
    options_parsed = []
    
    all_buttons = soup.find_all(class_=lambda x: x and "spoiler-button" in x)
    for btn in all_buttons:
        target_id = get_target_id(btn)
        if target_id:
            opt_info = get_option_group_info(target_id, btn.text)
            if opt_info:
                target_div = soup.find("div", id=target_id)
                if target_div:
                    options_divs_to_skip.add(id(target_div))
                    options_divs_to_skip.add(id(btn))
                    # Parse options inside it
                    opts = parse_options_from_div(target_div, opt_info, soup)
                    options_parsed.extend(opts)
                    print(f"Parsed {len(opts)} options from collapse '{btn.text.strip()}' (Type: {opt_info['tipo']})")
                    
    # 2. Parse Table 0 level resources
    table_0 = soup.find("table")
    resources_parsed = []
    table_abilities = set()
    
    if table_0:
        rows = table_0.find_all("tr")
        if rows:
            headers = [clean_text(th.text) for th in rows[0].find_all(["th", "td"])]
            print(f"Table 0 headers: {headers}")
            
            for r in rows[1:]:
                cells = r.find_all("td")
                if len(cells) < len(headers):
                    continue
                level_str = clean_text(cells[0].text)
                lvl_match = re.search(r'(\d+)', level_str)
                if not lvl_match:
                    continue
                level = int(lvl_match.group(1))
                
                # Parse abilities listed in the feature column (Características / Habilidades / etc.)
                char_col_idx = -1
                for idx, h in enumerate(headers):
                    h_slug = slugify(h)
                    if h_slug in {"habilidades", "habilidades-de-classe", "caracteristicas", "caracteristicas-de-classe", "features"}:
                        char_col_idx = idx
                        break
                if char_col_idx != -1:
                    char_text = clean_text(cells[char_col_idx].text)
                    if char_text and char_text != "—":
                        for name in re.split(r'[,;\n/]+', char_text):
                            name_clean = clean_text(name).strip()
                            if name_clean:
                                table_abilities.add((name_clean, level))
                                
                # Parse resource columns
                for idx, h in enumerate(headers):
                    if idx == 0 or idx == char_col_idx:
                        continue
                    val = clean_text(cells[idx].text)
                    if val and val != "—":
                        resources_parsed.append({
                            "nivel": level,
                            "nome": h,
                            "slug": slugify(h),
                            "valor": val,
                            "subclasse_slug": None
                        })
                        
    print(f"Parsed {len(resources_parsed)} progression resource rows.")
    print(f"Parsed {len(table_abilities)} unique features from progression table.")
    
    # 3. Parse Abilities (excluding option divs)
    abilities_parsed = []
    headings = soup.find_all(lambda t: t.name in ["h3", "h4"] and ("nível" in t.text.lower() or "nivel" in t.text.lower() or "level" in t.text.lower()))
    
    # Identify and skip Místico manifestations (to group them into a single ::toggle block under Manifestação Mística)
    manifestations = []
    toggle_parts = []
    if class_slug == "mistico":
        m_heading = None
        for h in headings:
            h_text = clean_text(h.text)
            if "manifestação mística" in h_text.lower():
                m_heading = h
                break
        if m_heading:
            curr_sib = next_element_skipping_descendants(m_heading)
            while curr_sib:
                if isinstance(curr_sib, bs4.element.Tag):
                    if curr_sib.name in ["h1", "h2", "hr"]:
                        break
                    if curr_sib.name in ["h3", "h4", "h5", "h6"]:
                        curr_text_lower = curr_sib.text.lower()
                        if "nível" in curr_text_lower or "nivel" in curr_text_lower or "level" in curr_text_lower:
                            break
                    buttons = []
                    if curr_sib.name == "a" and "spoiler-button" in curr_sib.get("class", []):
                        buttons.append(curr_sib)
                    else:
                        buttons.extend(curr_sib.find_all("a", class_=lambda x: x and "spoiler-button" in x))
                    
                    for btn in buttons:
                        btn_text = btn.text.strip()
                        if btn_text in ["Arma Mística", "Contrato Místico", "Livro Místico", "Marca Mística"]:
                            target_id = get_target_id(btn)
                            if target_id:
                                target_div = soup.find("div", id=target_id)
                                if target_div:
                                    manifestations.append((btn, target_div))
                                    options_divs_to_skip.add(id(btn))
                                    options_divs_to_skip.add(id(target_div))
                curr_sib = next_element_skipping_descendants(curr_sib)
            
            if manifestations:
                toggle_parts = ["\n\n::toggle\n# Manifestação Mística\n"]
                for m_btn, m_div in manifestations:
                    m_title = m_btn.text.strip()
                    m_desc = extract_manifestation_markdown(m_div, options_divs_to_skip)
                    toggle_parts.append(f"### {m_title}\n{m_desc}\n\n")
                toggle_parts.append("::endtoggle")

    for h in headings:
        # Skip headings inside skipped divs (like Místico manifestations)
        parent = h.parent
        is_ignored = False
        while parent:
            if id(parent) in options_divs_to_skip:
                is_ignored = True
                break
            parent = parent.parent
        if is_ignored:
            continue

        h_text = clean_text(h.text)
        parts = re.split(r'[:—]', h_text, 1)
        if len(parts) < 2:
            continue
        level_str, name = parts[0], parts[1]
        lvl_match = re.search(r'(\d+)', level_str)
        if not lvl_match:
            continue
        level = int(lvl_match.group(1))
        name = clean_text(name).strip()
        
        subclass = get_subclass_for_heading(h, classe, soup, btn_map=btn_map, subclasses_cache=subclasses_cache)
        subclass_slug = subclass.slug if subclass else None
        
        desc_parts = []
        curr = next_element_skipping_descendants(h)
        while curr:
            if isinstance(curr, bs4.element.Tag):
                if curr.name in ["h1", "h2", "hr"]:
                    break
                if curr.name in ["h3", "h4", "h5", "h6"]:
                    curr_text_lower = curr.text.lower()
                    if "nível" in curr_text_lower or "nivel" in curr_text_lower or "level" in curr_text_lower:
                        break
                if "spoiler-button" in curr.get("class", []):
                    target_id = get_target_id(curr)
                    if target_id:
                        opt_info = get_option_group_info(target_id, curr.text)
                        if opt_info:
                            desc_parts.append(to_markdown(curr, options_divs_to_skip))
                    curr = next_element_skipping_descendants(curr)
                    continue
                if id(curr) in options_divs_to_skip:
                    desc_parts.append(to_markdown(curr, options_divs_to_skip))
                    curr = next_element_skipping_descendants(curr)
                    continue
                if curr.name in ["p", "ul", "ol", "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"]:
                    desc_parts.append(to_markdown(curr, options_divs_to_skip))
                    curr = next_element_skipping_descendants(curr)
                    continue
                curr = curr.next_element
            else:
                txt = clean_text(curr)
                if txt:
                    desc_parts.append(txt + "\n\n")
                curr = curr.next_element
                
        desc = "".join(desc_parts).strip()
        desc = re.sub(r'\n{3,}', '\n\n', desc)
        
        if class_slug == "mistico" and name == "Manifestação Mística" and toggle_parts:
            desc += "".join(toggle_parts)
        
        abilities_parsed.append({
            "nome": name,
            "nivel": level,
            "subclasse_slug": subclass_slug,
            "descricao": desc,
            "table_only": False
        })
        
    print(f"Parsed {len(abilities_parsed)} ability descriptions from headings.")
    
    # 4. Handle table_only abilities
    found_ability_keys = {(a["nome"].lower(), a["nivel"]) for a in abilities_parsed}
    for tab_name, tab_level in table_abilities:
        if (tab_name.lower(), tab_level) not in found_ability_keys:
            abilities_parsed.append({
                "nome": tab_name,
                "nivel": tab_level,
                "subclasse_slug": None,
                "descricao": "Apenas tabela.",
                "table_only": True
            })
            
    # 5. Post-process specific features to inject option widgets if not present
    for ab in abilities_parsed:
        name_clean = ab["nome"].strip()
        # Estilo de Luta feature (Bardo / others)
        if name_clean == "Estilo de Luta":
            if "::options=Estilo de Luta" not in ab["descricao"]:
                ab["descricao"] += "\n\n::click Estilo de Luta\n::options=Estilo de Luta\n::endclick"
                
        # Guerreiro: Disciplina Marcial
        elif class_slug == "guerreiro" and name_clean == "Disciplina Marcial":
            if "::options=Estilo de Luta" not in ab["descricao"]:
                ab["descricao"] += "\n\n::click Estilo de Luta\n::options=Estilo de Luta\n::endclick"
            if "::options=Maestria de Arma" not in ab["descricao"]:
                ab["descricao"] += "\n\n::click Maestria de Arma\n::options=Maestria de Arma\n::endclick"
                
        # Caçador: Preparos de Caçada
        elif class_slug == "cacador" and name_clean == "Preparos de Caçada":
            if "::options=Estilo de Luta" not in ab["descricao"]:
                ab["descricao"] += "\n\n::click Estilo de Luta\n::options=Estilo de Luta\n::endclick"
            if "::options=Maestria de Arma" not in ab["descricao"]:
                ab["descricao"] += "\n\n::click Maestria de Arma\n::options=Maestria de Arma\n::endclick"
            
    # Deduplicate resources
    seen_resources = set()
    unique_resources = []
    for r in resources_parsed:
        key = (r["nivel"], r["nome"].lower())
        if key not in seen_resources:
            seen_resources.add(key)
            unique_resources.append(r)
    resources_parsed = unique_resources

    # Deduplicate abilities
    seen_abilities = set()
    unique_abilities = []
    for ab in abilities_parsed:
        key = (ab["subclasse_slug"], ab["nome"].lower(), ab["nivel"])
        if key not in seen_abilities:
            seen_abilities.add(key)
            unique_abilities.append(ab)
    abilities_parsed = unique_abilities

    # Deduplicate options with merging of classes and subclasses lists
    merged_options = {}
    for opt in options_parsed:
        key = opt["nome"].lower()
        if key not in merged_options:
            merged_options[key] = opt
        else:
            for c in opt["classes"]:
                if c not in merged_options[key]["classes"]:
                    merged_options[key]["classes"].append(c)
            for s in opt["subclasses"]:
                if s not in merged_options[key]["subclasses"]:
                    merged_options[key]["subclasses"].append(s)
    options_parsed = list(merged_options.values())

    # Write to output TXT files
    class_txt_path = os.path.join(output_imports_dir, f"{class_key}.txt")
    with open(class_txt_path, "w", encoding="utf-8") as f:
        f.write("[RECURSOS]\n")
        resources_by_lvl = {}
        for r in resources_parsed:
            lvl = r["nivel"]
            if lvl not in resources_by_lvl:
                resources_by_lvl[lvl] = []
            resources_by_lvl[lvl].append(r)
            
        for lvl in sorted(resources_by_lvl.keys()):
            f.write(f"Nivel: {lvl}\n")
            for r in resources_by_lvl[lvl]:
                f.write(f"{r['nome']}: {r['valor']}\n")
            f.write("---\n")
            
        f.write("\n[HABILIDADES]\n")
        for ab in abilities_parsed:
            f.write(f"Nome: {ab['nome']}\n")
            f.write(f"Nivel: {ab['nivel']}\n")
            f.write(f"Subclasse: {ab['subclasse_slug'] or ''}\n")
            f.write(f"Table Only: {'sim' if ab['table_only'] else 'nao'}\n")
            f.write(f"Descrição:\n{ab['descricao']}\n")
            f.write("---\n")
            
    print(f"Generated class import TXT: {class_txt_path}")
    
    if options_parsed:
        options_txt_path = os.path.join(output_imports_dir, f"Opcoes_{class_key}.txt")
        with open(options_txt_path, "w", encoding="utf-8") as f:
            f.write("[OPCOES]\n")
            for opt in options_parsed:
                f.write(f"Nome: {opt['nome']}\n")
                f.write(f"Tipo: {opt['tipo']}\n")
                if opt['pre_requisito']:
                    f.write(f"Pre Requisito: {opt['pre_requisito']}\n")
                f.write(f"Nivel Recebimento: {opt['nivel_recebimento']}\n")
                f.write(f"Classes: {','.join(opt['classes'])}\n")
                f.write(f"Subclasses: {','.join(opt['subclasses'])}\n")
                f.write(f"Descricao:\n{opt['descricao']}\n")
                f.write("---\n")
        print(f"Generated options import TXT: {options_txt_path}")
        
    # Database transaction
    with transaction.atomic():
        TbRecursoclasse.objects.filter(id_classe=classe).delete()
        TbClassehabilidade.objects.filter(id_classe=classe).delete()
        
        for r in resources_parsed:
            TbRecursoclasse.objects.create(
                id_classe=classe,
                id_subclasse=None,
                nome=r["nome"],
                slug=r["slug"],
                nivel=r["nivel"],
                valor=r["valor"]
            )
            
        for ab in abilities_parsed:
            sub = None
            if ab["subclasse_slug"]:
                sub = TbSubclasse.objects.filter(id_classe=classe, slug=ab["subclasse_slug"]).first()
            TbClassehabilidade.objects.create(
                id_classe=classe,
                id_subclasse=sub,
                nome=ab["nome"],
                descricao=ab["descricao"],
                niveladquirido=ab["nivel"],
                table_only=ab["table_only"]
            )
            
        for opt in options_parsed:
            opt_slug = slugify(opt["nome"])
            op_obj, created = TbOpcaojogo.objects.get_or_create(
                slug=opt_slug,
                defaults={
                    "nome": opt["nome"],
                    "tipo": opt["tipo"],
                    "pre_requisito": opt["pre_requisito"] or None,
                    "descricao": opt["descricao"]
                }
            )
            if not created:
                op_obj.descricao = opt["descricao"]
                op_obj.pre_requisito = opt["pre_requisito"] or None
                op_obj.tipo = opt["tipo"]
                op_obj.save()
                
            TbAcessoopcao.objects.filter(id_opcao=op_obj, id_classe=classe).delete()
            
            for c_slug in opt["classes"]:
                cls = TbClasse.objects.filter(slug=c_slug).first()
                if cls:
                    TbAcessoopcao.objects.get_or_create(
                        id_opcao=op_obj,
                        id_classe=cls,
                        id_subclasse=None,
                        defaults={"nivel_recebimento": opt["nivel_recebimento"]}
                    )
            for s_slug in opt["subclasses"]:
                sub = TbSubclasse.objects.filter(slug=s_slug).first()
                if sub:
                    TbAcessoopcao.objects.get_or_create(
                        id_opcao=op_obj,
                        id_classe=None,
                        id_subclasse=sub,
                        defaults={"nivel_recebimento": opt["nivel_recebimento"]}
                    )
                    
    print(f"Successfully imported and updated database for {classe.nome}.")
    return True

if __name__ == "__main__":
    files = [f for f in os.listdir(classes_dir) if f.endswith(".html")]
    success_count = 0
    for filename in sorted(files):
        try:
            if parse_class_html_file(filename):
                success_count += 1
        except Exception as e:
            print(f"Error parsing/importing file {filename}: {e}")
            import traceback
            traceback.print_exc()
            
    print(f"\nDone! Successfully parsed and imported {success_count} out of {len(files)} files.")
