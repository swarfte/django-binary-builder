from django_binary_builder.builders.launcher import build_runtime_defaults


def test_runtime_defaults_include_server_mode_and_webview(build_context):
    context = build_context(
        NAME="Test App",
        SERVER={"MODE": "webview"},
        WEBVIEW={"WIDTH": 1000, "HEIGHT": 700, "RESIZABLE": False},
    )

    defaults = build_runtime_defaults(context)

    assert defaults["server"]["mode"] == "webview"
    assert defaults["webview"] == {
        "title": "Test App",
        "width": 1000,
        "height": 700,
        "resizable": False,
    }


def test_runtime_defaults_support_browser_mode(build_context):
    context = build_context(SERVER={"MODE": "browser", "OPEN_BROWSER": False})

    defaults = build_runtime_defaults(context)

    assert defaults["server"]["mode"] == "browser"
    assert defaults["server"]["open_browser"] is False
