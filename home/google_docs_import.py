"""
Utilitário para importar conteúdo de Google Docs públicos como Markdown.

Usa a Google Drive API (files.export) com API key para exportar
documentos públicos como HTML e depois converte para Markdown formatado
para o sistema Bonfire.
"""
import os
import re
import html as html_module
import urllib.request
import urllib.error
import json


def extract_doc_id(url_or_id: str) -> str:
    """Extrai o ID do documento de uma URL do Google Docs ou retorna o ID puro."""
    # Match: https://docs.google.com/document/d/DOC_ID/...
    match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    # Se já é um ID puro (sem barras)
    if re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
        return url_or_id
    return url_or_id


def fetch_doc_html(doc_id: str) -> str:
    """
    Busca o conteúdo de um Google Doc público como HTML usando a URL de exportação pública.
    Retorna o HTML ou levanta exceção. Não requer API key.
    """
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'BonfireSite/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get_content_type()
            if content_type == 'application/zip':
                raise PermissionError("O documento contém arquivos que forçam download em ZIP. Remova algumas imagens ou simplifique o arquivo.")
            return resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise PermissionError("Documento não encontrado. Verifique se o link está correto.")
        elif e.code in (401, 403):
            raise PermissionError(
                "Sem acesso ao documento. Verifique se o Google Doc está compartilhado como "
                "\"Qualquer pessoa com o link pode ver\"."
            )
        raise PermissionError(f"Erro ao acessar o documento (HTTP {e.code}).")


def _clean_google_style(style_str: str) -> dict:
    """Parseia um atributo style inline e retorna um dict."""
    props = {}
    if not style_str:
        return props
    for part in style_str.split(';'):
        part = part.strip()
        if ':' in part:
            key, value = part.split(':', 1)
            props[key.strip().lower()] = value.strip()
    return props


def _font_size_pt(style: dict) -> float:
    """Extrai o font-size em pt de um dict de estilos CSS."""
    fs = style.get('font-size', '')
    match = re.match(r'([\d.]+)\s*pt', fs)
    if match:
        return float(match.group(1))
    match = re.match(r'([\d.]+)\s*px', fs)
    if match:
        return float(match.group(1)) * 0.75  # px -> pt aprox.
    return 0


def _detect_heading_level(font_size_pt: float, text_length: int) -> int:
    """
    Detecta o nível de heading baseado no tamanho da fonte e comprimento do texto.
    Retorna 0 se não for heading.
    """
    if font_size_pt <= 0 or text_length == 0:
        return 0
    # Textos muito longos provavelmente não são títulos
    if text_length > 200:
        return 0
    if font_size_pt >= 24:
        return 1
    if font_size_pt >= 18:
        return 2
    if font_size_pt >= 14:
        return 3
    if font_size_pt >= 13:
        return 4
    return 0


def _extract_image_urls(html_content: str) -> list:
    """Extrai URLs de imagens do HTML do Google Docs."""
    urls = []
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE):
        src = match.group(1)
        if src.startswith('data:'):
            continue
        urls.append(html_module.unescape(src))
    return urls


