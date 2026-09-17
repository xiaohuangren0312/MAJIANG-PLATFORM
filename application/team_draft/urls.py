from django.urls import path
from . import views
urlpatterns=[path('draft/',views.home),path('draft/<uuid:id>/',views.page),path('api/draft/',views.activities),path('api/draft/<uuid:id>/',views.detail)]
