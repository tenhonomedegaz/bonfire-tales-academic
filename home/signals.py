import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
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
from .sqlite_mongo_sync import sqlite_instance_to_mongo, delete_sqlite_instance_from_mongo
from .bot_mongo import BotMongoUnavailable


logger = logging.getLogger(__name__)


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
    if sender not in SYNCED_MODELS:
        return

    errors = []
    for field in sender._meta.fields:
        if isinstance(field, (models.CharField, models.TextField)):
            errors.extend(find_sql_danger(getattr(instance, field.name, None), field.verbose_name or field.name))

    if errors:
        raise ValidationError({"__all__": ["Texto bloqueado por conter comando SQL potencialmente destrutivo."]})


@receiver(post_save)
def auto_sync_mongo_on_save(sender, instance, **kwargs):
    if sender not in SYNCED_MODELS:
        return
    try:
        sqlite_instance_to_mongo(instance)
    except BotMongoUnavailable as e:
        logger.warning("MongoDB unavailable during post_save sync for %s: %s", sender.__name__, str(e))
    except Exception as e:
        logger.error("Error syncing %s to MongoDB: %s", sender.__name__, str(e), exc_info=True)


@receiver(post_delete)
def auto_sync_mongo_on_delete(sender, instance, **kwargs):
    if sender not in SYNCED_MODELS:
        return
    try:
        delete_sqlite_instance_from_mongo(instance)
    except BotMongoUnavailable as e:
        logger.warning("MongoDB unavailable during post_delete sync for %s: %s", sender.__name__, str(e))
    except Exception as e:
        logger.error("Error deleting %s from MongoDB: %s", sender.__name__, str(e), exc_info=True)




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
    }


@receiver(post_save, sender=TbMapMarker)
def auto_create_region_from_marker(sender, instance, created, **kwargs):
    
    global _syncing_region_marker
    if _syncing_region_marker:
        return

    slug = slugify(instance.nome)
    if not slug:
        return

    
    if not TbRegiao.objects.filter(models.Q(slug=slug) | models.Q(nome=instance.nome)).exists():
        _syncing_region_marker = True
        try:
            TbRegiao.objects.create(
                slug=slug,
                **_shared_fields_from_marker(instance),
            )
        finally:
            _syncing_region_marker = False


@receiver(post_save, sender=TbRegiao)
def auto_create_marker_from_region(sender, instance, created, **kwargs):
    
    global _syncing_region_marker
    if _syncing_region_marker:
        return

    slug = instance.slug
    if not slug:
        return

    
    existing = TbMapMarker.objects.filter(nome=instance.nome).first()
    if existing:
        return

    _syncing_region_marker = True
    try:
        TbMapMarker.objects.create(
            nome=instance.nome,
            lat=0,
            lng=0,
            categoria=instance.categoria or 'cidade',
            territorio=instance.territorio or '',
        )
    finally:
        _syncing_region_marker = False