def html_to_markdown(html_content: str) -> str:
    """
    Converte HTML exportado do Google Docs para Markdown formatado Bonfire.
    """
    # 1. Extrair definições de CSS da tag <style> para mapear font-sizes das classes
    css_font_sizes = {}
    style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL | re.IGNORECASE)
    if style_matches:
        css_text = style_matches[0]
        for match in re.finditer(r'\.([a-zA-Z0-9_-]+)\s*\{([^}]+)\}', css_text):
            class_name = match.group(1)
            props = match.group(2)
            fs_match = re.search(r'font-size:\s*([\d.]+)pt', props)
            if fs_match:
                css_font_sizes[class_name] = float(fs_match.group(1))
            else:
                fs_px_match = re.search(r'font-size:\s*([\d.]+)px', props)
                if fs_px_match:
                    css_font_sizes[class_name] = float(fs_px_match.group(1)) * 0.75

    # Remove o head e scripts
    html_content = re.sub(r'<head[^>]*>.*?</head>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    image_counter = [0]
    
    def replace_img(match):
        tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', tag)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', tag)
        if src_match:
            src = html_module.unescape(src_match.group(1))
            if src.startswith('data:'):
                image_counter[0] += 1
                return f'\n![Imagem {image_counter[0]}](COLE_O_LINK_DA_IMAGEM_AQUI)\n'
            alt = alt_match.group(1) if alt_match else f'Imagem'
            return f'\n![{alt}]({src})\n'
        return ''
    
    html_content = re.sub(r'<img[^>]*/?>', replace_img, html_content, flags=re.IGNORECASE)
    
    def replace_link(match):
        attrs = match.group(1)
        text = match.group(2)
        href_match = re.search(r'href=["\']([^"\']+)["\']', attrs)
        if href_match:
            href = html_module.unescape(href_match.group(1))
            if 'google.com/url' in href:
                q_match = re.search(r'[?&]q=([^&]+)', href)
                if q_match:
                    href = urllib.request.unquote(q_match.group(1))
            clean_text = re.sub(r'<[^>]+>', '', text).strip()
            if clean_text:
                return f'[{clean_text}]({href})'
        return re.sub(r'<[^>]+>', '', text)
    
    html_content = re.sub(r'<a\s+([^>]*)>(.*?)</a>', replace_link, html_content, flags=re.DOTALL | re.IGNORECASE)
    
    html_content = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<u[^>]*>(.*?)</u>', r'__\1__', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    html_content = re.sub(r'<ul[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ul>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<ol[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ol>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    def process_paragraph(match):
        p_attrs = match.group(1) or ''
        p_content = match.group(2)
        
        max_font_size = 0
        
        # 1. Verificar tamanho de fonte nas classes do parágrafo
        p_class_match = re.search(r'class=["\']([^"\']*)["\']', p_attrs)
        if p_class_match:
            for c in p_class_match.group(1).split():
                if c in css_font_sizes and css_font_sizes[c] > max_font_size:
                    max_font_size = css_font_sizes[c]
        
        # 2. Verificar estilo inline do parágrafo
        p_style_match = re.search(r'style=["\']([^"\']*)["\']', p_attrs)
        if p_style_match:
            p_style = _clean_google_style(p_style_match.group(1))
            p_fs = _font_size_pt(p_style)
            if p_fs > max_font_size:
                max_font_size = p_fs
                
        # 3. Verificar spans internos (classes e estilos inline)
        span_matches = re.finditer(r'<span([^>]*)>', p_content)
        for sm in span_matches:
            span_attrs = sm.group(1)
            # span classes
            span_class_match = re.search(r'class=["\']([^"\']*)["\']', span_attrs)
            if span_class_match:
                for c in span_class_match.group(1).split():
                    if c in css_font_sizes and css_font_sizes[c] > max_font_size:
                        max_font_size = css_font_sizes[c]
            # span styles
            style_match = re.search(r'style=["\']([^"\']*)["\']', span_attrs)
            if style_match:
                style = _clean_google_style(style_match.group(1))
                fs = _font_size_pt(style)
                if fs > max_font_size:
                    max_font_size = fs
        
        clean_text = re.sub(r'<[^>]+>', '', p_content).strip()
        clean_text = html_module.unescape(clean_text)
        
        heading_level = _detect_heading_level(max_font_size, len(clean_text))
        
        if not clean_text:
            return '\n'
        
        if heading_level > 0:
            prefix = '#' * heading_level
            return f'\n{prefix} {clean_text}\n'
        
        return f'\n{clean_text}\n'
    
    html_content = re.sub(
        r'<p([^>]*)>(.*?)</p>',
        process_paragraph,
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    for level in range(1, 7):
        prefix = '#' * level
        html_content = re.sub(
            rf'<h{level}[^>]*>(.*?)</h{level}>',
            lambda m, p=prefix: f'\n{p} {re.sub(r"<[^>]+>", "", m.group(1)).strip()}\n',
            html_content,
            flags=re.DOTALL | re.IGNORECASE
        )
    
    html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<[^>]+>', '', html_content)
    html_content = html_module.unescape(html_content)
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    html_content = re.sub(r'[ \t]+', ' ', html_content)
    html_content = re.sub(r'\*\*\s*\*\*', '', html_content)
    html_content = re.sub(r'\*\s*\*', '', html_content)
    
    lines = html_content.strip().split('\n')
    cleaned_lines = [line.strip() for line in lines]
    
    return '\n'.join(cleaned_lines)


def import_google_doc(url_or_id: str) -> dict:
    """
    Importa um Google Doc público e retorna dict com titulo e conteudo_markdown.
    
    Raises:
        PermissionError: Se não tiver acesso ao documento.
    """
    doc_id = extract_doc_id(url_or_id)
    
    raw_html = fetch_doc_html(doc_id)
    
    # Extrair título do documento
    title_match = re.search(r'<title[^>]*>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
    titulo = html_module.unescape(title_match.group(1).strip()) if title_match else 'Documento Importado'
    
    # Converter para Markdown
    markdown = html_to_markdown(raw_html)
    
    return {
        'titulo': titulo,
        'conteudo_markdown': markdown,
        'doc_id': doc_id,
    }
