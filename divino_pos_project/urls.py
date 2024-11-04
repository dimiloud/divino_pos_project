from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('divino_pos.urls')),  # Inclure les URLs de l'application divino_pos
]
