import importlib


def test_headless_defaults_to_false_locally(monkeypatch):
    monkeypatch.delenv("HEADLESS", raising=False)
    monkeypatch.delenv("CI", raising=False)

    import config.settings as settings

    reloaded = importlib.reload(settings)

    assert reloaded.HEADLESS is False


def test_headless_defaults_to_true_in_ci(monkeypatch):
    monkeypatch.delenv("HEADLESS", raising=False)
    monkeypatch.setenv("CI", "true")

    import config.settings as settings

    reloaded = importlib.reload(settings)

    assert reloaded.HEADLESS is True
