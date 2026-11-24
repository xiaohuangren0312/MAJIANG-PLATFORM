from datetime import date, time
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook

from .domain import apply, initial
from .models import Event


class ExcelImportTests(TestCase):
    def setUp(self):
        doc = apply(initial(), 'team', 'stage', {'name':'常规赛'})
        doc['stages'][0]['windMode'] = 'fixed'
        for name in '甲乙丙丁':
            doc = apply(doc, 'team', 'team', {'name':name})
        self.event = Event.objects.create(name='导入测试',kind='team',document=doc)
        user = get_user_model().objects.create_user('excel-manager')
        self.event.editors.add(user)
        self.client.force_login(user)
        self.url = f'/manage/events/{self.event.pk}/schedule-excel/'
        self.row = ['常规赛',date(2027,1,3),time(19,30),'A桌',*'甲乙丙丁']

    def upload(self, rows):
        book = load_workbook(BytesIO(self.client.get(self.url+'?template=1').content))
        for row in rows:
            book['赛程'].append(row)
        data = BytesIO()
        book.save(data)
        data.seek(0)
        data.name = 'schedule.xlsx'
        return self.client.post(self.url,{'workbook':data})

    def test_round_trip(self):
        preview = self.upload([self.row])
        self.assertContains(preview,'确认导入 1 场')
        self.event.refresh_from_db()
        self.assertFalse(self.event.document['matches'])
        body = dict(action='schedule-excel',token=preview.context['token'],revision=self.event.revision)
        api = f'/api/events/{self.event.pk}/'
        self.assertEqual(self.client.post(api,body,content_type='application/json').status_code,200)
        self.assertEqual(self.client.post(api,body,content_type='application/json').status_code,409)
        self.event.refresh_from_db()
        self.assertEqual(self.event.document['matches'][0]['seatDraw']['mode'],'fixed')
        self.assertContains(self.upload([self.row]),'已占用')

    def test_bad_rows(self):
        for rows, error in [([self.row,self.row],'第 3 行'),([self.row[:-1]+['陌生队']],'陌生队'),
                            ([self.row[:-1]+['=A2']],'含公式')]:
            response = self.upload(rows)
            self.assertContains(response,error)
            self.assertNotIn('token',response.context)

    def test_personal_excel_round(self):
        doc=apply(initial(),'personal','stage',{'name':'个人赛'})
        for i in range(12):
            doc=apply(doc,'personal','player',dict(number=str(i+1),name='选手'+str(i+1)))
        self.event.kind='personal'
        self.event.document=doc
        self.event.save()
        url=f'/manage/events/{self.event.pk}/batch-schedule/'
        response=self.client.post(url,dict(mode='template',ajax='1',stage=doc['stages'][0]['id'],
            days=['2027-01-03'],times=['19:30'],tables=['1','2','3'],entries=[p['id'] for p in doc['players']]))
        self.assertEqual(response.status_code,200)
        book=load_workbook(BytesIO(response.content))
        self.assertEqual(book['本轮排名'].max_row,13)
        for i,p in enumerate(doc['players']):
            book['赛程'].cell(2+i//4,5+i%4,f"{p['number']} · {p['name']}")
        data=BytesIO()
        book.save(data)
        data.seek(0)
        data.name='本轮.xlsx'
        response=self.client.post(url,dict(workbook=data,ajax='1'))
        self.assertEqual(response.status_code,200,response.content[:300])
        preview=response.json()
        self.event.refresh_from_db()
        self.assertFalse(self.event.document['matches'])
        api=f'/api/events/{self.event.pk}/'
        body=dict(action='pairing-commit',revision=preview['revision'],token=preview['token'],tables=preview['tables'])
        self.assertEqual(self.client.post(api,body,content_type='application/json').status_code,200)
        self.event.refresh_from_db()
        self.assertEqual(len(self.event.document['matches']),3)
