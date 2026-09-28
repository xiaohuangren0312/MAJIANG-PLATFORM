import datetime
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from . import public_feed
from .views import public_data

class PublicFeedTests(SimpleTestCase):
    def setUp(self):
        public_feed._cached = None
        self.event = SimpleNamespace(pk='event', name='S4', kind='team', document={'matches': []})
        self.events = patch.object(public_feed.Event.objects, 'filter').start()
        self.events.return_value.order_by.return_value = [self.event]
        self.archives = patch.object(public_feed.HistoricalArchive.objects, 'filter').start()
        self.archives.return_value.order_by.return_value = []
        self.project = patch.object(public_feed, 'public_event', side_effect=lambda e: {'name':e.name,'body':'x'*4000}).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(lambda: setattr(public_feed, '_cached', None))
    def get(self, **headers):
        return public_data(RequestFactory().get('/data.json', **headers))
    def test_cached_and_conditional(self):
        first=self.get(); second=self.get(HTTP_IF_NONE_MATCH=first['ETag'])
        self.assertEqual(second.status_code,304)
        self.assertEqual(second.content,b'')
        self.assertEqual(self.project.call_count,1)
    def test_changes_and_unpublishing_invalidate(self):
        first=self.get();self.event.name='new'
        changed=self.get(HTTP_IF_NONE_MATCH=first['ETag'])
        self.assertEqual(changed.status_code,200)
        self.events.return_value.order_by.return_value=[]
        self.assertNotIn(b'new',self.get().content)
    def test_gzip_and_weak_etag(self):
        import gzip
        first=self.get(HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(first['Content-Encoding'],'gzip')
        self.assertIn(b'S4',gzip.decompress(first.content))
        self.assertEqual(self.get(HTTP_ACCEPT_ENCODING='gzip',HTTP_IF_NONE_MATCH=first['ETag']).status_code,304)
    def test_clock_disclosure_invalidates_without_revision(self):
        self.event.document['matches']=[{'state':'draft','seats':[{}]}]
        with patch('league.coach_lineups.visible',return_value=False): self.get()
        with patch('league.coach_lineups.visible',return_value=True): self.get()
        self.assertEqual(self.project.call_count,2)
    def test_archive_payload_changes_invalidate(self):
        archive=SimpleNamespace(pk='s1',payload={'name':'old'})
        self.archives.return_value.order_by.return_value=[archive]
        with patch.object(public_feed,'rank_metrics',side_effect=lambda p:p):
            first=self.get();archive.payload={'name':'changed'}
            self.assertEqual(self.get(HTTP_IF_NONE_MATCH=first['ETag']).status_code,200)
