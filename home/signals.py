import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.utils.text import slugify

from .models import (
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbCronica,
    TbEssencia,
    TbJornal,
    TbLinhagem,
    TbMapMarker,
    TbOpcaojogo,
    TbRaca,
    TbRecursoclasse,
    TbRegiao,
    TbSubclasse,
    TbTalento,
    TbTerritorio,
    TbTracoracial,
)
from .security import find_sql_danger


logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def reconcile_registered_master_on_login(sender, user, **kwargs):
    # Password login must also repair claims for an already verified Discord link.
    from django.db import DatabaseError, transaction
    from .master_legacy import claim_discord_masters
    discord_id = str(getattr(getattr(user, 'profile', None), 'discord_user_id', '') or '')
    try:
        with transaction.atomic():
            claim_discord_masters(user, discord_id)
    except (DatabaseError, ValidationError):
        logger.warning('Conciliacao de mestre pendente para conta %s; login preservado.', user.pk)


@receiver(post_save, sender='home.TbPersonagem')
@receiver(post_save, sender='home.TbPersonagemClasse')
def grant_permanent_rank_cosmetics(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from .models import TbPersonagem
    from .rank_cosmetic_rewards import sync_rank_cosmetics
    character = instance if sender is TbPersonagem else instance.id_personagem
    sync_rank_cosmetics(character.dono)


SYNCED_MODELS = (
    TbAcessoopcao,
    TbClasse,
    TbClassehabilidade,
    TbCronica,
    TbEssencia,
    TbJornal,
    TbLinhagem,
    TbMapMarker,
    TbOpcaojogo,
    TbRaca,
    TbRecursoclasse,
    TbRegiao,
    TbSubclasse,
    TbTalento,
    TbTerritorio,
    TbTracoracial,
)



_syncing_region_marker = False


@receiver(pre_save)
def block_dangerous_sql_text(sender, instance, **kwargs):
    if kwargs.get('raw', False):
        return
    if sender not in SYNCED_MODELS:
        return

    errors = []
    for field in sender._meta.fields:
        if isinstance(field, (models.CharField, models.TextField)):
            errors.extend(find_sql_danger(getattr(instance, field.name, None), field.verbose_name or field.name))

    if errors:
        raise ValidationError({"__all__": ["Texto bloqueado por conter comando SQL potencialmente destrutivo."]})


def _unique_slug(base):
    
    slug = slugify(base) or 'regiao'
    candidate = slug
    counter = 2
    while TbRegiao.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _shared_fields_from_marker(marker):
    
    return {
        'nome': marker.nome,
        'territorio': marker.territorio or '',
        'categoria': marker.categoria or 'cidade',
        'camada': marker.camada,
    }


@receiver(pre_save, sender=TbMapMarker)
def capture_original_marker_name(sender, instance, **kwargs):
    if instance.pk:
        orig = TbMapMarker.objects.filter(pk=instance.pk).first()
        if orig:
            instance._original_nome = orig.nome


@receiver(pre_save, sender=TbRegiao)
def capture_original_region_name(sender, instance, **kwargs):
    if instance.pk:
        orig = TbRegiao.objects.filter(pk=instance.pk).first()
        if orig:
            instance._original_nome = orig.nome


@receiver(post_save, sender=TbMapMarker)
def auto_create_region_from_marker(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    
    global _syncing_region_marker
    if _syncing_region_marker:
        return

    slug = slugify(instance.nome)
    if not slug:
        return

    _syncing_region_marker = True
    try:
        if created:
            if not TbRegiao.objects.filter(models.Q(slug=slug) | models.Q(nome=instance.nome)).exists():
                TbRegiao.objects.create(
                    slug=slug,
                    **_shared_fields_from_marker(instance),
                )
        else:
            orig_nome = getattr(instance, '_original_nome', None)
            search_name = orig_nome if orig_nome else instance.nome
            region = TbRegiao.objects.filter(nome=search_name).first()
            if region:
                region.nome = instance.nome
                new_slug = slugify(instance.nome) or 'regiao'
                candidate = new_slug
                counter = 2
                while TbRegiao.objects.filter(slug=candidate).exclude(pk=region.pk).exists():
                    candidate = f"{new_slug}-{counter}"
                    counter += 1
                region.slug = candidate
                region.territorio = instance.territorio or ''
                region.categoria = instance.categoria or 'cidade'
                region.camada = instance.camada
                region.save()
    finally:
        _syncing_region_marker = False


@receiver(post_save, sender=TbRegiao)
def auto_create_marker_from_region(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    
    global _syncing_region_marker
    if _syncing_region_marker:
        return

    slug = instance.slug
    if not slug:
        return

    _syncing_region_marker = True
    try:
        if created:
            existing = TbMapMarker.objects.filter(nome=instance.nome).first()
            if not existing:
                TbMapMarker.objects.create(
                    nome=instance.nome,
                    lat=0,
                    lng=0,
                    categoria=instance.categoria or 'cidade',
                    territorio=instance.territorio or '',
                    camada=instance.camada,
                )
        else:
            orig_nome = getattr(instance, '_original_nome', None)
            search_name = orig_nome if orig_nome else instance.nome
            marker = TbMapMarker.objects.filter(nome=search_name).first()
            if marker:
                marker.nome = instance.nome
                marker.categoria = instance.categoria or 'cidade'
                marker.territorio = instance.territorio or ''
                marker.camada = instance.camada
                marker.save()
    finally:
        _syncing_region_marker = False
