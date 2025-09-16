from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

urlpatterns = [
    # Serve /favicon.ico from static files
    re_path(r"^favicon\.ico$", RedirectView.as_view(url=staticfiles_storage.url("favicon.png"), permanent=True)),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("orchestrator.urls")),
]
