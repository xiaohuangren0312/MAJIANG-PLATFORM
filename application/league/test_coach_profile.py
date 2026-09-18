import io,tempfile,copy
from pathlib import Path
from PIL import Image
from django.test import TestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from .test_coach_lineups import CoachLineupTests
from .projection import public_event
class CoachProfileTests(TestCase):
    setUp=CoachLineupTests.setUp
    def post(self,user,kind,id,**extra):
        self.client.force_login(user);self.e.refresh_from_db()
        return self.client.post(f'/api/coach/profile/{self.e.pk}/',{'revision':self.e.revision,'kind':kind,'entityId':id,'bio':'新的简介',**extra},content_type='application/json')
    def test_scope_fields_archive_and_projection(self):
        self.assertEqual(self.post(self.coach,'team',self.tid,color='#123456').status_code,200)
        self.e.refresh_from_db();self.assertEqual(public_event(self.e)['teams'][0]['bio'],'新的简介')
        self.assertEqual(self.post(self.coach,'player',self.pid).status_code,200)
        self.assertEqual(self.post(self.coach,'team',self.other_tid).status_code,403)
        self.assertEqual(self.post(self.coach,'player',self.other_pid).status_code,403)
        self.assertEqual(self.post(self.viewer,'team',self.tid).status_code,403)
        self.assertEqual(self.post(self.coach,'player',self.pid,teamId=self.other_tid).status_code,400)
        self.assertEqual(self.post(self.coach,'team',self.tid,color=self.e.document['teams'][1]['color']).status_code,400)
        self.assertEqual(self.post(self.admin,'player',self.other_pid).status_code,200)
        self.e.refresh_from_db();self.e.document['archiveRevision']={'test':True};self.e.save()
        self.assertEqual(self.post(self.coach,'team',self.tid).status_code,403)
    def test_image_permission_private_read_and_score_preservation(self):
        buf=io.BytesIO();Image.new('RGB',(20,20),'red').save(buf,format='PNG')
        self.e.public=False;self.e.save();before=copy.deepcopy(self.e.document['matches'])
        with tempfile.TemporaryDirectory(dir='/data/majiang/dev/tmp') as tmp,override_settings(ENV_ROOT=Path(tmp)):
            self.client.force_login(self.coach)
            def upload(id):
                self.e.refresh_from_db()
                return self.client.post(f'/api/events/{self.e.pk}/image/',{'revision':self.e.revision,'kind':'player','entityId':id,'image':SimpleUploadedFile('x.png',buf.getvalue(),'image/png')})
            self.assertEqual(upload(self.other_pid).status_code,403)
            r=upload(self.pid);self.assertEqual(r.status_code,200,r.content);url=r.json()['imageUrl']
            self.assertEqual(self.client.get(url).status_code,200)
            self.client.force_login(self.other);self.assertEqual(self.client.get(url).status_code,404)
            self.e.refresh_from_db();self.assertEqual(self.e.document['matches'],before)
    def test_scoped_listing_and_disabled_coach(self):
        self.client.force_login(self.coach)
        r=self.client.get(f'/api/coach/profile/{self.e.pk}/');self.assertEqual(r.status_code,200)
        self.assertEqual([x['id'] for x in r.json()['teams']],[self.tid])
        self.assertEqual([x['id'] for x in r.json()['players']],[self.pid])
        self.e.document['coachAccounts'][str(self.coach.pk)]['active']=False;self.e.save()
        self.assertEqual(self.post(self.coach,'team',self.tid).status_code,403)
