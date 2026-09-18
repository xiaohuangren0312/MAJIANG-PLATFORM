from django.urls import path,include
from league import views,media,archive_export,brand,event_brand
urlpatterns=[path("",include("team_draft.urls")),path("brand/logo",brand.logo),path("api/brand/logo/",brand.upload),path("api/rule-templates/",views.rule_templates),path("api/events/<uuid:id>/archive.csv",archive_export.download),path("api/events/<uuid:id>/image/",media.upload),path("media/roster/<uuid:id>/<str:name>",media.serve),path('api/history-reviews/<str:key>/import/',views.import_history),path('manage/history/',views.history_page),path('api/history-reviews/',views.history_reviews),path('api/history-reviews/<str:key>/',views.history_reviews),path('',views.index),path('index.html',views.index),path('data.json',views.public_data),path('account/',views.account),path('login/',views.signin),path('logout/',views.signout),path('manage/',views.manage),path('api/events/',views.events),path('api/events/<uuid:id>/',views.event_detail),path('api/events/<uuid:id>/access/',views.access_list),path('api/accounts/',views.create_account),path('assets/<str:name>',views.asset),path('health/',views.health)]

from django.conf import settings
if settings.HISTORY_BACKFILL_ENABLED:
    from league import history_backfill
    urlpatterns += [path('manage/history-backfill/',history_backfill.page),path('manage/history-backfill/review/',views.history_page),path('api/history-backfill/events/',history_backfill.events),path('api/history-backfill/events/<uuid:id>/',history_backfill.detail)]

urlpatterns += [path('brand/events/<uuid:id>/logo',event_brand.logo),path('api/events/<uuid:id>/logo/',event_brand.upload)]
