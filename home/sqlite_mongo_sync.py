import hashlib
import json
import re
import threading
from datetime import date, datetime, time
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from .bot_mongo import get_bot_database, serialize_document


DEFAULT_NAMESPACE = "site_sqlite"
MONGO_BACKUP_TABLE = "MongoBackupDocument"
SYNC_LOCK = threading.Lock()


def mongo_safe_collection(namespace, table_name):
    safe_table = re.sub(r"[^A-Za-z0-9_]+", "_", table_name).strip("_")
    return f"{namespace}_{safe_table}"


def sqlite_table_from_collection(collection_name, namespace=DEFAULT_NAMESPACE):
    prefix = f"{namespace}_"
    return collection_name[len(prefix):] if collection_name.startswith(prefix) else ""


def serialize_sqlite_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def stable_row_hash(row):
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalized_row(row):
    return {
        key: serialize_sqlite_value(value)
        for key, value in row.items()
        if not str(key).startswith("_")
    }


def table_names():
    return [
        table_name
        for table_name in connection.introspection.table_names()
        if table_name != MONGO_BACKUP_TABLE and table_name.startswith("TB_")
    ]


def table_info(cursor, table_name):
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    rows = cursor.fetchall()
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": row[3],
            "default": row[4],
            "pk": row[5],
        }
        for row in rows
    ]


def table_columns(cursor, table_name):
    return [column["name"] for column in table_info(cursor, table_name)]


def primary_key_columns(cursor, table_name):
    return [
        column["name"]
        for column in sorted(table_info(cursor, table_name), key=lambda item: item["pk"])
        if column["pk"]
    ]


def unique_columns(cursor, table_name):
    cursor.execute(f'PRAGMA index_list("{table_name}")')
    uniques = set()
    for index in cursor.fetchall():
        if not index[2]:
            continue
        cursor.execute(f'PRAGMA index_info("{index[1]}")')
        indexed_columns = [row[2] for row in cursor.fetchall()]
        if len(indexed_columns) == 1:
            uniques.add(indexed_columns[0])
    return uniques


def sqlite_pk(table_name, row, primary_keys):
    if primary_keys:
        pk_value = "::".join(str(row.get(column, "")) for column in primary_keys)
        return f"{table_name}:{pk_value}"
    return f"{table_name}:sha256:{stable_row_hash(row)}"


def row_by_pk(cursor, table_name, pk_column, pk_value):
    cursor.execute(f'SELECT * FROM "{table_name}" WHERE "{pk_column}" = %s', [pk_value])
    row = cursor.fetchone()
    if not row:
        return None
    columns = [column[0] for column in cursor.description]
    return {column: serialize_sqlite_value(value) for column, value in zip(columns, row)}


def prepare_duplicate_row(row, pk_columns, unique_cols):
    duplicate = dict(row)
    for pk_column in pk_columns:
        duplicate.pop(pk_column, None)

    suffix = timezone.now().strftime("%Y%m%d%H%M%S%f")
    for unique_col in unique_cols:
        value = duplicate.get(unique_col)
        if value:
            duplicate[unique_col] = f"{value}-local-{suffix}"
    return duplicate


def insert_row(cursor, table_name, row):
    if not row:
        cursor.execute(f'INSERT INTO "{table_name}" DEFAULT VALUES')
        return
    columns = list(row.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f'"{column}"' for column in columns)
    cursor.execute(
        f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({placeholders})',
        [row[column] for column in columns],
    )


def update_or_insert_row(cursor, table_name, row, pk_columns):
    if len(pk_columns) != 1:
        insert_row(cursor, table_name, row)
        return

    pk_column = pk_columns[0]
    pk_value = row.get(pk_column)
    if pk_value is None:
        insert_row(cursor, table_name, row)
        return

    existing = row_by_pk(cursor, table_name, pk_column, pk_value)
    if existing:
        update_columns = [column for column in row.keys() if column != pk_column]
        if update_columns:
            set_sql = ", ".join(f'"{column}" = %s' for column in update_columns)
            cursor.execute(
                f'UPDATE "{table_name}" SET {set_sql} WHERE "{pk_column}" = %s',
                [row[column] for column in update_columns] + [pk_value],
            )
        return

    insert_row(cursor, table_name, row)


