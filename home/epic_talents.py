"""Categoria epica explicita com compatibilidade para etiquetas legadas."""


def talent_category(tipo, labels=None):
    """Expose legacy general epics without overriding other explicit categories."""
    tipo = tipo or "geral"
    if tipo == "geral" and "epico" in {
        label.strip().casefold() for label in (labels or "").split(",")
    }:
        return "epico"
    return tipo


def is_epic_talent(talent):
    """Reconhece a categoria ou etiqueta exata, nunca o nome do talento."""
    return talent_category(getattr(talent, "tipo", None),
                           getattr(talent, "etiquetas_adicionais", None)) == "epico"
