"""Bounded presentation metadata. No image fetch, uploads or movement rules."""
import math

from .editorial_links import safe_editorial_image


def _number(value, low, high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Parametro visual fora do intervalo permitido.')
    return value


def validate_presentation(value):
    if type(value) is not dict or set(value) != {'background','grid_opacity'}:
        raise ValueError('Configuracao visual invalida.')
    grid=_number(value['grid_opacity'],0,1)
    background=value['background']
    if background is not None:
        if type(background) is not dict or set(background) != {'url','cell_px','origin_x','origin_y','opacity'}:
            raise ValueError('Calibracao da imagem invalida.')
        raw=background['url']
        if not isinstance(raw,str) or len(raw)>2048:
            raise ValueError('URL da imagem invalida.')
        url=safe_editorial_image(raw)
        if not url or not (url.startswith('https://') or url.startswith('/')):
            raise ValueError('Use imagem HTTPS ou caminho /static/ ou /media/.')
        background={'url':url,'cell_px':_number(background['cell_px'],1,4096),
                    'origin_x':_number(background['origin_x'],-32768,32768),
                    'origin_y':_number(background['origin_y'],-32768,32768),
                    'opacity':_number(background['opacity'],0,1)}
    return {'background':background,'grid_opacity':grid}
