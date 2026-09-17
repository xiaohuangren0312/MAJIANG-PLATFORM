from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from league.models import Event
from league.domain import Invalid
from .history import validate_links,candidate_history,history_options

class ExplicitHistoryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='history-admin',is_superuser=True)
        self.payload=dict(name='历史',players=[dict(id='same-name-a',name='同名'),dict(id='same-name-b',name='同名')],stages=[dict(id='regular',name='常规赛'),dict(id='final',name='决赛')],statistics={'regular':{'raw':{'player':[dict(id='same-name-a',games=2,raw=125,avgRank=2.5),dict(id='same-name-b',games=1,raw=-10,avgRank=None)]}},'final':{'raw':{'player':[dict(id='same-name-a',games=None,total=None,avgRank=None)]}}})
        self.event=Event.objects.create(name='公开历史',kind='team',public=True,document={'historySnapshot':self.payload})
    def mapping(self,pid='same-name-a'):
        return [dict(playerId='current',historyLinks=[dict(eventId=str(self.event.pk),playerId=pid)])]
    def test_explicit_identity_not_name_and_units(self):
        links=validate_links(self.mapping(),self.user)
        with patch('team_draft.history.public_event',return_value=self.payload):
            rows=candidate_history(dict(historyLinks=links))['current'][0]['stages']
        self.assertEqual(rows[0],dict(name='常规赛',games=2,total=12.5,average=6.25,avgRank=2.5))
        self.assertIsNone(rows[1]['total']);self.assertIsNone(rows[1]['games']);self.assertIsNone(rows[1]['average'])
    def test_no_mapping_does_not_guess_name(self):
        self.assertEqual(candidate_history({}),{})
    def test_reject_unknown_identity_and_duplicate_event(self):
        with self.assertRaises(Invalid):validate_links(self.mapping('missing'),self.user)
        payload=self.mapping();payload[0]['historyLinks']*=2
        with self.assertRaises(Invalid):validate_links(payload,self.user)
    def test_private_history_never_exposed(self):
        links=validate_links(self.mapping(),self.user)
        self.event.public=False;self.event.save()
        self.assertEqual(history_options(),[])
        self.assertEqual(candidate_history(dict(historyLinks=links)),{'current':[]})
        with self.assertRaises(Invalid):validate_links(self.mapping(),self.user)


class PublicArchiveHistoryTests(TestCase):
    def setUp(self):
        import json,copy
        from pathlib import Path
        from league.models import HistoricalArchive
        self.payload=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        self.archive=HistoricalArchive.objects.create(key='real-shape',public=True,payload=self.payload)
        self.person=self.payload['players'][0]
        self.source='archive:real-shape'
        self.links={'candidate':[dict(eventId=self.source,playerId=self.person['id'])]}
    def test_archive_options_and_correct_public_metrics(self):
        from league.projection import rank_metrics
        options=history_options()
        self.assertEqual(options[0]['id'],self.source)
        self.assertTrue(any(p['id']==self.person['id'] for p in options[0]['players']))
        validated=validate_links([dict(playerId='candidate',historyLinks=self.links['candidate'])],None)
        rows=candidate_history({'historyLinks':validated})['candidate'][0]
        expected=rank_metrics(self.payload)
        for stage in expected['stages']:
            stat=next((s for s in expected['statistics'][stage['id']]['raw']['player'] if s['id']==self.person['id']),None)
            if not stat:continue
            actual=next(r for r in rows['stages'] if r['name']==stage['name'])
            self.assertEqual(actual['avgRank'],stat.get('avgRank'))
            self.assertEqual(actual['games'],stat.get('games'))
            self.assertEqual(actual['total'],stat.get('raw',stat.get('total'))/10)
        self.archive.refresh_from_db()
        self.assertEqual(self.archive.payload,self.payload)
    def test_archive_private_or_missing_identity_never_guessed(self):
        wrong=[dict(playerId='candidate',historyLinks=[dict(eventId=self.source,playerId='nonexistent')])]
        with self.assertRaises(Invalid):validate_links(wrong,None)
        self.archive.public=False;self.archive.save()
        self.assertEqual(history_options(),[])
        self.assertEqual(candidate_history({'historyLinks':self.links}),{'candidate':[]})
    def test_public_import_replaces_archive_in_options(self):
        from league.models import HistoryImport
        event=Event.objects.create(name='已公开导入',kind='team',public=True,document={'historySnapshot':self.payload})
        HistoryImport.objects.create(archive=self.archive,event=event,fingerprint='test')
        ids=[r['id'] for r in history_options()]
        self.assertIn(str(event.pk),ids);self.assertNotIn(self.source,ids)
        event.public=False;event.save()
        self.assertIn(self.source,[r['id'] for r in history_options()])
