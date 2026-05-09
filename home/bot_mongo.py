import re
from datetime import datetime
from itertools import islice

from django.conf import settings

try:
    from bson import ObjectId
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:  
    ObjectId = None
    MongoClient = None

    class PyMongoError(Exception):
        pass


_client = None


class BotMongoUnavailable(RuntimeError):
    pass


def _get_client():
    global _client

    if MongoClient is None:
        raise BotMongoUnavailable("Instale pymongo para acessar o banco Mongo do bot.")

    uri = getattr(settings, "BOT_MONGO_URI", "")
    if not uri:
        raise BotMongoUnavailable("Configure BOT_MONGO_URI ou DATABASE_URL com a URL do Mongo do bot.")

    if _client is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=2500)

    return _client


def get_bot_database():
    client = _get_client()
    database_name = getattr(settings, "BOT_MONGO_DATABASE", "")

    try:
        client.admin.command("ping")
        if database_name:
            return client[database_name]

        try:
            return client.get_default_database()
        except Exception:
            pass

        known_collections = set(getattr(settings, "BOT_MONGO_COLLECTIONS", {}).values())
        for candidate_name in client.list_database_names():
            if candidate_name in {"admin", "config", "local"}:
                continue
            candidate = client[candidate_name]
            if known_collections.intersection(candidate.list_collection_names()):
                return candidate

        raise BotMongoUnavailable(
            "Nenhum database com as colecoes do bot foi encontrado. Configure BOT_MONGO_DATABASE."
        )
    except Exception as exc:
        if isinstance(exc, BotMongoUnavailable):
            raise
        raise BotMongoUnavailable(str(exc)) from exc


def get_collection(name):
    collection_name = settings.BOT_MONGO_COLLECTIONS[name]
    return get_bot_database()[collection_name]


def serialize_mongo_value(value):
    if ObjectId is not None and isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_mongo_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_mongo_value(item) for key, item in value.items()}
    return value


def serialize_document(document):
    return serialize_mongo_value(document or {})


def find_published_quests(search="", status="", limit=100):
    collection = get_collection("quests")
    query = {"isPublished": True}

    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "finished"}

    if search:
        escaped_search = re.escape(search)
        query["$or"] = [
            {"name": {"$regex": escaped_search, "$options": "i"}},
            {"description": {"$regex": escaped_search, "$options": "i"}},
            {"tags": {"$regex": escaped_search, "$options": "i"}},
            {"type": {"$regex": escaped_search, "$options": "i"}},
        ]

    cursor = (
        collection.find(query)
        .sort([("questDate", 1), ("createdAt", -1)])
        .limit(limit)
    )
    return [serialize_document(document) for document in cursor]


def count_documents(collection_name):
    return get_collection(collection_name).count_documents({})


def list_collection_summaries():
    database = get_bot_database()
    site_collections = set(getattr(settings, "SITE_MONGO_COLLECTIONS", {}).values())
    if not site_collections:
        site_collections = {
            value for value in getattr(settings, "BOT_MONGO_COLLECTIONS", {}).values()
            if value in {"spells", "backgrounds", "bestiary", "organizations"} or str(value).startswith("site_")
        }
    bot_collections = set(getattr(settings, "BOT_MONGO_COLLECTIONS", {}).values()) - site_collections
    summaries = []
    for collection_name in sorted(database.list_collection_names()):
        collection = database[collection_name]
        try:
            count = collection.estimated_document_count()
            sample = serialize_document(collection.find_one())
        except PyMongoError:
            count = 0
            sample = {}
        summaries.append({
            "name": collection_name,
            "count": count,
            "sample_keys": sorted(sample.keys())[:12],
            "database": database.name,
            "kind": "site" if collection_name in site_collections or collection_name.startswith("site_") else ("bot" if collection_name in bot_collections else "other"),
        })
    return summaries


def collection_document_count(collection_name, search=""):
    collection = get_bot_database()[collection_name]
    query = _document_search_query(collection, search)
    return collection.count_documents(query)


def find_documents(collection_name, search="", limit=50, skip=0):
    collection = get_bot_database()[collection_name]
    query = _document_search_query(collection, search)
    cursor = collection.find(query).sort([("_id", 1)]).skip(skip).limit(limit)
    return [serialize_document(document) for document in cursor]


def _document_search_query(collection, search=""):
    query = {}
    if search:
        escaped_search = re.escape(search)
        query = {"$or": [
            {key: {"$regex": escaped_search, "$options": "i"}}
            for key in _guess_searchable_fields(collection)
        ]}
    return query


def _document_id_candidates(document_id):
    candidates = [document_id]
    if ObjectId is not None:
        try:
            candidates.append(ObjectId(document_id))
        except Exception:
            pass
    return candidates


def get_document(collection_name, document_id):
    collection = get_bot_database()[collection_name]
    for candidate in _document_id_candidates(document_id):
        document = collection.find_one({"_id": candidate})
        if document:
            return serialize_document(document)
    return None


def save_document(collection_name, document):
    collection = get_bot_database()[collection_name]
    document = dict(document or {})
    document_id = document.get("_id")

    if document_id in ("", None):
        document.pop("_id", None)
        result = collection.insert_one(document)
        return str(result.inserted_id)

    original_id = document_id
    for candidate in _document_id_candidates(str(document_id)):
        existing = collection.find_one({"_id": candidate})
        if existing:
            document["_id"] = candidate
            collection.replace_one({"_id": candidate}, document, upsert=True)
            return str(candidate)

    document["_id"] = original_id
    collection.replace_one({"_id": original_id}, document, upsert=True)
    return str(original_id)


def delete_document(collection_name, document_id):
    collection = get_bot_database()[collection_name]
    for candidate in _document_id_candidates(document_id):
        result = collection.delete_one({"_id": candidate})
        if result.deleted_count:
            return True
    return False


def _guess_searchable_fields(collection):
    fields = set()
    for document in islice(collection.find({}, {"_id": 0}).limit(10), 10):
        for key, value in document.items():
            if isinstance(value, str):
                fields.add(key)
    return sorted(fields) or ["name", "nome", "description", "descricao", "slug"]
