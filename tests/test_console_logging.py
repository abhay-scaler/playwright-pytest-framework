import logging

import pytest


@pytest.mark.ui
def test_console_error_and_page_error_are_logged(page, caplog):
    with caplog.at_level(logging.ERROR, logger="conftest"):
        page.goto(
            "data:text/html,<script>"
            "console.error('sentinel-console-error');"
            "throw new Error('sentinel-page-error');"
            "</script>"
        )

    messages = [record.message for record in caplog.records]
    assert any("sentinel-console-error" in m for m in messages)
    assert any("sentinel-page-error" in m for m in messages)


@pytest.mark.ui
def test_ordinary_console_messages_are_not_logged_as_errors(page, caplog):
    with caplog.at_level(logging.ERROR, logger="conftest"):
        page.goto("data:text/html,<script>console.log('sentinel-ordinary-log')</script>")

    messages = [record.message for record in caplog.records]
    assert not any("sentinel-ordinary-log" in m for m in messages)


@pytest.mark.ui
def test_console_and_page_error_listeners_do_not_fail_the_test(page):
    # The whole point of these listeners is passive observability - a console
    # error or an uncaught JS exception must never fail the test itself, and
    # the page must remain usable afterward.
    page.goto(
        "data:text/html,<script>"
        "console.error('does-not-fail-the-test');"
        "throw new Error('does-not-fail-the-test-either');"
        "</script>"
    )
    assert page.evaluate("1 + 1") == 2
