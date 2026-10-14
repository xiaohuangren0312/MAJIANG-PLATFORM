"""Keep transaction boundaries on the same database as the ORM router."""
from contextlib import ContextDecorator
from django.db import transaction as original
from .tenancy import database
class Atomic(ContextDecorator):
 def __init__(self,args,kwargs):self.args=args;self.kwargs=kwargs
 def _recreate_cm(self):return Atomic(self.args,self.kwargs)
 def __enter__(self):
  kwargs=dict(self.kwargs);kwargs.setdefault('using',database())
  self.cm=original.atomic(*self.args,**kwargs);return self.cm.__enter__()
 def __exit__(self,*args):return self.cm.__exit__(*args)
def atomic(*args,**kwargs):
 if args and callable(args[0]):return Atomic((),kwargs)(args[0])
 return Atomic(args,kwargs)
def set_rollback(value,using=None):return original.set_rollback(value,using=using or database())
