import os

import pytest

from django_binary_builder.conf import get_builder_settings
from django_binary_builder.context import create_build_context

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "tests.test_project.settings",
)


@pytest.fixture
def build_context(tmp_path, settings):
    def factory(**overrides):
        builder_settings = {
            "NAME": "Test App",
            "VERSION": "2.5.1",
            "PUBLISHER": "Test Publisher",
            "EXECUTABLE_NAME": "test-app",
            "OUTPUT_DIR": tmp_path / "release",
            "WORK_DIR": tmp_path / "work",
        }
        builder_settings.update(overrides)

        settings.DJANGO_BINARY_BUILDER = builder_settings

        config = get_builder_settings()

        return create_build_context(
            target_platform="windows",
            config=config,
        )

    return factory
