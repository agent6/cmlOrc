from django.urls import path
from . import views


app_name = "orchestrator"

urlpatterns = [
    path("", views.home, name="home"),
    # User management (staff only)
    path("users/", views.user_list, name="user_list"),
    path("users/add/", views.user_add, name="user_add"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/password/", views.user_password, name="user_password"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("settings/health/", views.health_settings, name="health_settings"),
    path("labs/upload/", views.labs_upload, name="labs_upload"),
    path("labs/upload/item/<int:pk>/", views.labs_upload_item, name="labs_upload_item"),
    # Simple API endpoint to assign a user to a lab and return server IP
    path("api/assign/", views.api_assign, name="api_assign"),
    # Simple API endpoint to release a user's assignment
    path("api/release/", views.api_release, name="api_release"),
    path("assign/", views.pool_assign, name="pool_assign"),
    path("servers/add/", views.server_add, name="server_add"),
    path("servers/<int:pk>/edit/", views.server_edit, name="server_edit"),
    path("servers/<int:pk>/clone/", views.server_clone, name="server_clone"),
    path("servers/<int:pk>/test/", views.server_test, name="server_test"),
    path("servers/<int:pk>/row/", views.server_row, name="server_row"),
    path("servers/<int:pk>/assign/", views.server_assign, name="server_assign"),
    path("servers/<int:pk>/release/", views.server_release, name="server_release"),
    path("servers/<int:pk>/delete/", views.server_delete, name="server_delete"),
    path("pool/metrics/", views.pool_metrics, name="pool_metrics"),
    path("pool/metrics/data/", views.pool_metrics_data, name="pool_metrics_data"),
    path("pool/counts/", views.pool_counts, name="pool_counts"),
    path("logs/leases/", views.lease_log, name="lease_log"),
]
