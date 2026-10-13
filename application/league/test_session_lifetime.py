from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase, Client
from django.utils import timezone


class SessionLifetimeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('session-review', password='Session-test-password-2026')

    def signin(self):
        return self.client.post('/login/', {'username': self.user.username, 'password': 'Session-test-password-2026'})

    def test_persistent_thirty_days_and_browser_reopen(self):
        before = timezone.now()
        response = self.signin()
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['expires'])
        self.assertGreaterEqual(int(cookie['max-age']), 2591998)
        self.assertLessEqual(int(cookie['max-age']), 2592000)
        expiry = self.client.session.get_expiry_date()
        self.assertGreaterEqual(expiry, before + timedelta(days=30))
        browser = Client()
        browser.cookies[settings.SESSION_COOKIE_NAME] = cookie.value
        self.assertEqual(browser.get('/account/').status_code, 200)

    def test_reads_and_writes_do_not_extend_deadline(self):
        self.signin()
        expiry = self.client.session.get_expiry_date()
        with patch('django.utils.timezone.now', return_value=timezone.now()+timedelta(days=5)):
            self.assertEqual(self.client.get('/account/').status_code, 200)
            session = self.client.session
            session['test_preference'] = 'value'
            session.save()
            self.assertEqual(session.get_expiry_date(), expiry)
            self.assertEqual(Session.objects.get(session_key=session.session_key).expire_date, expiry)

    def test_expired_session_requires_login(self):
        self.signin()
        with patch('django.utils.timezone.now', return_value=timezone.now()+timedelta(days=31)):
            self.assertEqual(self.client.get('/account/').status_code, 302)

    def test_logout_revokes_old_cookie(self):
        self.signin()
        key = self.client.session.session_key
        self.client.post('/logout/')
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        browser = Client()
        browser.cookies[settings.SESSION_COOKIE_NAME] = key
        self.assertEqual(browser.get('/account/').status_code, 302)

    def test_disabled_user_and_password_reset_revoke_session(self):
        self.signin()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get('/account/').status_code, 302)
        self.user.is_active = True
        self.user.save()
        self.signin()
        self.user.set_password('Replacement-password-2026')
        self.user.save()
        self.assertEqual(self.client.get('/account/').status_code, 302)
