"""One-time development cutover, run by root; commands execute as majiang-dev."""
import os,subprocess,json,datetime,pathlib
root=pathlib.Path('/data/majiang/dev/app/application')
envroot=pathlib.Path('/data/majiang/dev')
assert subprocess.check_output(['findmnt','-no','UUID','/data'],text=True).strip()=='b270c63c-c47e-445e-9058-ad3ea94db996'
assert not (envroot/'config/db-backend').exists(),'Already switched; do not repeat'
backup=envroot/'backups'/('sqlite-to-postgres-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
base=['runuser','-u','majiang-dev','--','env','PYTHONPYCACHEPREFIX=/data/majiang/dev/cache/pycache','TMPDIR=/data/majiang/dev/tmp']
python=str(envroot/'venv/bin/python')
def run(args,backend='sqlite',capture=False):
    return subprocess.run(base+['HQL_DB_BACKEND='+backend,python]+args,cwd=root,check=True,text=True,stdout=subprocess.PIPE if capture else None).stdout
# Check driver before interrupting service.
run(['-c','import psycopg'])
subprocess.run(['systemctl','stop','hql-dev'],check=True)
switched=False
try:
    run(['-c','import pathlib; p=pathlib.Path('+repr(str(backup))+'); p.mkdir(mode=0o700)'])
    run(['-c','import sqlite3; a=sqlite3.connect("/data/majiang/dev/data/hql.sqlite3"); b=sqlite3.connect('+repr(str(backup/'hql.sqlite3'))+'); a.backup(b); b.close(); a.close()'])
    run(['manage.py','dumpdata','--natural-foreign','--exclude','contenttypes','--exclude','auth.permission','--output',str(backup/'data.json')])
    before=json.loads(run(['ops/verify_database.py'],capture=True))
    run(['manage.py','migrate','--noinput'],'postgresql')
    run(['manage.py','loaddata',str(backup/'data.json')],'postgresql')
    after=json.loads(run(['ops/verify_database.py'],'postgresql',capture=True))
    assert before['counts']==after['counts'] and before['sha256']==after['sha256'], 'Migration comparison failed'
    print('Verified complete data equality:',after,flush=True)
    run(['manage.py','test','league','--verbosity','1'],'postgresql')
    report={'backup':str(backup),'before':before,'after':after}
    (backup/'verification.json').write_text(json.dumps(report,indent=2))
    run(['-c','from pathlib import Path; p=Path("/data/majiang/dev/config/db-backend"); p.write_text("postgresql"); p.chmod(0o600)'])
    drop=pathlib.Path('/etc/systemd/system/hql-dev.service.d');drop.mkdir(exist_ok=True)
    (drop/'postgresql.conf').write_text('[Unit]\nRequires=hql-postgres-dev.service\nAfter=hql-postgres-dev.service\n')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    switched=True
finally:
    subprocess.run(['systemctl','start','hql-dev'],check=True)
print('PostgreSQL cutover complete.' if switched else 'SQLite service resumed; cutover not committed.',flush=True)
print('Backup:',backup,flush=True)
