"""Central platform credentials; ordinary users stay in their venue database."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group
from django.db import transaction
from hql.tenancy import database
from league.roles import PLATFORM_SHADOW

class VenueBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User=get_user_model(); alias=database()
        username=username or kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:return None
        if alias != 'default':
            central=User.objects.using('default').filter(username=username,is_superuser=True).first()
            if central:
                if not central.is_active or not central.check_password(password):return None
                with transaction.atomic(using=alias):
                    local=User.objects.using(alias).filter(username=username).first()
                    if local and not local.groups.filter(name=PLATFORM_SHADOW).exists():return None
                    if local is None:local=User(username=username)
                    local.password=central.password;local.is_active=True;local.is_superuser=True;local.is_staff=True
                    local.save(using=alias)
                    group,_=Group.objects.using(alias).get_or_create(name=PLATFORM_SHADOW)
                    local.groups.add(group)
                return local
            local=User.objects.using(alias).filter(username=username).first()
            if local and local.groups.filter(name=PLATFORM_SHADOW).exists():return None
        return super().authenticate(request,username=username,password=password,**kwargs)

    def get_user(self,user_id):
        user=super().get_user(user_id)
        if user and database()!='default' and user.groups.filter(name=PLATFORM_SHADOW).exists():
            central=get_user_model().objects.using('default').filter(username=user.username,is_superuser=True,is_active=True).first()
            if not central or central.password!=user.password:return None
        return user

    @staticmethod
    def credential_user(user):
        if database()!='default' and user.groups.filter(name=PLATFORM_SHADOW).exists():
            return get_user_model().objects.using('default').get(username=user.username,is_superuser=True,is_active=True)
        return user
