from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

from config.settings import ACTION_TIMEOUT, BASE_DIR, ENVIRONMENT, RETRY_COUNT

APPS_DIR = BASE_DIR / "apps"

_KNOWN_KEYS = {"base_url", "action_timeout", "retry_count", "ignore_https_errors", "secrets"}


@dataclass(frozen=True)
class AppConfig:
    """Resolved configuration for one application in one environment.

    Loaded from apps/<app_name>/config/<environment>.json. Fields not present in
    the JSON fall back to the framework-wide defaults in config/settings.py.
    """

    app_name: str
    environment: str
    base_url: str
    action_timeout: int
    retry_count: int
    # Defaults to True to preserve every existing app's current behavior
    # unchanged. A future app whose environment has a real certificate to
    # validate can set "ignore_https_errors": false in its own config JSON.
    ignore_https_errors: bool = True
    secrets: dict[str, str] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def secret(self, name: str) -> str:
        try:
            return self.secrets[name]
        except KeyError:
            raise KeyError(
                f"App '{self.app_name}' has no secret '{name}' resolved. Add it to the "
                f"'secrets' map in apps/{self.app_name}/config/{self.environment}.json "
                "(value must be an environment variable NAME, not the secret itself) "
                "and set that environment variable."
            ) from None


@lru_cache(maxsize=None)
def load_app_config(app_name: str, environment: str | None = None) -> AppConfig:
    env_name = environment or ENVIRONMENT
    config_path = APPS_DIR / app_name / "config" / f"{env_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No config found for app '{app_name}' in environment '{env_name}' "
            f"(expected {config_path}). Add apps/{app_name}/config/{env_name}.json."
        )

    raw = json.loads(config_path.read_text(encoding="utf-8"))

    resolved_secrets: dict[str, str] = {}
    for logical_name, env_var in raw.get("secrets", {}).items():
        value = os.getenv(env_var)
        if value is not None:
            resolved_secrets[logical_name] = value

    ignore_https_errors = raw.get("ignore_https_errors", True)
    if not isinstance(ignore_https_errors, bool):
        # bool("false") is True in Python - silently coercing a malformed
        # value here would flip a security-relevant setting to the opposite
        # of what was written instead of failing. A JSON string like
        # "false" is a plausible typo (JSON booleans are unquoted), so this
        # must fail loudly rather than coerce.
        raise ValueError(
            f"'ignore_https_errors' in apps/{app_name}/config/{env_name}.json must be a "
            f"JSON boolean (true/false, unquoted), got {ignore_https_errors!r}"
        )

    return AppConfig(
        app_name=app_name,
        environment=env_name,
        base_url=raw.get("base_url", ""),
        action_timeout=int(raw.get("action_timeout", ACTION_TIMEOUT)),
        retry_count=int(raw.get("retry_count", RETRY_COUNT)),
        ignore_https_errors=ignore_https_errors,
        secrets=resolved_secrets,
        extra={k: v for k, v in raw.items() if k not in _KNOWN_KEYS},
    )
