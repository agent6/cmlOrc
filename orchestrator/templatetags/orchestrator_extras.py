from django import template
from django.utils import timezone

register = template.Library()


def _format_timedelta(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "expired"
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    else:
        parts.append(f"{seconds}s")
    return " ".join(parts)


@register.filter(name="time_left")
def time_left(assigned_until):
    if not assigned_until:
        return "-"
    now = timezone.now()
    delta = assigned_until - now
    return _format_timedelta(delta)


@register.filter(name="add_class")
def add_class(field, css):
    """Add CSS class to a form field widget in templates."""
    try:
        return field.as_widget(attrs={**field.field.widget.attrs, "class": (field.field.widget.attrs.get("class", "") + " " + css).strip()})
    except Exception:
        return field


@register.filter(name="add_attrs")
def add_attrs(field, attrs_str):
    """Add arbitrary attrs to a form field: 'placeholder=foo,style=color:red'"""
    try:
        attrs = {}
        for part in attrs_str.split(","):
            if not part.strip():
                continue
            if "=" in part:
                k, v = part.split("=", 1)
                attrs[k.strip()] = v.strip()
        return field.as_widget(attrs={**field.field.widget.attrs, **attrs})
    except Exception:
        return field
