from django.test import TestCase
from django.contrib.auth import get_user_model
from html.parser import HTMLParser

class NavParser(HTMLParser):
    def __init__(self):
        super().__init__();self.in_nav=False;self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='nav' and a.get('aria-label')=='教练主菜单':self.in_nav=True
        if self.in_nav and tag=='a':self.links.append(a)
    def handle_endtag(self,tag):
        if tag=='nav':self.in_nav=False

class CoachNavigationTests(TestCase):
    paths=['/coach/','/coach/lineups/','/coach/schedule/','/coach/profile/']
    def test_anonymous_pages_require_login(self):
        for path in self.paths:
            response=self.client.get(path)
            self.assertEqual(response.status_code,302)
            self.assertIn('/login/',response.url)
    def test_same_four_links_and_exact_active_destination(self):
        user=get_user_model().objects.create_user('navigation-coach')
        self.client.force_login(user)
        for path in self.paths:
            with self.subTest(path=path):
                response=self.client.get(path);self.assertEqual(response.status_code,200)
                parser=NavParser();parser.feed(response.content.decode())
                self.assertEqual([a['href'] for a in parser.links],self.paths)
                self.assertEqual([a['href'] for a in parser.links if a.get('aria-current')=='page'],[path])
