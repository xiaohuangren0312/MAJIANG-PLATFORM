"""Delete unused roster identities without cascading into competition records."""
import copy
from .domain import require, find


def delete_roster(document, kind, entity_id):
    require(not document.get('archive'), '赛事已归档，名单不可删除')
    require(kind in ('team', 'player'), '名单类型错误')
    historical = bool(document.get('historySnapshot'))
    payload = (document.get('historyCurrent') or document.get('historySnapshot')) if historical else document
    collection = 'teams' if kind == 'team' else 'players'
    row = find(payload.get(collection, []), entity_id)
    references = []
    names = {'teams':'队伍/教练', 'players':'选手归属/转队/羁绊', 'matches':'赛程与战果',
             'results':'历史战果', 'schedule':'历史赛程', 'settlements':'阶段结算',
             'statistics':'阶段排行', 'snapshots':'阶段快照', 'dailySummaries':'比赛日成绩'}
    def contains(value):
        if isinstance(value, dict):
            return entity_id in value or any(contains(v) for v in value.values())
        if isinstance(value, list): return any(contains(v) for v in value)
        return value == entity_id
    for key, value in payload.items():
        if key=='archiveRevision':continue  # Frozen prior publication is not an active dependency.
        if key == collection:
            value = [x for x in value if x.get('id') != entity_id]
        if contains(value): references.append(names.get(key, '赛事关联记录'))
    require(not references, '无法删除“' + row['name'] + '”：仍被' + '、'.join(dict.fromkeys(references)) + '引用。请先处理关联记录；已有战果的名单应保留。')
    result = copy.deepcopy(document)
    target = copy.deepcopy(payload) if historical else result
    target[collection] = [x for x in target[collection] if x['id'] != entity_id]
    if historical: result['historyCurrent'] = target
    return result


def referenced(value, entity_id):
    if isinstance(value,dict):return entity_id in value or any(referenced(v,entity_id) for v in value.values())
    if isinstance(value,list):return any(referenced(v,entity_id) for v in value)
    return value==entity_id
