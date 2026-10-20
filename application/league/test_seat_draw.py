import copy
from unittest.mock import patch
from django.test import TestCase
from .test_coach_lineups import CoachLineupTests
from .domain import apply,Invalid
from .seat_draw import draw
class SeatDrawTests(TestCase):
    setUp=CoachLineupTests.setUp
    def test_team_draw_is_not_automatic_or_single_game(self):
        d=self.e.document;m=d['matches'][0]
        for seat,p in zip(m['seats'],d['players']):seat['playerId']=p['id']
        before=copy.deepcopy(m)
        draw(d,m,automatic=True);self.assertEqual(m,before)
        with self.assertRaises(Invalid):draw(d,m)
        with self.assertRaises(Invalid):apply(d,'team','random-seats',{'id':m['id']})
    def test_coach_cannot_use_admin_command_and_start_locked(self):
        self.client.force_login(self.coach)
        r=self.client.post(f'/api/events/{self.e.pk}/',{'revision':1,'action':'random-seats','id':self.mid},content_type='application/json');self.assertEqual(r.status_code,404)
        with patch('django.utils.timezone.now',return_value=self.now.replace(hour=20)):
            with self.assertRaises(Invalid):apply(self.e.document,'team','random-seats',{'id':self.mid})
