from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from playwright.sync_api import APIRequestContext, sync_playwright

from core.app_config import AppConfig


@contextmanager
def api_request_context(
    base_url: str = "",
    timeout: Optional[int] = None,
    config: Optional[AppConfig] = None,
) -> Iterator[APIRequestContext]:
    """A thin wrapper around Playwright's own APIRequestContext, used in
    preference to a second HTTP library so API tests share Playwright's own
    request/response machinery instead of a separate one.

    This context is standalone - it does not share cookies or auth state
    with any `page`/`context` fixture. A test that genuinely needs that
    (e.g. reusing a UI login's session for API calls) should use the
    browser context's own `context.request` instead of this helper, which
    Playwright exposes for exactly that purpose.

    Pass `config` for an app-owned API (reads its base_url/action_timeout);
    pass an explicit `base_url` for a standalone API check not tied to any
    application, like the current jsonplaceholder smoke test.
    """
    if config is not None:
        base_url = base_url or config.base_url
        timeout = timeout if timeout is not None else config.action_timeout

    with sync_playwright() as pw:
        request_context = pw.request.new_context(
            base_url=base_url or None,
            timeout=float(timeout) if timeout is not None else None,
        )
        try:
            yield request_context
        finally:
            request_context.dispose()
