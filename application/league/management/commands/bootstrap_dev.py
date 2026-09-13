import json,secrets
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from league.models import HistoricalArchive

class Command(BaseCommand):
    help='Create an initial development administrator and read-only historical archives, without overwriting existing records.'
    def add_arguments(self,parser):parser.add_argument('--history',required=True)
    def handle(self,*args,**opts):
        if str(settings.ENV_ROOT)!='/data/majiang/dev':raise CommandError('Only the development environment is supported')
        User=get_user_model()
        if not User.objects.filter(username='hql-admin').exists():
            password='1234@qwer'
            User.objects.create_superuser(username='hql-admin',password=password)
            path=settings.ENV_ROOT/'config/admin-login.txt'
            path.write_text('用户名：hql-admin\n密码：'+password+'\n',encoding='utf-8');path.chmod(0o600)
            self.stdout.write('Initial administrator created; credentials saved in development config.')
        data=json.loads(Path(opts['history']).read_text(encoding='utf-8'))
        for t in data['tournaments']:
            archive,created=HistoricalArchive.objects.get_or_create(key=t['id'],defaults={'payload':t})
            self.stdout.write(f"Historical archive {t['id']}: {'created' if created else 'already exists; kept unchanged'}")
