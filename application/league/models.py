import uuid
from django.conf import settings
from django.db import models

class Event(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name=models.CharField(max_length=120)
    kind=models.CharField(max_length=10,choices=[('team','团体赛'),('personal','个人赛')])
    public=models.BooleanField(default=False)
    is_test=models.BooleanField(default=False)
    revision=models.PositiveIntegerField(default=1)
    editors=models.ManyToManyField(settings.AUTH_USER_MODEL)
    # Event is the atomic consistency boundary. Each change checks revision;
    # IDs are resolved only within this document, never across tournaments.
    document=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

class Audit(models.Model):
    event=models.ForeignKey(Event,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    revision=models.PositiveIntegerField()
    action=models.CharField(max_length=40)
    reason=models.TextField(blank=True)
    before=models.JSONField()
    after=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['event','revision'],name='event_revision_unique')]

class HistoricalArchive(models.Model):
    key=models.CharField(primary_key=True,max_length=30)
    public=models.BooleanField(default=True)
    payload=models.JSONField()
    imported_at=models.DateTimeField(auto_now_add=True)

class LoginAttempt(models.Model):
    key=models.CharField(primary_key=True,max_length=64)
    failures=models.PositiveIntegerField(default=0)
    updated_at=models.DateTimeField(auto_now=True)


class HistoryReview(models.Model):
    archive=models.OneToOneField(HistoricalArchive,on_delete=models.PROTECT)
    fingerprint=models.CharField(max_length=64)
    revision=models.PositiveIntegerField(default=0)
    decisions=models.JSONField(default=dict)

class HistoryReviewAudit(models.Model):
    review=models.ForeignKey(HistoryReview,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    revision=models.PositiveIntegerField()
    before=models.JSONField()
    after=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['review','revision'],name='history_review_revision_unique')]


class HistoryImport(models.Model):
    archive=models.OneToOneField(HistoricalArchive,on_delete=models.PROTECT)
    event=models.OneToOneField(Event,on_delete=models.PROTECT)
    fingerprint=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)


class EventCleanup(models.Model):
    event_id=models.UUIDField(unique=True)
    event_name=models.CharField(max_length=120)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    reason=models.TextField()
    backup_path=models.TextField()
    backup_sha256=models.CharField(max_length=64)
    counts=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)


class RuleTemplate(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name=models.CharField(max_length=120,unique=True)
    rule=models.JSONField()
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
