import json,os,uuid,fcntl
from pathlib import Path
from datetime import datetime,timezone
FIELDS={'name':80,'english':100,'tagline':160}
def read_brand(v):
 path=Path(v['root'])/'uploads/brand/settings.json'
 data=json.loads(path.read_text()) if path.exists() else {}
 return {**{k:data.get(k,v.get(k,'以牌会友 · 共赴山海' if k=='tagline' else '')) for k in FIELDS},'revision':data.get('revision',0)}
def update_brand(v,body,actor):
 from league.domain import require
 require(set(body)<=set(FIELDS)|{'revision'},'不支持的设置项')
 values={}
 for k,limit in FIELDS.items():
  val=body.get(k);require(isinstance(val,str),'字段格式错误');val=val.strip()
  require(len(val)<=limit and (k!='name' or bool(val)),'场馆名称必填，字段长度超限');values[k]=val
 root=Path(v['root'])/'uploads/brand';root.mkdir(parents=True,exist_ok=True)
 with (root/'settings.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  old=read_brand(v);require(type(body.get('revision')) is int and body['revision']==old['revision'],'设置已更新，请刷新后重试')
  path=root/'settings.json';history=json.loads(path.read_text()).get('history',[]) if path.exists() else []
  record=dict(actorId=actor.pk,actor=actor.username,at=datetime.now(timezone.utc).isoformat(),before=old,after=values)
  result=dict(**values,revision=old['revision']+1,history=history+[record])
  temp=root/(uuid.uuid4().hex+'.tmp')
  try:
   with temp.open('x') as f:json.dump(result,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
   temp.chmod(0o640);os.replace(temp,path)
  finally:temp.unlink(missing_ok=True)
 return read_brand(v)
