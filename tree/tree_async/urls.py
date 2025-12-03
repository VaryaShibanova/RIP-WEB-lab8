"""
URL configuration for tree_async project.
"""

from django.urls import path, include

urlpatterns = [
    path('api/asynctree/', include('calculator.urls')),
]