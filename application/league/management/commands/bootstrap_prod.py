"""Create a production administrator without copying development credentials."""
import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Create a missing production administrator; never reset existing users or import data.'
    def handle(self, *args, **options):
        if str(settings.ENV_ROOT) != '/data/majiang/prod':
            raise CommandError('Only the production environment is supported')
        User = get_user_model()
        if User.objects.filter(username='hql-admin').exists():
            self.stdout.write('Existing administrator retained.')
            return
        path = settings.ENV_ROOT / 'config/admin-login.txt'
        password = secrets.token_urlsafe(18)
        # Keep recovery credentials before the database write, with owner-only access.
        with path.open('x', encoding='utf-8') as f:
            path.chmod(0o600)
            f.write('用户名：hql-admin\n密码：' + password + '\n')
        try:
            User.objects.create_superuser(username='hql-admin', password=password)
        except Exception:
            path.unlink()
            raise
        self.stdout.write('Production administrator created; credentials saved in production config.')
