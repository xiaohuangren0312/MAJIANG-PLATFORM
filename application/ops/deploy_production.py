"""Deploy an explicitly selected committed revision; run as root on work-host.
Never imports development data or credentials. Production bootstrap is separate.
"""
import argparse, json, os, pathlib, pwd, secrets, subprocess, time
P=pathlib.Path
ROOT=P('/data/majiang/prod')
REPO=P('/data/majiang/dev/app')
def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)
def owner(path,user='majiang-prod',mode=None):
    u=pwd.getpwnam(user);os.chown(path,u.pw_uid,u.pw_gid)
    if mode is not None:os.chmod(path,mode)
def write(path,text,user='majiang-prod',mode=0o600):
    path.write_text(text);owner(path,user,mode)
def asuser(user,*args,**kw):return run('runuser','-u',user,'--',*args,**kw)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--revision',required=True);a=ap.parse_args()
    assert os.geteuid()==0, 'root required for service management'
    uuid=subprocess.check_output(['findmnt','-n','-o','UUID','/data'],text=True).strip()
    assert uuid=='b270c63c-c47e-445e-9058-ad3ea94db996', 'unexpected data mount'
    sha=subprocess.check_output(['git','-c',f'safe.directory={REPO}','-C',str(REPO),'rev-parse','--verify',a.revision+'^{commit}'],text=True).strip()
    release=ROOT/'releases'/sha[:12]
    if not release.exists():
        release.mkdir(mode=0o750)
        archive=subprocess.Popen(['git','-c',f'safe.directory={REPO}','-C',str(REPO),'archive',sha],stdout=subprocess.PIPE)
        run('tar','-x','-C',str(release),stdin=archive.stdout)
        archive.stdout.close();assert archive.wait()==0
        run('chown','-R','majiang-prod:majiang-prod',str(release))
    for d in ('cache','tmp','logs','data','uploads','backups','config'):
        (ROOT/d).mkdir(exist_ok=True);owner(ROOT/d,mode=0o700 if d=='config' else 0o750)
    secret=ROOT/'config/django-secret'
    if not secret.exists():write(secret,secrets.token_urlsafe(64)+'\n')
    try:pwd.getpwnam('pg-hql-prod')
    except KeyError:run('useradd','--system','--gid','majiang-prod','--home-dir',str(ROOT/'data/postgres'),'--no-create-home','--shell','/usr/sbin/nologin','pg-hql-prod')
    for name in ('data/postgres','data/pg-run','logs/postgres'):
        q=ROOT/name;q.mkdir(exist_ok=True);owner(q,'pg-hql-prod',0o700 if name.endswith('postgres') else 0o770)
    pg=ROOT/'data/postgres';bin='/usr/lib/postgresql/18/bin/'
    if not (pg/'PG_VERSION').exists():
        asuser('pg-hql-prod',bin+'initdb','-D',str(pg),'--auth-local=peer','--auth-host=scram-sha-256','--encoding=UTF8','--locale=C.UTF-8',stdout=subprocess.DEVNULL)
        with (pg/'postgresql.conf').open('a') as f:f.write("\nlisten_addresses = ''\nport = 5434\nunix_socket_directories = '/data/majiang/prod/data/pg-run'\nunix_socket_permissions = 0770\nlogging_collector = on\nlog_directory = '/data/majiang/prod/logs/postgres'\nlog_filename = 'postgresql-%Y-%m-%d.log'\nlog_rotation_age = 1d\n")
    pgunit=P('/etc/systemd/system/hql-postgres-prod.service')
    pgunit.write_text('[Unit]\nDescription=Huanquelou production PostgreSQL\nAfter=network.target\nRequiresMountsFor=/data/majiang/prod\n[Service]\nUser=pg-hql-prod\nGroup=majiang-prod\nExecStart=/usr/lib/postgresql/18/bin/postgres -D /data/majiang/prod/data/postgres\nExecReload=/bin/kill -HUP $MAINPID\nKillSignal=SIGINT\nTimeoutStopSec=120\nRestart=on-failure\nUMask=0077\nNoNewPrivileges=true\nProtectSystem=strict\nProtectHome=true\nReadWritePaths=/data/majiang/prod/data/postgres /data/majiang/prod/data/pg-run /data/majiang/prod/logs/postgres\n[Install]\nWantedBy=multi-user.target\n')
    run('systemctl','daemon-reload');run('systemctl','enable','--now','hql-postgres-prod')
    for _ in range(20):
        if subprocess.run([bin+'pg_isready','-h',str(ROOT/'data/pg-run'),'-p','5434'],stdout=subprocess.DEVNULL).returncode==0:break
        time.sleep(.5)
    conn=['-h',str(ROOT/'data/pg-run'),'-p','5434','-d','postgres']
    def sql(query):return subprocess.check_output(['runuser','-u','pg-hql-prod','--',bin+'psql',*conn,'-At','-v','ON_ERROR_STOP=1','-c',query],text=True).strip()
    if sql("SELECT count(*) FROM pg_roles WHERE rolname='majiang-prod'")=='0':sql('CREATE ROLE "majiang-prod" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    if sql("SELECT count(*) FROM pg_database WHERE datname='hql_prod'")=='0':sql('CREATE DATABASE hql_prod OWNER "majiang-prod"')
    write(ROOT/'config/db-backend','postgresql\n')
    write(ROOT/'config/postgresql.json',json.dumps(dict(NAME='hql_prod',USER='majiang-prod',HOST=str(ROOT/'data/pg-run'),PORT='5434'))+'\n')
    venv=ROOT/'venv'
    if not (venv/'bin/python').exists():asuser('majiang-prod','/usr/bin/python3.14','-m','venv',str(venv))
    env=os.environ.copy();env.update(HQL_ENV_ROOT=str(ROOT),TMPDIR=str(ROOT/'tmp'),PYTHONPYCACHEPREFIX=str(ROOT/'cache/pycache'),PIP_CACHE_DIR=str(ROOT/'cache/pip'))
    asuser('majiang-prod',str(venv/'bin/pip'),'install','-r',str(release/'application/requirements.lock'),env=env)
    asuser('majiang-prod',bin+'pg_dump','-h',str(ROOT/'data/pg-run'),'-p','5434','-d','hql_prod','-Fc','-f',str(ROOT/'backups'/('before-release-'+sha[:12]+'-'+str(int(time.time()))+'.dump')))
    for args in [('check',),('migrate','--noinput'),('collectstatic','--noinput')]:
        asuser('majiang-prod',str(venv/'bin/python'),'manage.py',*args,cwd=release/'application',env=env)
    # Health-check release before switching the persistent service.
    log=(ROOT/'logs/release-check.log').open('a')
    proc=subprocess.Popen(['runuser','-u','majiang-prod','--',str(venv/'bin/gunicorn'),'hql.wsgi:application','--bind','127.0.0.1:8772','--workers','1','--worker-tmp-dir',str(ROOT/'tmp')],cwd=release/'application',env=env,stdout=log,stderr=log)
    try:
        import urllib.request
        for _ in range(30):
            try:
                data=json.load(urllib.request.urlopen('http://127.0.0.1:8772/health/',timeout=2))
                assert data=={'status':'ok','environment':'prod'};break
            except OSError:time.sleep(.5)
        else:raise RuntimeError('release health check failed')
    finally:proc.terminate();proc.wait(timeout=20);log.close()
    link=ROOT/'current.next';link.unlink(missing_ok=True);link.symlink_to(release);link.replace(ROOT/'current')
    unit=P('/etc/systemd/system/hql-prod.service')
    unit.write_text('[Unit]\nDescription=Huanquelou production application\nAfter=network.target hql-postgres-prod.service\nRequires=hql-postgres-prod.service\nRequiresMountsFor=/data/majiang/prod\n[Service]\nUser=majiang-prod\nGroup=majiang-prod\nWorkingDirectory=/data/majiang/prod/current/application\nEnvironment=HQL_ENV_ROOT=/data/majiang/prod\nEnvironment=TMPDIR=/data/majiang/prod/tmp\nEnvironment=PYTHONPYCACHEPREFIX=/data/majiang/prod/cache/pycache\nExecStart=/data/majiang/prod/venv/bin/gunicorn hql.wsgi:application --bind 127.0.0.1:8771 --workers 2 --threads 4 --worker-tmp-dir /data/majiang/prod/tmp --access-logfile /data/majiang/prod/logs/access.log --error-logfile /data/majiang/prod/logs/gunicorn.log\nRestart=on-failure\nUMask=0027\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=strict\nProtectHome=true\nReadWritePaths=/data/majiang/prod\n[Install]\nWantedBy=multi-user.target\n')
    run('systemctl','daemon-reload');run('systemctl','enable','hql-prod');run('systemctl','restart','hql-prod')
    print('Production release:',sha)
if __name__=='__main__':main()