def sqlite_table_to_mongo(table_name, namespace=DEFAULT_NAMESPACE, database=None):
    if database is None:
        database = get_bot_database()
    collection_name = mongo_safe_collection(namespace, table_name)
    if collection_name not in database.list_collection_names():
        database.create_collection(collection_name)
    collection = database[collection_name]
    collection.create_index("_sqlite_table")
    collection.create_index("_sqlite_pk")

    with connection.cursor() as cursor:
        pk_columns = primary_key_columns(cursor, table_name)
        cursor.execute(f'SELECT * FROM "{table_name}"')
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    current_ids = []
    for row_values in rows:
        row = {
            column: serialize_sqlite_value(value)
            for column, value in zip(columns, row_values)
        }
        pk = sqlite_pk(table_name, row, pk_columns)
        current_ids.append(pk)
        row_hash = stable_row_hash(normalized_row(row))
        document = {
            "_id": pk,
            "_sqlite_table": table_name,
            "_sqlite_pk": pk,
            "_source": "django_sqlite",
            "_row_hash": row_hash,
            **row,
        }
        collection.replace_one({"_id": pk}, document, upsert=True)

    collection.delete_many({
        "_source": "django_sqlite",
        "_sqlite_table": table_name,
        "_id": {"$nin": current_ids},
    })
    return len(rows)


def sqlite_instance_to_mongo(instance, namespace=DEFAULT_NAMESPACE, database=None):
    if database is None:
        database = get_bot_database()
    table_name = instance._meta.db_table
    collection_name = mongo_safe_collection(namespace, table_name)
    if collection_name not in database.list_collection_names():
        database.create_collection(collection_name)
    collection = database[collection_name]
    collection.create_index("_sqlite_table")
    collection.create_index("_sqlite_pk")

    with connection.cursor() as cursor:
        pk_columns = primary_key_columns(cursor, table_name)
        pk_field = instance._meta.pk
        cursor.execute(f'SELECT * FROM "{table_name}" WHERE "{pk_field.column}" = %s', [instance.pk])
        columns = [column[0] for column in cursor.description]
        row_values = cursor.fetchone()

    if not row_values:
        return None

    row = {
        column: serialize_sqlite_value(value)
        for column, value in zip(columns, row_values)
    }
    pk = sqlite_pk(table_name, row, pk_columns)
    row_hash = stable_row_hash(normalized_row(row))
    document = {
        "_id": pk,
        "_sqlite_table": table_name,
        "_sqlite_pk": pk,
        "_source": "django_sqlite",
        "_row_hash": row_hash,
        **row,
    }
    collection.replace_one({"_id": pk}, document, upsert=True)
    return pk


def delete_sqlite_instance_from_mongo(instance, namespace=DEFAULT_NAMESPACE, database=None):
    if database is None:
        database = get_bot_database()
    table_name = instance._meta.db_table
    collection_name = mongo_safe_collection(namespace, table_name)
    collection = database[collection_name]

    with connection.cursor() as cursor:
        pk_columns = primary_key_columns(cursor, table_name)

    if len(pk_columns) == 1:
        
        
        pk_val = getattr(instance, instance._meta.pk.attname)
        pk_id = f"{table_name}:{pk_val}"
        collection.delete_one({"_id": pk_id})
    else:
        
        
        
        pk_vals = [str(getattr(instance, col, "")) for col in pk_columns]
        pk_id = f"{table_name}::{'::'.join(pk_vals)}"
        collection.delete_one({"_id": pk_id})


def sqlite_to_mongo(namespace=DEFAULT_NAMESPACE, selected_tables=None):
    database = get_bot_database()
    selected = set(selected_tables or [])
    copied = {}
    for table_name in table_names():
        if selected and table_name not in selected:
            continue
        copied[table_name] = sqlite_table_to_mongo(table_name, namespace=namespace, database=database)
    return copied


