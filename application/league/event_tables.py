"""Stable event table identities and editable display names."""
from .domain import require, integer, find

def code(number):
    value=''
    while number>0:
        number,rem=divmod(number-1,26);value=chr(65+rem)+value
    return value

def catalog(d):
    if 'tables' in d:return d['tables']
    numbers=sorted({m['number'] for m in d.get('matches',[])}) or [1,2]
    return [dict(number=n,name=code(n)+'桌',active=True) for n in numbers]

def display(d,number):
    return next((t['name'] for t in catalog(d) if t['number']==number),code(number)+'桌')

def stage_tables(d,stage):
    active=[t['number'] for t in catalog(d) if t.get('active',True)]
    return [n for n in stage.get('tableNumbers',[]) if n in active]

def selection(d,values):
    require(isinstance(values,list) and values,'请至少选择一张桌')
    require(all(type(n) is int for n in values) and len(set(values))==len(values),'用桌编号重复或无效')
    active={t['number'] for t in catalog(d) if t.get('active',True)}
    require(set(values)<=active,'包含未配置或已停用的桌次')
    return values

def validate_match(d,number):
    if 'tables' not in d:return
    require(any(t['number']==number and t.get('active',True) for t in d['tables']),'请选择已启用的赛事桌次')

def update(d,rows):
    require(isinstance(rows,list) and 0<len(rows)<=1000,'请保留至少一张桌，最多1000张')
    clean=[];numbers=set();names=set()
    for row in rows:
        require(isinstance(row,dict),'桌次格式错误')
        n=integer(row.get('number'),'桌次编号',1,1000)
        name=row.get('name');require(isinstance(name,str) and 0<len(name.strip())<=40,'桌名应为1至40个字符')
        name=name.strip();require(not any(ord(c)<32 for c in name),'桌名不能含控制字符')
        require(n not in numbers,'桌次编号重复');require(name.casefold() not in names,'桌名重复')
        active=row.get('active',True);require(type(active) is bool,'桌次状态错误')
        numbers.add(n);names.add(name.casefold());clean.append(dict(number=n,name=name,active=active))
    active={t['number'] for t in clean if t['active']};require(active,'请保留至少一张启用的桌')
    used={m['number'] for m in d.get('matches',[])}
    used.update(int(n) for day in d.get('tableLive',{}).values() for n in day)
    used.update(n for s in d.get('stages',[]) for n in s.get('tableNumbers',[]))
    require(used<=numbers,'桌次已关联赛程、直播或阶段，不能删除；可改名')
    require(all(set(s.get('tableNumbers',[]))<=active for s in d.get('stages',[]) if not s.get('locked')),'请先调整未结束阶段的用桌，再停用桌次')
    d['tables']=clean
