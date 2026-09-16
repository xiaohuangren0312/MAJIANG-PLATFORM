"""Edit historical stage labels/cutoffs without replaying settlement."""
import copy
from .domain import require,find,label,integer
from .history_correction import effective

def update(document,body):
    require(bool(document.get('historySnapshot')),'仅支持历史赛事')
    require(not document.get('archive'),'赛事已归档')
    result=copy.deepcopy(document);payload=copy.deepcopy(effective(document))
    stage=find(payload['stages'],body.get('id'));name=label(body.get('name'))
    require(not any(s['id']!=stage['id'] and s['name'].strip().casefold()==name.casefold() for s in payload['stages']),'阶段名称重复')
    count=integer(body.get('advanceCount',0),'晋级名次',0,10000)
    stage.update(name=name,advanceCount=count)
    result['historyCurrent']=payload
    return result
