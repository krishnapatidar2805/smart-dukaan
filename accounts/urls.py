from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("staff/", views.add_staff_view, name="staff_list"),
    path("audit-log/", views.audit_log_view, name="audit_log"),
    path("audit-log/clear/", views.audit_log_clear, name="audit_log_clear"),
]