def mongo_collection_to_sqlite(collection_name, namespace=DEFAULT_NAMESPACE):
    table_name = sqlite_table_from_collection(collection_name, namespace)
    if not table_name or table_name not in table_names():
        return {"table": table_name, "inserted": 0, "updated": 0, "conflicts": 0, "skipped": True}

    database = get_bot_database()
    collection = database[collection_name]
    inserted = 0
    updated = 0
    conflicts = 0

    with connection.cursor() as cursor:
        columns = table_columns(cursor, table_name)
        pk_columns = primary_key_columns(cursor, table_name)
        unique_cols = unique_columns(cursor, table_name)
        pk_column = pk_columns[0] if len(pk_columns) == 1 else None

        cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            for document in collection.find({}):
                document = serialize_document(document)
                row = {
                    column: document.get(column)
                    for column in columns
                    if column in document
                }
                if not row:
                    continue

                existing = row_by_pk(cursor, table_name, pk_column, row.get(pk_column)) if pk_column else None
                desired_hash = document.get("_row_hash") or stable_row_hash(normalized_row(row))
                existing_hash = stable_row_hash(normalized_row(existing)) if existing else ""

                if existing and existing_hash == desired_hash:
                    updated += 1
                    continue

                if existing and normalized_row(existing) != normalized_row(row):
                    duplicate = prepare_duplicate_row(existing, pk_columns, unique_cols)
                    insert_row(cursor, table_name, duplicate)
                    conflicts += 1

                update_or_insert_row(cursor, table_name, row, pk_columns)
                if existing:
                    updated += 1
                else:
                    inserted += 1
        finally:
            cursor.execute("PRAGMA foreign_keys=ON")

    return {
        "table": table_name,
        "inserted": inserted,
        "updated": updated,
        "conflicts": conflicts,
        "skipped": False,
    }


def ensure_mongo_backup_table():
    with connection.cursor() as cursor:
        cursor.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "{MONGO_BACKUP_TABLE}" (
                "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                "collection_name" TEXT NOT NULL,
                "document_id" TEXT NOT NULL,
                "document_json" TEXT NOT NULL,
                "synced_at" TEXT NOT NULL,
                UNIQUE("collection_name", "document_id")
            )
            '''
        )


def backup_all_mongo_documents_to_sqlite():
    database = get_bot_database()
    ensure_mongo_backup_table()
    synced_at = timezone.now().isoformat()
    total = 0

    with connection.cursor() as cursor:
        for collection_name in database.list_collection_names():
            collection = database[collection_name]
            for document in collection.find({}):
                serialized = serialize_document(document)
                document_id = str(serialized.get("_id", stable_row_hash(serialized)))
                payload = json.dumps(serialized, ensure_ascii=False, sort_keys=True, default=str)
                cursor.execute(
                    f'''
                    INSERT INTO "{MONGO_BACKUP_TABLE}"
                    ("collection_name", "document_id", "document_json", "synced_at")
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT("collection_name", "document_id")
                    DO UPDATE SET
                        "document_json" = excluded."document_json",
                        "synced_at" = excluded."synced_at"
                    ''',
                    [collection_name, document_id, payload, synced_at],
                )
                total += 1
    return total


def mongo_to_sqlite(namespace=DEFAULT_NAMESPACE, backup=True):
    database = get_bot_database()
    results = {}
    for collection_name in sorted(database.list_collection_names()):
        if not collection_name.startswith(f"{namespace}_"):
            continue
        results[collection_name] = mongo_collection_to_sqlite(collection_name, namespace=namespace)
    backup_total = backup_all_mongo_documents_to_sqlite() if backup else 0
    return results, backup_total


def bidirectional_sync(namespace=DEFAULT_NAMESPACE, backup=True):
    with SYNC_LOCK:
        pull_results, backup_total = mongo_to_sqlite(namespace=namespace, backup=backup)
        push_results = sqlite_to_mongo(namespace=namespace)
    return {
        "pull": pull_results,
        "backup_total": backup_total,
        "push": push_results,
    }
