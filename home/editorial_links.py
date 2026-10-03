"""Destinos permitidos para chamadas editoriais da Home."""

from urllib.parse import urlsplit


def safe_editorial_link(value):
    """Aceita caminhos locais e links HTTP(S), sem esquemas executáveis."""
    if not isinstance(value, str) or not value or value != value.strip():
        return ''
    if any(ord(char) < 33 or char == '\\' for char in value):
        return ''
    if value.startswith('/'):
        return value if not value.startswith('//') else ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc:
            return ''
        if not parsed.hostname or parsed.username or parsed.password:
            return ''
        parsed.port  # Rejeita portas malformadas.
    except ValueError:
        return ''
    return value
