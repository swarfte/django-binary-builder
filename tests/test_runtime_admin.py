from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from django_binary_builder.runtime.admin import (
    create_initial_admin,
    resolve_admin_credentials,
)

pytestmark = pytest.mark.django_db


def make_defaults(**admin_overrides):
    admin = {
        "enabled": True,
        "sqlite_only": True,
        "username": "admin",
        "password": "admin1234",
        "email": "admin@localhost",
        "extra_fields": {},
        "require_password_change": True,
    }
    admin.update(admin_overrides)

    return {"initial_admin": admin}


def test_creates_superuser_with_defaults():
    result = create_initial_admin(make_defaults(), database_mode="sqlite")

    user_model = get_user_model()

    user = user_model._default_manager.get(username="admin")

    assert result["status"] == "created"
    assert result["username"] == "admin"
    assert result["password_change_required"] is True
    assert user.check_password("admin1234")
    assert user.is_superuser
    assert user.is_staff


def test_existing_user_is_not_recreated():
    create_initial_admin(make_defaults(), database_mode="sqlite")

    user_model = get_user_model()
    user = user_model._default_manager.get(username="admin")
    user.set_password("changed-by-operator")
    user.save()

    result = create_initial_admin(make_defaults(), database_mode="sqlite")

    user.refresh_from_db()

    assert result["status"] == "already_exists"
    assert result["password_change_required"] is False
    assert user.check_password("changed-by-operator")
    assert not user.check_password("admin1234")


def test_existing_user_email_is_not_modified():
    create_initial_admin(make_defaults(), database_mode="sqlite")

    user_model = get_user_model()
    user = user_model._default_manager.get(username="admin")
    user.email = "changed@example.com"
    user.save()

    create_initial_admin(make_defaults(), database_mode="sqlite")

    user.refresh_from_db()

    assert user.email == "changed@example.com"


def test_disabled_admin_is_skipped():
    result = create_initial_admin(
        make_defaults(enabled=False),
        database_mode="sqlite",
    )

    assert result["status"] == "disabled"

    assert not get_user_model()._default_manager.exists()


def test_external_database_skipped_when_sqlite_only():
    result = create_initial_admin(
        make_defaults(),
        database_mode="external",
    )

    assert result["status"] == "skipped_external_database"

    assert not get_user_model()._default_manager.exists()


def test_external_database_allowed_when_not_sqlite_only():
    result = create_initial_admin(
        make_defaults(sqlite_only=False),
        database_mode="external",
    )

    assert result["status"] == "created"


def test_environment_overrides_credentials(monkeypatch):
    monkeypatch.setenv("DJANGO_BINARY_ADMIN_USERNAME", "root-user")
    monkeypatch.setenv("DJANGO_BINARY_ADMIN_PASSWORD", "env-password")
    monkeypatch.setenv("DJANGO_BINARY_ADMIN_EMAIL", "root@example.com")

    result = create_initial_admin(make_defaults(), database_mode="sqlite")

    user_model = get_user_model()
    user = user_model._default_manager.get(username="root-user")

    assert result["status"] == "created"
    assert result["username"] == "root-user"
    assert user.check_password("env-password")


def test_resolve_credentials_defaults():
    credentials = resolve_admin_credentials({})

    assert credentials == {
        "username": "admin",
        "password": "admin1234",
        "email": "admin@localhost",
    }


def test_extra_fields_are_applied():
    result = create_initial_admin(
        make_defaults(extra_fields={"first_name": "Initial"}),
        database_mode="sqlite",
    )

    user = get_user_model()._default_manager.get(username="admin")

    assert result["status"] == "created"
    assert user.first_name == "Initial"


def test_regular_user_is_not_promoted():
    user_model = get_user_model()

    user_model._default_manager.create_user(
        username="admin",
        password="user-password",
    )

    result = create_initial_admin(make_defaults(), database_mode="sqlite")

    user = user_model._default_manager.get(username="admin")

    assert result["status"] == "already_exists"
    assert not user.is_superuser
    assert not user.is_staff
    assert user.check_password("user-password")


class StubMeta:
    def get_field(self, name):
        raise ValueError(f"Unknown field: {name}")


class StubQuerySet:
    def first(self):
        return None


class StubManager:
    def __init__(self):
        self.created = None

    def filter(self, **kwargs):
        return StubQuerySet()

    def create_superuser(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(**kwargs)


def test_custom_username_field_is_respected(monkeypatch):
    stub_model = SimpleNamespace(
        USERNAME_FIELD="email",
        _meta=StubMeta(),
        _default_manager=StubManager(),
    )

    monkeypatch.setattr(
        "django.contrib.auth.get_user_model",
        lambda: stub_model,
    )

    create_initial_admin(make_defaults(), database_mode="sqlite")

    created = stub_model._default_manager.created

    assert created is not None
    assert created["email"] == "admin"
    assert created["password"] == "admin1234"
    assert "username" not in created


def test_email_setting_skipped_when_model_has_no_email_field(monkeypatch):
    stub_model = SimpleNamespace(
        USERNAME_FIELD="identifier",
        _meta=StubMeta(),
        _default_manager=StubManager(),
    )

    monkeypatch.setattr(
        "django.contrib.auth.get_user_model",
        lambda: stub_model,
    )

    create_initial_admin(make_defaults(), database_mode="sqlite")

    created = stub_model._default_manager.created

    assert created["identifier"] == "admin"
    assert "email" not in created
