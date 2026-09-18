"""Event-scoped edits; dependency checks are independent of administrator role."""
import copy,datetime,re
from .domain import require,find,live_stage,apply,label

def mutate(document,kind,action,body):
    require(not document.get('archive'),'请先开启归档修订')
    d=copy.deepcopy(document)
    if action=='match-delete':
        m=find(d['matches'],body.get('id'));live_stage(d,m['stageId'])
        require(not any(m['id'] in r.get('matchIds',[]) for r in d.get('pairingRounds',[])),'本场属于高高碰轮次，请先处理轮次依赖')
        d['matches'].remove(m)
    elif action=='match-update':
        m=find(d['matches'],body.get('id'));live_stage(d,m['stageId'])
        day=body.get('date');time=body.get('time');number=body.get('number')
        try:datetime.date.fromisoformat(day)
        except (TypeError,ValueError):require(False,'比赛日期格式错误')
        require(isinstance(time,str) and re.fullmatch(r'\d{2}:\d{2}',time),'时间格式应为HH:MM')
        require(0<=int(time[:2])<=23 and 0<=int(time[3:])<=59,'时间格式错误')
        try:datetime.time.fromisoformat(time)
        except (TypeError,ValueError):require(False,'时间格式错误')
        require(type(number) is int and 1<=number<=1000,'桌号超出范围')
        require(not any(x['id']!=m['id'] and x['state']!='cancelled' and x['date']==day and x['time']==time and x['number']==number for x in d['matches']),'同一开赛时间桌号重复')
        m.update(date=day,time=time,number=number,table=str(number))
    elif action=='stage-delete':
        stage=live_stage(d,body.get('id'))
        require(len(d['stages'])>1,'赛事至少保留一个阶段')
        require(not any(m['stageId']==stage['id'] for m in d['matches']),'阶段仍有赛程或战果，请先处理')
        require(not any(stage['id'] in [s['source'],s['target']] for s in d['settlements']),'阶段已参与结算，不能直接删除')
        require(not any(stage['id'] in p.get('bondStages',{}) for p in d['players']),'阶段仍有羁绊报名')
        d['stages'].remove(stage)
    elif action=='rule-delete':
        rule=find(d['rules'],body.get('id'))
        require(len(d['rules'])>1,'至少保留一个计分规则')
        require(not any(m.get('rule',{}).get('id')==rule['id'] for m in d['matches']),'计分规则已被对局引用，不能删除')
        d['rules'].remove(rule)
    return d
