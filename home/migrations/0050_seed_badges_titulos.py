# -*- coding: utf-8 -*-
"""F2 — seed mínimo de títulos e badges de comunidade (testabilidade).

Cadastra ~2 títulos e ~2 badges com origem='evento_manual' (concedíveis por staff,
NÃO 'livre' — quem não recebeu não os tem). Concede 1 título + 1 badge ao usuário
admin do dev (se existir) só pra a verificação mostrar renderizando.

Idempotente (get_or_create por slug / user+cosmetico). O grant ao admin só ocorre
em bases com um superusuário — em produção, onde o catálogo é sincronizado por
loaddata, o grant simplesmente não acha 'admin' e é no-op inofensivo.
"""
from django.db import migrations


# (slug, tipo, nome, descricao, raridade, asset_url)
TITULOS = [
    ('titulo-veterano-mesas', 'titulo', 'Veterano das Mesas',
     'Concedido a quem acumulou muitas horas de jogo à mesa.', 'raro', ''),
    ('titulo-portador-chama-eterna', 'titulo', 'Portador da Chama Eterna',
     'Guardião da fogueira — presença marcante na comunidade.', 'lendario', ''),
]

BADGES = [
    # asset_url guarda um glyph emoji nativo (renderizado como texto, sem CDN externo).
    ('badge-matador-dragoes', 'badge', 'Matador de Dragões',
     'Derrotou um dragão em uma mesa oficial.', 'epico', '🐉'),
    ('badge-primeira-fogueira', 'badge', 'Primeira Fogueira',
     'Participou de uma das primeiras mesas da comunidade.', 'raro', '🔥'),
]


def _seed(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    todos = []
    for ordem, (slug, tipo, nome, desc, rar, asset) in enumerate(TITULOS + BADGES):
        cos, _ = TbCosmetico.objects.get_or_create(
            slug=slug,
            defaults={
                'tipo': tipo,
                'nome': nome,
                'descricao': desc,
                'raridade': rar,
                'asset_url': asset,
                'origem': 'evento_manual',
                'escopo': 'perfil',
                'ativo': True,
                'ordem': ordem,
            },
        )
        todos.append((slug, cos))

    # Grant ao admin do dev (idempotente). Pega o superusuário 'admin' se existir.
    User = apps.get_model('auth', 'User')
    TbUsuarioCosmetico = apps.get_model('home', 'TbUsuarioCosmetico')
    admin = (User.objects.filter(username='admin').first()
             or User.objects.filter(is_superuser=True).order_by('pk').first())
    if not admin:
        return
    por_slug = dict(todos)
    for slug in ('titulo-veterano-mesas', 'badge-matador-dragoes'):
        cos = por_slug.get(slug)
        if cos:
            TbUsuarioCosmetico.objects.get_or_create(
                user=admin, cosmetico=cos, defaults={'origem': 'seed'})

    # Equipa o título concedido no perfil do admin (só se ainda não tiver título).
    UserProfile = apps.get_model('home', 'UserProfile')
    perfil = UserProfile.objects.filter(user=admin).first()
    if perfil and not (perfil.titulo_equipado or '').strip():
        perfil.titulo_equipado = 'titulo-veterano-mesas'
        perfil.save(update_fields=['titulo_equipado'])


def _unseed(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    slugs = [s for (s, *_r) in (TITULOS + BADGES)]
    # Remove os grants e depois os cosméticos (CASCADE cobriria, mas explícito é seguro).
    TbCosmetico.objects.filter(slug__in=slugs, origem='evento_manual').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0049_userprofile_badges_titulo'),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
