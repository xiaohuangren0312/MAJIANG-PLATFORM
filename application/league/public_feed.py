"""Public-only projection cache, invalidated by source content and timed disclosure."""
import hashlib
import json
import threading
import time
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import get_conditional_response
from .models import Event, HistoricalArchive
from .projection import public_event, rank_metrics

_lock = threading.Lock()
_cached = None

def response(request):
    global _cached
    # Read the public set every time: unpublishing and edits invalidate immediately,
    # including archive changes which do not have an Event revision.
    events = list(Event.objects.filter(public=True).order_by('created_at', 'pk'))
    archives = list(HistoricalArchive.objects.filter(public=True).order_by('pk'))
    from .coach_lineups import visible
    now = timezone.now()
    disclosure = [[visible(e.document, m, s, now) for m in e.document.get('matches', [])
                   if m.get('state') != 'cancelled' for s in m.get('seats', [])] for e in events]
    source = [(str(e.pk), e.name, e.kind, e.document) for e in events]
    live_tick = int(time.time() // 20) if any(e.document.get('tableLive') for e in events) else None
    key = hashlib.sha256(json.dumps([source, [(a.pk, a.payload) for a in archives], disclosure, live_tick],
                                   sort_keys=True, ensure_ascii=False).encode()).digest()
    # One build per worker at a time; retain only the latest public snapshot.
    with _lock:
        if _cached is None or _cached[0] != key:
            tournaments = [public_event(e) for e in events] + [rank_metrics(a.payload) for a in archives]
            content = json.dumps(tournaments, ensure_ascii=False, separators=(',', ':'))
            etag = '"' + hashlib.sha256(content.encode()).hexdigest() + '"'
            payload = ('{"demo":false,"updatedAt":' + json.dumps(now.isoformat()) + ',"tournaments":' + content + '}').encode()
            _cached = (key, etag, payload)
        _, etag, payload = _cached
    result = HttpResponse(payload, content_type='application/json')
    result['ETag'] = etag
    result['Cache-Control'] = 'private, no-cache'
    return get_conditional_response(request, etag=etag, response=result)
