from django.contrib.auth import get_user_model
from django.test import TestCase
from .domain import apply, initial
from .models import Audit, Event


class BatchScheduleTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('batch-manager')
        document = apply(initial(), 'team', 'stage', {'name': '常规赛'})
        for i in range(9):
            document = apply(document, 'team', 'team', {'name': str(i)})
        self.event = Event.objects.create(name='测试赛', kind='team', document=document)
        self.event.editors.add(self.manager)
        self.client.force_login(self.manager)
        self.page = f'/manage/events/{self.event.pk}/batch-schedule/'
        self.api = f'/api/events/{self.event.pk}/'
        self.ids = [team['id'] for team in document['teams']]
        self.payload = dict(action='batch-schedule', revision=self.event.revision,
                            stageId=document['stages'][0]['id'])
        self.row = dict(day='2027-01-01', time='19:30', table=1, teams=self.ids[:4])

    def post(self, rows):
        return self.client.post(self.api, dict(self.payload, rows=rows), content_type='application/json')

    def test_unequal_counts_save_once(self):
        self.assertContains(self.client.get(self.page), '阶段次数校验')
        rows = [self.row, dict(self.row, day='2027-01-02')]
        self.assertEqual(self.post(rows).status_code, 200)
        self.assertEqual(self.post(rows).status_code, 409)
        self.event.refresh_from_db()
        self.assertEqual(len(self.event.document['matches']), 2)
        self.assertEqual(Audit.objects.get(event=self.event).actor, self.manager)

    def test_conflicts_rollback(self):
        for other in [dict(self.row, table=2), dict(self.row, teams=self.ids[4:8]),
                      dict(self.row, day='2027-01-02', teams=['foreign'] + self.ids[:3]),
                      dict(self.row, day='2027-01-02', table=30)]:
            self.assertEqual(self.post([self.row, other]).status_code, 400)
        self.event.refresh_from_db()
        self.assertFalse(self.event.document['matches'])
        self.assertFalse(Audit.objects.filter(event=self.event).exists())
        self.assertEqual(self.post([self.row]).status_code, 200)
        self.payload['revision'] += 1
        self.assertEqual(self.post([dict(self.row, table=2)]).status_code, 400)

    def test_scope_and_archive(self):
        outsider = get_user_model().objects.create_user('outsider')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.page).status_code, 404)
        self.assertEqual(self.post([self.row]).status_code, 404)
        self.client.force_login(self.manager)
        self.event.document['archive'] = {'snapshot': True}
        self.event.save()
        self.assertEqual(self.client.get(self.page).status_code, 403)
        self.assertEqual(self.post([self.row]).status_code, 403)
