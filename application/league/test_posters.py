import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from .test_coach_lineups import CoachLineupTests
from .models import Event, Audit

class PosterTests(TestCase):
    setUp=CoachLineupTests.setUp
    def url(self):return f"/api/posters/{self.e.pk}/"
    def fill(self):
        d=self.e.document
        for m in d["matches"]:
            for i,s in enumerate(m["seats"]):s["playerId"]=d["players"][i]["id"]
        self.e.save()
    def test_roles_and_event_scope(self):
        self.assertEqual(self.client.get(self.url()).status_code,401)
        for user in (self.coach,self.viewer):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/manage/posters/").status_code,403)
            self.assertEqual(self.client.get(self.url()).status_code,403)
            self.assertEqual(self.client.get("/api/posters/").json()["events"],[])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/manage/posters/").status_code,200)
        self.assertEqual(self.client.get(self.url()).status_code,200)
        foreign=Event.objects.create(name="其他赛事",kind="team",document=copy.deepcopy(self.e.document))
        self.assertEqual(self.client.get(f"/api/posters/{foreign.pk}/").status_code,403)
        self.assertEqual([r["id"] for r in self.client.get("/api/posters/").json()["events"]],[str(self.e.pk)])
        root=get_user_model().objects.create_superuser("poster-root","root@example.test","test-password")
        self.client.force_login(root)
        self.assertEqual(self.client.get(f"/api/posters/{foreign.pk}/").status_code,200)
    def test_private_roster_exact_assets_and_no_writes(self):
        self.fill()
        self.e.document["players"][0]["imageUrl"]="/media/roster/test.png"
        self.e.save()
        old=copy.deepcopy(self.e.document);revision=self.e.revision
        self.client.force_login(self.admin)
        response=self.client.get(self.url())
        self.assertIn("no-store",response["Cache-Control"])
        rows=response.json()["matches"]
        self.assertEqual([r["game"] for r in rows],[1,2])
        self.assertTrue(all(r["private"] and r["complete"] for r in rows))
        self.assertEqual(rows[0]["players"][0]["name"],self.e.document["players"][0]["name"])
        self.assertEqual(rows[0]["players"][0]["imageUrl"],"/media/roster/test.png")
        self.assertEqual(rows[0]["players"][1]["imageUrl"],"/assets/player-default.png")
        self.assertEqual(self.client.post(self.url(),{}).status_code,405)
        self.e.refresh_from_db()
        self.assertEqual(self.e.document,old);self.assertEqual(self.e.revision,revision)
        self.assertEqual(Audit.objects.count(),0)
    def test_incomplete_cancelled_and_public(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.client.get(self.url()).json()["matches"][0]["complete"])
        self.fill()
        self.e.document["matches"][0]["lineupPublished"]=True
        self.e.document["matches"][1]["state"]="cancelled";self.e.save()
        rows=self.client.get(self.url()).json()["matches"]
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]["private"])
    def test_archived_revision_uses_published_snapshot(self):
        d=self.e.document
        snapshot={"teams":d["teams"],"players":copy.deepcopy(d["players"]),"stages":d["stages"],"schedule":[dict(d["matches"][0],state="completed",players=[dict(s,playerId=d["players"][i]["id"]) for i,s in enumerate(d["matches"][0]["seats"])])]}
        d["archiveRevision"]={"publicPayload":snapshot}
        d["players"][0]["name"]="未发布修订"
        self.e.save();self.client.force_login(self.admin)
        rows=self.client.get(self.url()).json()["matches"]
        self.assertEqual(rows[0]["players"][0]["name"],"选手0")
        self.assertFalse(rows[0]["private"])

    def test_confirmed_winds_and_commentators(self):
        self.fill();d=self.e.document;m=d['matches'][0]
        m['seatDraw']={'confirmed':True}
        d['matchResources']={m['id']:{'commentators':['解说甲','解说乙']}}
        self.e.save();self.client.force_login(self.admin)
        row=self.client.get(self.url()).json()['matches'][0]
        self.assertEqual([p['wind'] for p in row['players']],list('东南西北'))
        self.assertEqual(row['commentators'],['解说甲','解说乙'])
        self.assertTrue(row['seatOrderKnown'])
        self.assertTrue(row['private'])

    def test_unconfirmed_order_is_not_a_seat_assignment(self):
        self.fill();self.client.force_login(self.admin)
        row=self.client.get(self.url()).json()['matches'][0]
        self.assertFalse(row['seatOrderKnown'])
        self.assertEqual([p['wind'] for p in row['players']],[None]*4)
        self.assertEqual(row['commentators'],[])

    def test_snapshot_seats_and_commentators_stay_published(self):
        self.fill();d=self.e.document
        m=dict(d['matches'][0],state='completed',seatOrderKnown=True,
               players=[dict(s,wind=w) for s,w in zip(d['matches'][0]['seats'],'北西南东')],
               resources={'commentators':['已发布解说']})
        d['archiveRevision']={'publicPayload':dict(teams=d['teams'],players=d['players'],stages=d['stages'],schedule=[m])}
        d['matchResources']={m['id']:{'commentators':['未发布解说']}}
        self.e.save();self.client.force_login(self.admin)
        row=self.client.get(self.url()).json()['matches'][0]
        self.assertEqual([p['wind'] for p in row['players']],list('东南西北'))
        self.assertEqual(row['players'][0]['playerId'],d['matches'][0]['seats'][3]['playerId'])
        self.assertEqual(row['commentators'],['已发布解说'])
