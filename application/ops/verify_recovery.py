"""Create and verify an isolated development recovery copy; never restore over an app DB."""
import os,sys,json,subprocess,hashlib,uuid,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hql.settings')
import django
django.setup()
from django.conf import settings
import psycopg
from psycopg import sql
if settings.ENV_ROOT.name!='dev':raise SystemExit('Development verification only')
key=sys.argv[1] if len(sys.argv)>1 else 'hql'
venue=settings.VENUES[key];db=settings.DATABASES[venue['database']]
if db['ENGINE']!='django.db.backends.postgresql':raise SystemExit('PostgreSQL required')
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
folder=settings.ENV_ROOT/'backups'/'recovery-check'/stamp;folder.mkdir(parents=True,mode=0o700)
dump=folder/(key+'.dump');tempdb='hql_dev_verify_'+uuid.uuid4().hex[:12]
env={**os.environ,'PGHOST':str(db['HOST']),'PGPORT':str(db['PORT']),'PGUSER':db['USER'],'PGPASSWORD':db['PASSWORD'],'PGDATABASE':db['NAME']}
connargs=dict(host=db['HOST'],port=db['PORT'],user=db['USER'],password=db['PASSWORD'])
def counts(c):
    tables=c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
    return {name:c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0] for (name,) in tables}
def fingerprint(c):
    rows=c.execute('SELECT id,revision,document FROM league_event ORDER BY id').fetchall()
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
with psycopg.connect(dbname=db['NAME'],**connargs) as source:
    source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    snapshot=source.execute('SELECT pg_export_snapshot()').fetchone()[0]
    expected=counts(source);digest=fingerprint(source)
    subprocess.run(['pg_dump','-Fc','--snapshot='+snapshot,'-f',str(dump)],env=env,check=True,stdout=subprocess.DEVNULL)
os.chmod(dump,0o600)
with psycopg.connect(dbname=db['NAME'],autocommit=True,**connargs) as admin:
    admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(tempdb)))
    try:
        subprocess.run(['pg_restore','--exit-on-error','--no-owner','--no-privileges','-d',tempdb,str(dump)],env=env,check=True,stdout=subprocess.DEVNULL)
        with psycopg.connect(dbname=tempdb,**connargs) as restored:
            assert counts(restored)==expected,'Table counts differ'
            assert fingerprint(restored)==digest,'Event content differs'
    finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(tempdb)))
sha=hashlib.sha256(dump.read_bytes()).hexdigest()
evidence={'local':dict(verified=True,status='备份已校验',detail=f'{len(expected)} 张数据表 · SHA-256 已记录',at=stamp),'restore':dict(verified=True,status='恢复验证通过',detail='独立临时库恢复，表记录数与赛事内容一致；临时库已清理',at=stamp),'offsite':dict(verified=False,status='待验证',detail='尚未核验异机副本'),'artifact':str(dump),'sha256':sha}
evidence_dir=settings.ENV_ROOT/'backups'/'verification';evidence_dir.mkdir(exist_ok=True,mode=0o700)
(evidence_dir/(key+'.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(json.dumps(dict(artifact=str(dump),sha256=sha,tables=len(expected)),ensure_ascii=False))
