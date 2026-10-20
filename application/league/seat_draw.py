import secrets,datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from .domain import require,find,live_stage

def available(d,m):
    start=datetime.datetime.fromisoformat(m['date']+'T'+m['time']).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    return not d.get('archive') and m['state']=='draft' and not find(d['stages'],m['stageId']).get('locked') and start>timezone.now() and not any('score' in s for s in m['seats']) and not m.get('penalties') and not m.get('yakuman')

def draw(d,m,automatic=False):
    if automatic:
        if m.get('seatDraw') or not all(s.get('playerId') for s in m['seats']) or not available(d,m):return
    else:require(available(d,m),'本场已开赛、录分、取消或阶段锁定，不能随机座位')
    secrets.SystemRandom().shuffle(m['seats'])
    m['seatDraw']={'mode':'automatic' if automatic else 'manual','at':timezone.now().isoformat(),'count':m.get('seatDraw',{}).get('count',0)+1}
