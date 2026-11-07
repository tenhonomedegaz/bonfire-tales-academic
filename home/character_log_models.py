"""External sheet history is evidence, not a second character or reward ledger."""
from django.conf import settings
from django.db import models


class CharacterLogSource(models.Model):
    spreadsheet_id = models.CharField(max_length=160, unique=True)
    bot_log_id = models.CharField(max_length=30)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='imported_character_logs')
    discord_user_id = models.CharField(max_length=32)
    character = models.ForeignKey('home.TbPersonagem', on_delete=models.PROTECT,
                                  null=True, blank=True, related_name='external_logs')
    character_name = models.CharField(max_length=300)
    metadata = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class CharacterLogImportBatch(models.Model):
    source = models.ForeignKey(CharacterLogSource, on_delete=models.PROTECT, related_name='imports')
    fingerprint = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['source', 'fingerprint'], name='unique_character_log_import')]


class CharacterLogMission(models.Model):
    source = models.ForeignKey(CharacterLogSource, on_delete=models.PROTECT, related_name='missions')
    bot_quest_id = models.CharField(max_length=30)
    last_seen_batch = models.ForeignKey(CharacterLogImportBatch, on_delete=models.PROTECT)
    evidence = models.JSONField(default=dict)
    needs_review = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['source', 'bot_quest_id'], name='unique_log_mission_link')]


class CharacterHistoryMission(models.Model):
    """Attested historical mission absent from the bot; not a reward delivery."""
    title = models.CharField(max_length=500)
    identity_key = models.CharField(max_length=64, unique=True)
    date = models.DateField()
    master_name = models.CharField(max_length=200)
    guild_id = models.CharField(max_length=32)
    adventures = models.PositiveIntegerField(null=True, blank=True)
    evidence = models.TextField(max_length=3000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    master_record = models.OneToOneField('home.TbRegistroMestreLegado', on_delete=models.PROTECT,
                                         null=True, blank=True)

    class Meta:
        default_permissions = ()


class CharacterLogEntry(models.Model):
    source = models.ForeignKey(CharacterLogSource, on_delete=models.PROTECT, related_name='entries')
    source_key = models.CharField(max_length=100)
    last_seen_batch = models.ForeignKey(CharacterLogImportBatch, on_delete=models.PROTECT)
    category = models.CharField(max_length=24, default='mission')
    state = models.CharField(max_length=16, default='pending', db_index=True)
    observed = models.JSONField(default=dict)
    observed_digest = models.CharField(max_length=64)
    reference = models.CharField(max_length=160, blank=True, default='')
    adventures_confirmed = models.PositiveIntegerField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='character_history_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        permissions = [('review_character_history', 'Revisar historico de personagens e evidencias')]
        constraints = [models.UniqueConstraint(fields=['source', 'source_key'], name='unique_character_log_entry')]


class CharacterLogReview(models.Model):
    entry = models.ForeignKey(CharacterLogEntry, on_delete=models.PROTECT, related_name='reviews')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    before = models.JSONField()
    after = models.JSONField()
    note = models.TextField(max_length=2000)
    evidence = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
