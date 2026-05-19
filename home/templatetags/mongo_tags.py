from django import template
from home.bot_mongo import list_collection_summaries, BotMongoUnavailable

register = template.Library()

@register.simple_tag
def get_mongo_collections():
    try:
        return list_collection_summaries()
    except BotMongoUnavailable:
        return []


@register.filter
def mongo_kind(collection, kind):
    if isinstance(collection, dict):
        return collection.get("kind") == kind
    return False


@register.simple_tag
def site_mongo_collection(key):
    return key
