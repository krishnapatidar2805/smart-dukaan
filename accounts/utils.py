from .models import AuditLog


def log_activity(shop, user, action, module, object_repr, details=""):
    """Helper to record audit trail activity for shop actions."""
    if not shop:
        return None
    return AuditLog.objects.create(
        shop=shop,
        user=user if user and user.is_authenticated else None,
        action=action,
        module=module,
        object_repr=str(object_repr)[:200],
        details=str(details),
    )
