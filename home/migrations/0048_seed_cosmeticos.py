# -*- coding: utf-8 -*-
"""Seed do catálogo de cosméticos (F1) a partir dos dicts APPEARANCE_* de views.py.

Cada tema/moldura/efeito atual vira uma linha de TbCosmetico com origem='livre'
e escopo='ambos' — assim NINGUÉM perde acesso e a tela não muda (zero regressão).
`animado` é inferido do CSS (perfil.css): molduras animadas (todas têm ::before
girando) e efeitos com keyframes (embers/aurora/starfall). Idempotente
(get_or_create por slug) — pode rodar de novo sem duplicar.

O `slug` do catálogo é GLOBALMENTE único (exigência do modelo e do sync por slug),
então é prefixado pelo tipo: '<tipo>-<valor>' (ex.: 'tema-verdant', 'moldura-verdant',
'moldura-none', 'efeito-none'). O VALOR bruto que perfil/ficha guardam ('verdant',
'none'…) é recuperado por get_catalog removendo o prefixo '<tipo>-'. Isso resolve
as colisões de valor entre tipos (none em moldura+efeito; verdant em tema+moldura).

Os dados são embutidos aqui de propósito (migrations não devem importar de views.py,
que pode mudar). Se novos cosméticos forem adicionados, cadastre-os pelo admin.
"""
from django.db import migrations

# (valor, tipo, nome, css_class, animado) — valor = o que perfil/ficha armazenam.
COSMETICOS = [
    # ── Temas (redefinem CSS custom properties; sem keyframes por padrão) ──
    ('bonfire', 'tema', 'Bonfire', 'theme-bonfire', False),
    ('ember', 'tema', 'Brasas de Cineria', 'theme-ember', False),
    ('arcane', 'tema', 'Arcano Violeta', 'theme-arcane', False),
    ('verdant', 'tema', 'Bosque Esmeralda', 'theme-verdant', False),
    ('moonlit', 'tema', 'Luar Prateado', 'theme-moonlit', False),
    # 'custom' é a opção "Personalizado" (cores inline validadas). Livre também.
    ('custom', 'tema', 'Personalizado', 'theme-custom', False),

    # ── Molduras (todas com ::before girando/pulsando exceto 'none') ──
    ('none', 'moldura', 'Sem moldura', '', False),
    ('ember-ring', 'moldura', 'Anel de Brasa', 'frame-ember-ring', True),
    ('arcane-pulse', 'moldura', 'Pulso Arcano', 'frame-arcane-pulse', True),
    ('gold-trim', 'moldura', 'Friso Dourado', 'frame-gold-trim', True),
    ('frost', 'moldura', 'Coroa de Gelo', 'frame-frost', True),
    ('verdant', 'moldura', 'Trança Verdejante', 'frame-verdant', True),

    # ── Efeitos ──
    ('none', 'efeito', 'Sem efeito', '', False),
    ('soft-glow', 'efeito', 'Brilho suave', 'effect-soft-glow', False),
    ('glass', 'efeito', 'Vidro escuro', 'effect-glass', False),
    ('embers', 'efeito', 'Brasas discretas', 'effect-embers', True),
    ('aurora', 'efeito', 'Aurora', 'effect-aurora', True),
    ('starfall', 'efeito', 'Chuva de estrelas', 'effect-starfall', True),
]


def _slug(tipo, valor):
    return '%s-%s' % (tipo, valor)


def seed_cosmeticos(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    for ordem, (valor, tipo, nome, css_class, animado) in enumerate(COSMETICOS):
        TbCosmetico.objects.get_or_create(
            slug=_slug(tipo, valor),
            defaults={
                'tipo': tipo,
                'nome': nome,
                'css_class': css_class,
                'animado': animado,
                'origem': 'livre',
                'escopo': 'ambos',
                'raridade': 'comum',
                'ativo': True,
                'ordem': ordem,
            },
        )


def unseed_cosmeticos(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    for valor, tipo, *_rest in COSMETICOS:
        TbCosmetico.objects.filter(slug=_slug(tipo, valor), origem='livre').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0047_tbcosmetico_tbusuariocosmetico'),
    ]

    operations = [
        migrations.RunPython(seed_cosmeticos, unseed_cosmeticos),
    ]
