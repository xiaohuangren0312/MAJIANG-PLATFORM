import os,json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hql.settings')
import django;django.setup()
from django.core.management import call_command
from django.core import serializers
from django.db import connection
from io import StringIO
from collections import Counter
stream=StringIO()
call_command('dumpdata',exclude=['contenttypes','auth.permission'],use_natural_foreign_keys=True,stdout=stream,verbosity=0)
rows=json.loads(stream.getvalue())
# Stable ordering includes related primary keys serialized by natural keys.
rows.sort(key=lambda r:(r['model'],str(r['pk'])))
canonical=json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':'))
print(json.dumps({'backend':connection.vendor,'counts':dict(Counter(r['model'] for r in rows)),'sha256':hashlib.sha256(canonical.encode()).hexdigest()}))
