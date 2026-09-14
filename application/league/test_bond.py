import copy
from django.test import TestCase
from .tests import fixture,publish
from .domain import apply,Invalid
from .projection import statistics,settlement_preview,settle
class BondTests(TestCase):
 def test_stage_registration_and_historical_contributions(self):
  d=fixture();stage=d['stages'][0]['id'];tid=d['teams'][0]['id'];mid=d['matches'][0]['id']
  d=apply(d,'team','bond-player',dict(name='羁绊甲',stageId=stage,teamId=tid));pid=d['players'][-1]['id']
  seats=copy.deepcopy(d['matches'][0]['seats']);seats[0]['playerId']=pid
  d=apply(d,'team','lineup',dict(id=mid,seats=seats));d=apply(d,'team','score',dict(id=mid,scores=[40000,30000,20000,10000]));d=apply(d,'team','publish',dict(id=mid))
  old=copy.deepcopy(d['matches'][0]);self.assertTrue(old['seats'][0]['bond'])
  p=settlement_preview(d,'team',dict(source=stage,target=d['stages'][1]['id'],ids=[t['id'] for t in d['teams']]))
  d=settle(d,p,{});target=d['stages'][1]['id']
  with self.assertRaises(Invalid):apply(d,'team','match',dict(stageId=target,date='2026-09-15',time='19:30',number=1,seats=seats))
  d=apply(d,'team','bond-player',dict(id=pid,stageId=target,teamId=tid))
  d=apply(d,'team','match',dict(stageId=target,date='2026-09-15',time='19:30',number=1,seats=seats))
  self.assertEqual(d['matches'][0],old)
  row=next(x for x in statistics(d,stage,False,'player') if x['id']==pid)
  self.assertTrue(row['bond']);self.assertEqual(row['total'],600)
  self.assertIn(pid,[x['id'] for x in statistics(d,target,False,'player')])
  with self.assertRaises(Invalid):apply(d,'team','bond-player',dict(id=pid,stageId=target,teamId=tid))
  self.assertIsNone(next(x for x in d['players'] if x['id']==pid)['teamId'])
