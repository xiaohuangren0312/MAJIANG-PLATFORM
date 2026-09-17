import uuid
from django.conf import settings
from django.db import models

class DraftActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    event = models.ForeignKey('league.Event', null=True, blank=True, on_delete=models.PROTECT, related_name='draft_activities')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, default='setup', choices=[('setup','准备'),('active','进行中'),('complete','已完成')])
    revision = models.PositiveIntegerField(default=1)
    document = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event'], condition=models.Q(status__in=['setup','active'], event__isnull=False), name='draft_one_open_activity_per_event')]

class DraftAudit(models.Model):
    activity = models.ForeignKey(DraftActivity, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    action = models.CharField(max_length=40)
    before = models.JSONField()
    after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['activity','revision'], name='draft_activity_revision_unique')]
