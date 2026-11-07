# -*- coding: utf-8 -*-
"""WP4 — tema como dado: backfill dos 5 temas legados + seed dos 6 temas basais
novos (ver docs/agentes/arquitetura_temas_dinamicos.md §1 e §4 — paletas EXATAS
da tabela normativa).

Backfill: os 5 cosméticos de tema já semeados em 0048 (slugs 'tema-bonfire',
'tema-ember', 'tema-arcane', 'tema-verdant', 'tema-moonlit') ganham
`definicao_json` SE E SOMENTE SE estiver vazio — não sobrescreve ajuste manual
de staff feito via admin depois do seed original.

Seed: 6 temas novos (origem='livre', escopo='ambos', ativo=True), com `ordem`
alocada depois dos temas existentes (preserva a posição de 'tema-custom' como
última opção "Personalizado" no seletor). get_or_create por slug — idempotente.

reverse: remove os 6 novos por slug; zera definicao_json dos 5 legados (volta
ao estado "sem definição" — render cai no legado theme-* hardcoded).
"""
from django.db import migrations


# Paletas dos 5 temas legados (backfill) — accent/accent2/surface/deep + grad/partícula/vel.
BACKFILL_LEGADOS = {
    'tema-bonfire': {
        'accent': '#F27007', 'accent2': '#D21717', 'surface': '#101012', 'deep': '#09090A',
        'gradiente': True, 'particula': 'subir', 'vel': 'media', 'glow': True,
    },
    'tema-ember': {
        'accent': '#F59E0B', 'accent2': '#7C2D12', 'surface': '#1B120F', 'deep': '#0E0A08',
        'gradiente': True, 'particula': 'subir', 'vel': 'media', 'glow': True,
    },
    'tema-arcane': {
        'accent': '#A78BFA', 'accent2': '#06B6D4', 'surface': '#151223', 'deep': '#090914',
        'gradiente': True, 'particula': 'flutuar', 'vel': 'lenta', 'glow': True,
    },
    'tema-verdant': {
        'accent': '#34D399', 'accent2': '#84CC16', 'surface': '#0E1A14', 'deep': '#07110C',
        'gradiente': True, 'particula': 'subir', 'vel': 'lenta', 'glow': True,
    },
    'tema-moonlit': {
        'accent': '#CBD5E1', 'accent2': '#60A5FA', 'surface': '#10151F', 'deep': '#080B10',
        'gradiente': True, 'particula': 'cair', 'vel': 'lenta', 'glow': True,
    },
}

# 6 temas basais novos: (slug, nome, accent, accent2, surface, deep, gradiente, particula, vel).
TEMAS_NOVOS = [
    ('tema-coracao-da-forja', 'Coração da Forja',
     '#FF7A1A', '#FFD166', '#1A0F08', '#0D0806', True, 'subir', 'rapida'),
    ('tema-abissal', 'Abissal',
     '#38E1FF', '#2563EB', '#071722', '#030B12', True, 'flutuar', 'lenta'),
    ('tema-bosque-ferico', 'Bosque Feérico',
     '#4ADE80', '#FACC15', '#0B1D12', '#05100A', False, 'flutuar', 'media'),
    ('tema-veu-lunar', 'Véu Lunar',
     '#E2E8F0', '#7DD3FC', '#0D1220', '#05070D', False, 'cair', 'lenta'),
    ('tema-sangue-e-ouro', 'Sangue & Ouro',
     '#EF4444', '#F59E0B', '#1C0A12', '#10050A', True, 'subir', 'media'),
    ('tema-tempestade-arcana', 'Tempestade Arcana',
     '#A78BFA', '#22D3EE', '#140F26', '#0A0716', True, 'flutuar', 'media'),
]

# Descrições curtas e evocativas em PT-BR (não fazem parte da tabela normativa,
# só texto de apresentação no seletor).
DESCRICOES_NOVOS = {
    'tema-coracao-da-forja': 'O calor da forja em brasa — laranja vivo sobre ouro quente.',
    'tema-abissal': 'Profundezas geladas do oceano — azul elétrico sobre o breu.',
    'tema-bosque-ferico': 'Luz feérica entre as árvores — verde e dourado da mata viva.',
    'tema-veu-lunar': 'Névoa prateada sob o luar — branco-azulado e silêncio.',
    'tema-sangue-e-ouro': 'Pacto selado em sangue e riqueza — vermelho intenso e ouro.',
    'tema-tempestade-arcana': 'Raios de magia rasgando a tempestade — violeta e ciano.',
}


def _definicao(accent, accent2, surface, deep, gradiente, particula, vel):
    return {
        'accent': accent, 'accent2': accent2, 'surface': surface, 'deep': deep,
        'gradiente': gradiente, 'particula': particula, 'vel': vel, 'glow': True,
    }


def _backfill_e_seed(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')

    # --- Backfill dos 5 legados: só preenche se definicao_json estiver vazio ---
    for slug, definicao in BACKFILL_LEGADOS.items():
        cos = TbCosmetico.objects.filter(slug=slug, tipo='tema').first()
        if cos is None:
            continue  # slug não existe nesta base (seed 0048 não rodou) — no-op seguro.
        if not cos.definicao_json:
            cos.definicao_json = definicao
            cos.save(update_fields=['definicao_json'])

    # --- Seed dos 6 novos: ordem alocada após os temas existentes ---
    ordem_base = TbCosmetico.objects.filter(tipo='tema').count()
    for i, (slug, nome, accent, accent2, surface, deep, gradiente, particula, vel) in enumerate(TEMAS_NOVOS):
        TbCosmetico.objects.get_or_create(
            slug=slug,
            defaults={
                'tipo': 'tema',
                'nome': nome,
                'descricao': DESCRICOES_NOVOS.get(slug, ''),
                'raridade': 'comum',
                'definicao_json': _definicao(accent, accent2, surface, deep, gradiente, particula, vel),
                'origem': 'livre',
                'escopo': 'ambos',
                'ativo': True,
                'ordem': ordem_base + i,
            },
        )


def _reverse(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')

    # Remove os 6 novos por slug.
    novos_slugs = [slug for (slug, *_r) in TEMAS_NOVOS]
    TbCosmetico.objects.filter(slug__in=novos_slugs, tipo='tema', origem='livre').delete()

    # Zera definicao_json dos 5 legados (volta pro estado "sem definição").
    TbCosmetico.objects.filter(slug__in=BACKFILL_LEGADOS.keys(), tipo='tema').update(definicao_json={})


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0056_wipe_conteudo_demo'),
    ]

    operations = [
        migrations.RunPython(_backfill_e_seed, _reverse),
    ]
