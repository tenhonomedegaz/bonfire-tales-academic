import json
from datetime import date, datetime
from decimal import Decimal

from django.db import connection


class BotMongoUnavailable(RuntimeError):
    pass


DatabaseUnavailable = BotMongoUnavailable


def _quote_name(name):
    return connection.ops.quote_name(name)


def _table_names():
    with connection.cursor() as cursor:
        return set(connection.introspection.table_names(cursor))


def _ensure_table(table_name):
    if table_name not in _table_names():
        raise BotMongoUnavailable(f"Tabela PostgreSQL nao encontrada: {table_name}")
    return table_name


def _columns(table_name):
    table_name = _ensure_table(table_name)
    with connection.cursor() as cursor:
        return [column.name for column in connection.introspection.get_table_description(cursor, table_name)]


def serialize_mongo_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, dict)):
        return value
    return value


def serialize_document(document):
    return {key: serialize_mongo_value(value) for key, value in (document or {}).items()}


def _row_to_document(columns, row):
    return serialize_document(dict(zip(columns, row)))


def _json_value(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _document_pk(document):
    return document.get("id") or document.get("_id") or next(iter(document.values()), "")


def _searchable_columns(table_name):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    text_types = {"CharField", "TextField", "SlugField", "EmailField", "URLField"}
    searchable = []
    for column in description:
        try:
            field_type = connection.introspection.get_field_type(column.type_code, column)
        except Exception:
            field_type = ""
        if field_type in text_types or str(field_type).endswith("Field"):
            searchable.append(column.name)
    return searchable


def _where_search(table_name, search):
    search = (search or "").strip()
    if not search:
        return "", []
    columns = _searchable_columns(table_name)
    if not columns:
        return "", []
    clauses = [f"CAST({_quote_name(column)} AS TEXT) ILIKE %s" for column in columns]
    return f" WHERE {' OR '.join(clauses)}", [f"%{search}%"] * len(columns)


def _order_column(table_name):
    columns = _columns(table_name)
    for preferred in ("id", "Id", "createdAt", "created_at", "Nome", "name"):
        if preferred in columns:
            return preferred
    return columns[0] if columns else None


def list_collection_summaries():
    summaries = []
    with connection.cursor() as cursor:
        table_names = sorted(connection.introspection.table_names(cursor))
        django_tables = {"auth_", "django_", "admin_", "sessions"}
        for table_name in table_names:
            columns = [column.name for column in connection.introspection.get_table_description(cursor, table_name)]
            cursor.execute(f"SELECT COUNT(*) FROM {_quote_name(table_name)}")
            count = cursor.fetchone()[0]
            kind = "django" if table_name.startswith(tuple(django_tables)) else "app"
            if table_name.startswith(("rpg_", "discord_", "transactions", "dedicated-", "store_")):
                kind = "bot"
            summaries.append({
                "name": table_name,
                "count": count,
                "sample_keys": columns[:12],
                "database": connection.settings_dict.get("NAME", ""),
                "kind": kind,
            })
    return summaries


def collection_document_count(collection_name, search=""):
    table_name = _ensure_table(collection_name)
    where_sql, params = _where_search(table_name, search)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {_quote_name(table_name)}{where_sql}", params)
        return cursor.fetchone()[0]


def find_documents(collection_name, search="", limit=50, skip=0):
    table_name = _ensure_table(collection_name)
    columns = _columns(table_name)
    order_column = _order_column(table_name)
    where_sql, params = _where_search(table_name, search)
    order_sql = f" ORDER BY {_quote_name(order_column)} ASC" if order_column else ""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM {_quote_name(table_name)}{where_sql}{order_sql} LIMIT %s OFFSET %s",
            [*params, int(limit), int(skip)],
        )
        return [_row_to_document(columns, row) for row in cursor.fetchall()]


def get_document(collection_name, document_id):
    table_name = _ensure_table(collection_name)
    columns = _columns(table_name)
    with connection.cursor() as cursor:
        pk_column = connection.introspection.get_primary_key_column(cursor, table_name)
        pk_column = pk_column or ("id" if "id" in columns else columns[0])
        cursor.execute(
            f"SELECT * FROM {_quote_name(table_name)} WHERE CAST({_quote_name(pk_column)} AS TEXT) = %s LIMIT 1",
            [str(document_id)],
        )
        row = cursor.fetchone()
    return _row_to_document(columns, row) if row else None


def save_document(collection_name, document):
    raise BotMongoUnavailable("Edicao generica direta foi desativada. Use os ModelAdmins do Django para alterar dados PostgreSQL.")


def delete_document(collection_name, document_id):
    raise BotMongoUnavailable("Exclusao generica direta foi desativada. Use os ModelAdmins do Django para alterar dados PostgreSQL.")


def find_published_quests(search="", status="", limit=100):
    table_name = _ensure_table("rpg_quests")
    where = ['"isPublished" = TRUE']
    params = []

    if status:
        where.append("status = %s")
        params.append(status)
    else:
        where.append("status <> %s")
        params.append("finished")

    if search:
        where.append("(name ILIKE %s OR description ILIKE %s OR type ILIKE %s OR array_to_string(tags, ',') ILIKE %s)")
        term = f"%{search.replace('%', '').replace('_', '')}%"
        params.extend([term, term, term, term])

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT *
            FROM {_quote_name(table_name)}
            WHERE {" AND ".join(where)}
            ORDER BY "questDate" ASC, "createdAt" DESC
            LIMIT %s
            """,
            [*params, int(limit)],
        )
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    quests = []
    for row in rows:
        quest = _row_to_document(columns, row)
        quest["_id"] = quest.get("id")
        quest["subscribedPlayers"] = _json_value(quest.get("subscribedPlayers"), [])
        quest["questPlayers"] = _json_value(quest.get("questPlayers"), [])
        quest["participationRequests"] = _json_value(quest.get("participationRequests"), [])
        quest["timeEvents"] = _json_value(quest.get("timeEvents"), [])
        quests.append(quest)
    return quests


def count_documents(collection_name):
    return collection_document_count(collection_name)


def get_collection(name):
    return name


def get_bot_database():
    raise BotMongoUnavailable("Acesso Mongo legado foi removido. Use PostgreSQL via Django/Prisma.")
