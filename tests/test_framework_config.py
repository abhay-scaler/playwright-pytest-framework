import importlib


def test_environment_settings_are_exposed(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://example.test")
    monkeypatch.setenv("BROWSER", "firefox")
    monkeypatch.setenv("ACTION_TIMEOUT", "12345")
    monkeypatch.setenv("RETRY_COUNT", "3")

    import config.settings as settings

    reloaded = importlib.reload(settings)

    assert reloaded.BASE_URL == "https://example.test"
    assert reloaded.BROWSER_NAME == "firefox"
    assert reloaded.ACTION_TIMEOUT == 12345
    assert reloaded.RETRY_COUNT == 3
