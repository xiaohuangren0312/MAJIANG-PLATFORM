import copy
from unittest.mock import patch
from django.test import TestCase
from .test_coach_lineups import CoachLineupTests
from .domain import apply,Invalid
from .seat_draw import draw
class SeatDrawTests(TestCase):
    setUp=CoachLineupTests.setUp
    def test_manual_preserves_pairs_and_publication_and_blocks_scored(self):
        d=self.e.document;m=d['matches'][0];m['coachLineups']={self.tid:{'mode':'default'}}
        before=copy.deepcopy(m)
        with patch('league.seat_draw.secrets.SystemRandom') as rng:
            rng.return_value.shuffle.side_effect=lambda rows:rows.reverse()
            new=apply(d,'team','random-seats',{'id':m['id']})
        result=new['matches'][0]
        self.assertEqual(result['seats'],list(reversed(before['seats'])))
        self.assertEqual(result['coachLineups'],before['coachLineups'])
        self.assertEqual(result['seatDraw']['count'],1)
        result['seats'][0]['score']=25000
        with self.assertRaises(Invalid):apply(new,'team','random-seats',{'id':m['id']})
    def test_coach_completion_only_once_and_manual_override(self):
        d=self.e.document;m=d['matches'][0]
        for seat,p in zip(m['seats'][:3],d['players'][:3]):seat['playerId']=p['id']
        draw(d,m,automatic=True);self.assertNotIn('seatDraw',m)
        # An event manager uses the same coach endpoint for the final team.
        self.e.document=d;self.e.save();self.client.force_login(self.admin)
        r=self.client.post(f'/api/coach/lineups/{self.e.pk}/',{'revision':1,'rows':[{'matchId':m['id'],'teamId':d['teams'][3]['id'],'playerId':d['players'][3]['id']}]},content_type='application/json')
        self.assertEqual(r.status_code,200,r.content);self.e.refresh_from_db();m=self.e.document['matches'][0]
        self.assertEqual(m['seatDraw']['mode'],'automatic');old=copy.deepcopy(m['seats'])
        draw(self.e.document,m,automatic=True);self.assertEqual(m['seats'],old);self.assertEqual(m['seatDraw']['count'],1)
        draw(self.e.document,m);self.assertEqual(m['seatDraw']['count'],2)
    def test_coach_cannot_use_admin_command_and_start_locked(self):
        self.client.force_login(self.coach)
        r=self.client.post(f'/api/events/{self.e.pk}/',{'revision':1,'action':'random-seats','id':self.mid},content_type='application/json');self.assertEqual(r.status_code,404)
        with patch('django.utils.timezone.now',return_value=self.now.replace(hour=20)):
            with self.assertRaises(Invalid):apply(self.e.document,'team','random-seats',{'id':self.mid})
