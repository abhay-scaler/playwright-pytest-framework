import json

import pytest

from pwpf.core.app_config import load_app_config


def _write_config(apps_dir, app_name: str, environment: str, data: dict) -> None:
    config_dir = apps_dir / app_name / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / f"{environment}.json").write_text(json.dumps(data), encoding="utf-8")


def test_ignore_https_errors_defaults_to_true_when_omitted(tmp_path, monkeypatch):
    """Every app config written before this feature existed omits the key -
    it must keep behaving exactly as it did before this change."""
    monkeypatch.setattr("pwpf.core.app_config.apps_dir", lambda: tmp_path)
    _write_config(tmp_path, "no_override_app", "local", {"base_url": "https://example.test"})

    config = load_app_config("no_override_app", "local")

    assert config.ignore_https_errors is True


def test_ignore_https_errors_can_be_explicitly_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("pwpf.core.app_config.apps_dir", lambda: tmp_path)
    _write_config(
        tmp_path,
        "strict_tls_app",
        "local",
        {"base_url": "https://example.test", "ignore_https_errors": False},
    )

    config = load_app_config("strict_tls_app", "local")

    assert config.ignore_https_errors is False


def test_ignore_https_errors_rejects_a_quoted_string_instead_of_a_json_boolean(
    tmp_path, monkeypatch
):
    """bool("false") is True in Python - if this weren't validated, a plausible
    JSON typo would silently flip this security-relevant setting to the
    opposite of what was written instead of failing clearly."""
    monkeypatch.setattr("pwpf.core.app_config.apps_dir", lambda: tmp_path)
    _write_config(
        tmp_path,
        "malformed_tls_app",
        "local",
        {"base_url": "https://example.test", "ignore_https_errors": "false"},
    )

    with pytest.raises(ValueError, match="ignore_https_errors"):
        load_app_config("malformed_tls_app", "local")
