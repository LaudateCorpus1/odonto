"""
Urls for the Odonto project
"""
from django.conf.urls import include, url
from django.urls import path
from opal.urls import urlpatterns as opatterns

from odonto import views

urlpatterns = [
    path('summary-fp17/<int:pk>/', views.FP17SummaryDetailView.as_view(),
         name='odonto-summary-fp17'),
    path('view-fp17/<int:pk>/', views.ViewFP17DetailView.as_view(),
         name='odonto-view-fp17'),

    path('summary-fp17-o/<int:pk>/', views.FP17OSummaryDetailView.as_view(),
         name='odonto-summary-fp17-o'),
    path('view-fp17-o/<int:pk>/', views.ViewFP17ODetailView.as_view(),
         name='odonto-view-fp17-o'),


    url('^unsubmitted-fp17s',
        views.UnsubmittedFP17s.as_view(),
        name='odonto-unsubmitted-fp17s'),

    url('^open-fp17s',
        views.OpenFP17s.as_view(),
        name='odonto-open-fp17s'),
    url('^stats', views.Stats.as_view(), name="odonto-stats"),
]

urlpatterns += opatterns
