from django.test import SimpleTestCase
from django.core.cache import cache
from unittest.mock import patch,MagicMock
from .matchday_live import update,room_status

class MatchdayLiveTests(SimpleTestCase):
    def setUp(self):cache.clear()
    def test_normalize_and_clear(self):
        d={'matches':[{'date':'2026-09-20'}]}
        new=update(d,{'date':'2026-09-20','url':'https://live.bilibili.com/1750978495?broadcast_type=0'})
        self.assertNotIn('matchdayLive',d)
        self.assertEqual(new['matchdayLive']['2026-09-20'],'https://live.bilibili.com/1750978495')
        self.assertEqual(update(new,{'date':'2026-09-20','url':''})['matchdayLive'],{})
    def test_invalid_urls_and_dates(self):
        d={'matches':[{'date':'2026-09-20'}]}
        for url in ['http://127.0.0.1/1','https://live.bilibili.com.evil.test/1','https://live.bilibili.com@evil.test/1']:
            with self.assertRaises(Exception):update(d,{'date':'2026-09-20','url':url})
        with self.assertRaises(Exception):update(d,{'date':'2026-09-21','url':'https://live.bilibili.com/1'})
    @patch('league.matchday_live.urlopen')
    def test_states_and_cache(self,fetch):
        for value,expected in [(0,'offline'),(1,'live'),(2,'offline'),(9,'unknown')]:
            cache.clear();fetch.return_value.__enter__.return_value.read.return_value=('{"code":0,"data":{"live_status":%s}}'%value).encode()
            self.assertEqual(room_status('https://live.bilibili.com/1'),expected)
            count=fetch.call_count;room_status('https://live.bilibili.com/1');self.assertEqual(fetch.call_count,count)
    @patch('league.matchday_live.urlopen',side_effect=TimeoutError)
    def test_failure_is_not_offline(self,fetch):
        self.assertEqual(room_status('https://live.bilibili.com/1'),'unknown')
