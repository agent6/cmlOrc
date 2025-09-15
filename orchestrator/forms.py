from django import forms
from django.contrib.auth import get_user_model
from urllib.parse import urlsplit, urlunsplit
from .models import CMLServer


User = get_user_model()


class CMLServerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(render_value=True))

    class Meta:
        model = CMLServer
        fields = [
            "name",
            "base_url",
            "username",
            "password",
            "verify_tls",
        ]

    def clean_base_url(self):
        url = self.cleaned_data.get("base_url", "").strip()
        if not url:
            return url
        parts = urlsplit(url)
        if not parts.scheme:
            parts = parts._replace(scheme="https")
        path = (parts.path or "").rstrip("/")
        if not path:
            path = "/api/v0"
        elif path == "/api":
            path = "/api/v0"
        elif "/api/" not in path:
            path = f"{path}/api/v0"
        parts = parts._replace(path=path)
        return urlunsplit(parts)


class AssignmentForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.order_by("username"))
    lab_name = forms.CharField(max_length=255, help_text="Lab name (or UUID)")
    minutes = forms.IntegerField(min_value=1, max_value=1440, initial=240, help_text="Lease duration in minutes")


class LabUploadForm(forms.Form):
    yaml_file = forms.FileField(allow_empty_file=False, help_text=".yaml or .yml export from CML")

    def clean_yaml_file(self):
        f = self.cleaned_data.get("yaml_file")
        if not f:
            return f
        name = (getattr(f, "name", "") or "").lower()
        if not (name.endswith(".yaml") or name.endswith(".yml")):
            return f
        return f


class HealthSettingsForm(forms.Form):
    MODE_CHOICES = (
        ("ping", "Lightweight (HEAD/GET ping)"),
        ("labs", "Full (authenticate + list labs)"),
    )

    mode = forms.ChoiceField(choices=MODE_CHOICES)
    check_interval_sec = forms.IntegerField(min_value=1, max_value=3600, label="Normal check interval (sec)")
    scheduler_tick_sec = forms.IntegerField(min_value=1, max_value=10, label="Scheduler tick (sec)")
    http_timeout_sec = forms.IntegerField(min_value=1, max_value=120, label="HTTP timeout (sec)")
    quick_retries = forms.IntegerField(min_value=0, max_value=10, label="Quick retries on first failure")
    quick_retry_delay_sec = forms.IntegerField(min_value=1, max_value=60, label="Quick retry delay (sec)")
    backoff_base_sec = forms.IntegerField(min_value=1, max_value=3600, label="Backoff base (sec)")
    backoff_max_sec = forms.IntegerField(min_value=1, max_value=86400, label="Backoff max (sec)")
    stats_interval_sec = forms.IntegerField(min_value=5, max_value=86400, initial=60, label="Stats snapshot interval (sec)")


# -----------------------------
# User management (staff-only)
# -----------------------------

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    is_staff = forms.BooleanField(label="Staff access", required=False, initial=False)

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = bool(self.cleaned_data.get("is_staff"))
        # Never create superusers from this form
        user.is_superuser = False
        user.set_password(self.cleaned_data.get("password1") or "")
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    is_staff = forms.BooleanField(label="Staff access", required=False)

    class Meta:
        model = User
        fields = ["username", "email"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = bool(self.cleaned_data.get("is_staff"))
        if commit:
            user.save()
        return user


class UserPasswordForm(forms.Form):
    password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned
