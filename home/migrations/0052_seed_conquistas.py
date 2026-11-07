# -*- coding: utf-8 -*-
"""F3 — seed mínimo de conquistas + prova da recompensa caindo no inventário.

Cadastra ~2 conquistas ligadas às recompensas que a F2 semeou:
  - "Sangue de Dragão"     → recompensa = badge "Matador de Dragões" (badge-matador-dragoes)
  - "Ao Redor da Fogueira" → recompensa = badge "Primeira Fogueira"  (badge-primeira-fogueira)

Concede "Sangue de Dragão" ao admin do dev (se existir) reproduzindo a lógica de
`conquistas.conceder_conquista` com modelos históricos (migrations não devem
importar código de runtime): cria TbUsuarioConquista e materializa a recompensa em
TbUsuarioCosmetico com origem 'conquista:<slug>'. Idempotente (get_or_create).

Em produção (catálogo sincronizado por loaddata) o grant não acha 'admin' e é
no-op inofensivo. As conquistas em si sincronizam por slug (CONTENT).
"""
from django.db import migrations


# (slug, nome, descricao, recompensa_slug, secreta, ordem)
CONQUISTAS = [
    ('sangue-de-dragao', 'Sangue de Dragão',
     'Derrotou um dragão em uma mesa oficial da comunidade.',
     'badge-matador-dragoes', False, 0),
    ('ao-redor-da-fogueira', 'Ao Redor da Fogueira',
     'Participou de uma das primeiras mesas da comunidade.',
     'badge-primeira-fogueira', False, 1),
]


def _seed(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    TbConquista = apps.get_model('home', 'TbConquista')
    TbUsuarioConquista = apps.get_model('home', 'TbUsuarioConquista')
    TbUsuarioCosmetico = apps.get_model('home', 'TbUsuarioCosmetico')
    User = apps.get_model('auth', 'User')

    por_slug = {}
    for slug, nome, desc, recompensa_slug, secreta, ordem in CONQUISTAS:
        recompensa = TbCosmetico.objects.filter(slug=recompensa_slug).first()
        cos, _ = TbConquista.objects.get_or_create(
            slug=slug,
            defaults={
                'nome': nome,
                'descricao': desc,
                'secreta': secreta,
                'criterio': 'manual',
                'recompensa': recompensa,
                'ordem': ordem,
                'ativo': True,
            },
        )
        # Garante a recompensa ligada mesmo se a conquista já existia sem ela.
        if recompensa and cos.recompensa_id != recompensa.id:
            cos.recompensa = recompensa
            cos.save(update_fields=['recompensa'])
        por_slug[slug] = cos

    # Concede 1 conquista ao admin do dev, provando a recompensa no inventário.
    admin = (User.objects.filter(username='admin').first()
             or User.objects.filter(is_superuser=True).order_by('pk').first())
    if not admin:
        return
    conq = por_slug.get('sangue-de-dragao')
    if not conq:
        return
    TbUsuarioConquista.objects.get_or_create(
        user=admin, conquista=conq, defaults={'concedida_por': admin})
    if conq.recompensa_id:
        recompensa = TbCosmetico.objects.filter(pk=conq.recompensa_id).first()
        if recompensa:
            TbUsuarioCosmetico.objects.get_or_create(
                user=admin, cosmetico=recompensa,
                defaults={'origem': 'conquista:%s' % conq.slug})


def _unseed(apps, schema_editor):
    TbConquista = apps.get_model('home', 'TbConquista')
    slugs = [s for (s, *_r) in CONQUISTAS]
    # CASCADE remove as concessões junto. Não removemos o cosmético (é da F2).
    TbConquista.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0051_tbconquista_tbusuarioconquista'),
    ]

    operations = [
        migrations.RunPython(_seed, _unseed),
    ]
