"""Venue administration is scoped to the current request database."""
from hql.tenancy import database
VENUE_ADMIN = 'venue-admin'
PLATFORM_SHADOW = 'platform-identity'
def venue_admin(user):
    if not user.is_authenticated or not user.is_active:return False
    if user._state.db != database():return False
    return user.is_superuser or user.groups.filter(name=VENUE_ADMIN).exists()
