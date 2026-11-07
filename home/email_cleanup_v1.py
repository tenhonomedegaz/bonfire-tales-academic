"""Frozen migration helper. Delete only empty duplicates, never move player PKs."""
from django.db.models import Count
from django.db.models.functions import Lower, Trim


def cleanup_and_index(apps, schema_editor):
    db = schema_editor.connection.alias
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('home', 'UserProfile')
    Receipt = apps.get_model('home', 'UserAccountMergeReceipt')
    query = User.objects.using(db).annotate(address=Lower(Trim('email')))
    groups = list(query.exclude(address='').values('address').annotate(n=Count('pk')).filter(n__gt=1))
    if groups and schema_editor.connection.vendor == 'postgresql':
        from .master_legacy_api import _backup
        _backup()
    tables = set(schema_editor.connection.introspection.table_names())
    relations = []
    for model in apps.get_models(include_auto_created=True):
        if model == Profile or model._meta.db_table not in tables:
            continue
        for field in model._meta.local_fields:
            target = getattr(field.remote_field, 'model', None) if field.is_relation else None
            if getattr(getattr(target, '_meta', None), 'label_lower', None) == User._meta.label_lower:
                relations.append((model, field.attname))
    plans = []
    for group in groups:
        users = list(query.select_for_update().filter(address=group['address']).order_by('pk'))
        profiles = {p.user_id: p for p in Profile.objects.using(db).select_for_update().filter(user_id__in=[u.pk for u in users])}
        def protected(user):
            profile = profiles.get(user.pk)
            if user.is_staff or user.is_superuser:
                return True
            if profile:
                fields = ('discord_user_id', 'moedas_mestragem', 'mm_ganhas_total', 'moedas_evento',
                          'mestre_ouro_ativo', 'avatar_url', 'banner_url', 'background_url', 'bio',
                          'theme_custom', 'titulo_equipado', 'badges_destaque', 'badges_derivadas_ocultas')
                if any(getattr(profile, name, None) for name in fields):
                    return True
                if profile.profile_theme not in ('', 'bonfire') or profile.avatar_frame not in (None, '', 'none') or profile.profile_effect not in (None, '', 'none'):
                    return True
            return any(model._base_manager.using(db).filter(**{field: user.pk}).exists() for model, field in relations)
        rich = [user for user in users if protected(user)]
        if len(rich) > 1:
            raise RuntimeError('Contas duplicadas com dados em mais de um login; concilie antes da exclusao: ' + ', '.join(str(u.pk) for u in rich))
        keeper = rich[0] if rich else max(users, key=lambda u: (
            bool(getattr(profiles.get(u.pk), 'email_verified', False)),
            u.last_login.timestamp() if u.last_login else 0, u.pk))
        plans.append((keeper, [u for u in users if u.pk != keeper.pk], profiles))
    # Preflight every group before the first delete. Transaction/FK locks prevent
    # a new character or purchase from being attached during the cleanup.
    for keeper, discarded, profiles in plans:
        verified = any(getattr(p, 'email_verified', False) for p in profiles.values())
        target = profiles.get(keeper.pk)
        if target and verified and not target.email_verified:
            Profile.objects.using(db).filter(pk=target.pk).update(email_verified=True)
        for user in discarded:
            Receipt.objects.using(db).create(keeper_id=keeper.pk, removed_user_id=user.pk,
                removed_username=user.username, email_verification_preserved=verified)
            user.delete(using=db)
    for user in User.objects.using(db).only('pk', 'email').iterator():
        normalized = (user.email or '').strip().lower()
        if normalized != user.email:
            User.objects.using(db).filter(pk=user.pk).update(email=normalized)
    table = schema_editor.quote_name(User._meta.db_table)
    if schema_editor.connection.vendor == 'postgresql':
        # Drain deferred FK triggers from cleanup before DDL, without committing
        # the account deletions separately from the uniqueness guarantee.
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')
    schema_editor.execute(f'CREATE UNIQUE INDEX auth_user_email_normalized_unique ON {table} (LOWER(TRIM(email))) WHERE TRIM(email) <> \'\'')
