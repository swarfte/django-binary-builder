"""Initial administrator creation for SQLite first-run initialization."""

import logging
import os
from typing import Any

from django_binary_builder.exceptions import RuntimeInitializationError

ADMIN_USERNAME_VARIABLE = "DJANGO_BINARY_ADMIN_USERNAME"
ADMIN_PASSWORD_VARIABLE = "DJANGO_BINARY_ADMIN_PASSWORD"
ADMIN_EMAIL_VARIABLE = "DJANGO_BINARY_ADMIN_EMAIL"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234"
DEFAULT_ADMIN_EMAIL = "admin@localhost"

STATUS_CREATED = "created"
STATUS_ALREADY_EXISTS = "already_exists"
STATUS_SKIPPED_EXTERNAL = "skipped_external_database"
STATUS_DISABLED = "disabled"

logger = logging.getLogger(__name__)


def resolve_admin_credentials(
    admin_config: dict[str, Any],
) -> dict[str, str]:
    """Resolve admin credentials; the process environment wins."""

    return {
        "username": (
            os.environ.get(ADMIN_USERNAME_VARIABLE)
            or admin_config.get("username")
            or DEFAULT_ADMIN_USERNAME
        ),
        "password": (
            os.environ.get(ADMIN_PASSWORD_VARIABLE)
            or admin_config.get("password")
            or DEFAULT_ADMIN_PASSWORD
        ),
        "email": (
            os.environ.get(ADMIN_EMAIL_VARIABLE)
            or admin_config.get("email")
            or DEFAULT_ADMIN_EMAIL
        ),
    }


def create_initial_admin(
    defaults: dict[str, Any],
    *,
    database_mode: str,
) -> dict[str, Any]:
    """Create the initial administrator when conditions are met.

    Returns a status dictionary safe to store in the runtime state.
    Passwords are never included in the result or in log output.
    """

    admin_config = defaults.get("initial_admin", {})

    if not admin_config.get("enabled", True):
        return {
            "status": STATUS_DISABLED,
            "username": None,
            "password_change_required": False,
        }

    if database_mode != "sqlite" and admin_config.get("sqlite_only", True):
        logger.info(
            "Initial administrator creation is limited to SQLite mode; "
            "skipping for database mode '%s'.",
            database_mode,
        )
        return {
            "status": STATUS_SKIPPED_EXTERNAL,
            "username": None,
            "password_change_required": False,
        }

    from django.contrib.auth import get_user_model
    from django.db import transaction

    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    credentials = resolve_admin_credentials(admin_config)
    username = credentials["username"]

    existing = user_model._default_manager.filter(**{username_field: username}).first()

    if existing is not None:
        if admin_config.get("reset_password_if_user_exists"):
            logger.warning(
                "INITIAL_ADMIN.RESET_PASSWORD_IF_USER_EXISTS is not "
                "implemented in this version; the existing password for "
                "'%s' is preserved.",
                username,
            )

        logger.info(
            "Initial administrator '%s' already exists; leaving the account unchanged.",
            username,
        )

        return {
            "status": STATUS_ALREADY_EXISTS,
            "username": username,
            "password_change_required": False,
        }

    create_kwargs: dict[str, Any] = {
        username_field: username,
        "password": credentials["password"],
    }

    if username_field != "email" and _model_has_email_field(user_model):
        create_kwargs["email"] = credentials["email"]

    create_kwargs.update(admin_config.get("extra_fields") or {})

    try:
        with transaction.atomic():
            user_model._default_manager.create_superuser(**create_kwargs)
    except TypeError as error:
        raise RuntimeInitializationError(
            "Could not create the initial administrator with the "
            f"configured fields: {error}"
        ) from error

    logger.warning(
        "Initial administrator '%s' was created with a publicly "
        "documented default password. Change the password immediately "
        "after the first login.",
        username,
    )

    return {
        "status": STATUS_CREATED,
        "username": username,
        "password_change_required": bool(
            admin_config.get("require_password_change", True)
        ),
    }


def _model_has_email_field(user_model: Any) -> bool:
    try:
        user_model._meta.get_field("email")
    except Exception:
        return False

    return True
