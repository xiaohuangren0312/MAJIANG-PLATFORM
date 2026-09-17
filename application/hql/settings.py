import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
ENV_ROOT=Path(os.environ.get('HQL_ENV_ROOT','/data/majiang/dev'))
SECRET_KEY=(ENV_ROOT/'config/django-secret').read_text().strip()
DEBUG=False
ALLOWED_HOSTS=[host.strip() for host in os.environ.get('HQL_ALLOWED_HOSTS','127.0.0.1,localhost,testserver').split(',') if host.strip()]
INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles','league','team_draft']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='hql.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates',BASE_DIR/'team_draft'/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.template.context_processors.csrf']}}]
# Explicit backend selection: missing PostgreSQL config must never fall back.
DB_BACKEND=os.environ.get('HQL_DB_BACKEND',(ENV_ROOT/'config/db-backend').read_text().strip() if (ENV_ROOT/'config/db-backend').exists() else 'sqlite')
if DB_BACKEND=='postgresql':
    import json
    pg_config=json.loads((ENV_ROOT/'config/postgresql.json').read_text())
    DATABASES={'default':{'ENGINE':'django.db.backends.postgresql',**pg_config,'CONN_MAX_AGE':60,'CONN_HEALTH_CHECKS':True}}
elif DB_BACKEND=='sqlite':
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':ENV_ROOT/'data/hql.sqlite3','OPTIONS':{'timeout':20}}}
else:raise RuntimeError('Unsupported database backend')
STATIC_URL='/assets/'
STATIC_ROOT=ENV_ROOT/'cache/static'
STATICFILES_DIRS=[BASE_DIR/'static']
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LANGUAGE_CODE='zh-hans'
TIME_ZONE='Asia/Shanghai'
USE_TZ=True
LOGIN_URL='/login/'
LOGIN_REDIRECT_URL='/manage/'
LOGOUT_REDIRECT_URL='/login/'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_SECURE=os.environ.get('HQL_HTTPS')=='1'
CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SESSION_COOKIE_AGE=28800
X_FRAME_OPTIONS='DENY'
SECURE_CONTENT_TYPE_NOSNIFF=True
DATA_UPLOAD_MAX_MEMORY_SIZE=2*1024*1024
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}}]
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'file':{'class':'logging.FileHandler','filename':str(ENV_ROOT/'logs/application.log')}},'root':{'handlers':['file'],'level':'WARNING'}}
