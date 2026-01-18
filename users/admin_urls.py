"""
URL routing для кастомных админских страниц (аналитика)
"""

from django.urls import path
from . import admin_views

urlpatterns = [
    # Главный дашборд
    path('dashboard/', admin_views.analytics_dashboard_view, name='admin_dashboard'),

    # API и экспорт
    path('api/dashboard-stats/', admin_views.dashboard_stats_api, name='admin_dashboard_stats_api'),
    path('export/excel/', admin_views.export_excel, name='admin_export_excel'),
]
