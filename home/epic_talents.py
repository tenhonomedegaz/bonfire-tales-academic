"""Classificação de talentos épicos no campo de etiquetas já existente."""


def is_epic_talent(talent):
    """Reconhece a etiqueta exata, sem depender do nome ou da categoria do talento."""
    labels = getattr(talent, "etiquetas_adicionais", None) or ""
    return "epico" in {label.strip().casefold() for label in labels.split(",")}
