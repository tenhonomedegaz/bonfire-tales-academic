# -*- coding: utf-8 -*-
"""WP4 — wipe do conteúdo demo (F2/F3): PO pediu pra não manter nenhuma badge ou
conquista "do jeito que está" (ver docs/agentes/arquitetura_temas_dinamicos.md §2).

Remove:
  - Conquistas do seed 0052 ('sangue-de-dragao', 'ao-redor-da-fogueira') e as
    concessões (TbUsuarioConquista) ligadas a elas.
  - Títulos/badges do seed 0050 ('titulo-veterano-mesas', 'titulo-portador-chama-eterna',
    'badge-matador-dragoes', 'badge-primeira-fogueira') e a posse (TbUsuarioCosmetico)
    ligada a eles.
  - Referências penduradas em UserProfile: titulo_equipado apontando pra slug
    deletado vira '' e slugs deletados somem de badges_destaque (lista JSON).

NÃO mexe nas badges DERIVADAS (staff/apoiador/mestre-ouro/fundador) — são
computadas em home/badges.py, nunca existiram como linha em TbCosmetico.

Idempotente e segura em prod: filtra por slug: se o slug não existir (prod ainda
não rodou os seeds F2/F3, ou já foi limpo), os deletes/filtros são silenciosamente
no-op. Reverse é no-op — conteúdo demo não volta.
"""
from django.db import migrations


CONQUISTAS_SLUGS = ['sangue-de-dragao', 'ao-redor-da-fogueira']

TITULOS_SLUGS = ['titulo-veterano-mesas', 'titulo-portador-chama-eterna']
BADGES_SLUGS = ['badge-matador-dragoes', 'badge-primeira-fogueira']
COSMETICOS_DEMO_SLUGS = TITULOS_SLUGS + BADGES_SLUGS


def _wipe(apps, schema_editor):
    TbConquista = apps.get_model('home', 'TbConquista')
    TbUsuarioConquista = apps.get_model('home', 'TbUsuarioConquista')
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    TbUsuarioCosmetico = apps.get_model('home', 'TbUsuarioCosmetico')
    UserProfile = apps.get_model('home', 'UserProfile')

    # --- Conquistas demo -------------------------------------------------
    conquistas_qs = TbConquista.objects.filter(slug__in=CONQUISTAS_SLUGS)
    TbUsuarioConquista.objects.filter(conquista__in=conquistas_qs).delete()
    conquistas_qs.delete()

    # --- Títulos/badges demo ----------------------------------------------
    cosmeticos_qs = TbCosmetico.objects.filter(slug__in=COSMETICOS_DEMO_SLUGS)
    TbUsuarioCosmetico.objects.filter(cosmetico__in=cosmeticos_qs).delete()
    cosmeticos_qs.delete()

    # --- Referências penduradas em UserProfile -----------------------------
    # titulo_equipado: limpa quem tinha um dos títulos demo equipado.
    UserProfile.objects.filter(titulo_equipado__in=TITULOS_SLUGS).update(titulo_equipado='')

    # badges_destaque (JSON list): remove os slugs demo de quem os fixou na
    # vitrine. Só toca perfis que realmente contêm algum slug alvo.
    demo_set = set(COSMETICOS_DEMO_SLUGS)
    for perfil in UserProfile.objects.all():
        raw = perfil.badges_destaque
        if not isinstance(raw, list) or not raw:
            continue
        limpos = [s for s in raw if s not in demo_set]
        if len(limpos) != len(raw):
            perfil.badges_destaque = limpos
            perfil.save(update_fields=['badges_destaque'])


def _noop(apps, schema_editor):
    # Conteúdo demo não volta — reverse intencionalmente vazio.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0055_tbconquista_icone_file_tbcosmetico_asset_file_and_more'),
    ]

    operations = [
        migrations.RunPython(_wipe, _noop),
    ]
