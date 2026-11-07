"""Capture a real pre-D snapshot before exercising D operations in tests."""

import hashlib
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def capture_pre_d_snapshot(path):
    executor = MigrationExecutor(connection)
    original_heads = executor.loader.graph.leaf_nodes('home')
    try:
        executor.migrate([('home', '0154_redesign_master_portfolio')])
        call_command('preview_redesign_d', output=str(path),
                     expected_home_head='0154_redesign_master_portfolio',
                     stdout=StringIO())
    finally:
        MigrationExecutor(connection).migrate(original_heads)
    return hashlib.sha256(path.read_bytes()).hexdigest()
