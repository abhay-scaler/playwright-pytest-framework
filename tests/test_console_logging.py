"""Browser console errors and uncaught page errors reach the framework's log.

The listeners are passive observability (`pwpf/plugin.py`): an `error`-level
console message or an uncaught page exception is logged and nothing else -
never a failed test, never a changed page.

Reading these assertions needs one fact about how the capture works. The
framework's loggers do not propagate (`pwpf/utils/logger.py`), so their records
never reach the root logger where `caplog` installs its handler. They are
captured anyway because pytest attaches that handler to every *already
existing* non-propagating logger when it sets up a test
(`_pytest/logging.py`, "Attach to all non-propagating loggers"), and
`pwpf.plugin`'s logger exists from the moment the plugin is imported. The gap
pytest documents in the same breath - a logger that becomes non-propagating
later is missed - is why the tests below asserted on their own capture rather
than taking it for granted.

Three things follow, all deliberate:

- `caplog.at_level` names the framework's logger, taken from the module rather
  than written out, so it cannot drift again. It used to say `"conftest"`,
  which stopped existing when the plugin moved out of the root conftest.py:
  harmless, because the capture never depended on it, and misleading for
  exactly as long as it stood.
- The negative test asserts a *presence* alongside the absence. An assertion
  that something was not logged passes just as happily when nothing was
  captured at all, so it is paired with a sentinel that must be there. The
  version this replaces had no such control, and its page emitted no error at
  all: it was asserting the absence of a message in an empty capture.
- The pages are built with `set_content` rather than a `data:` URI. The logged
  line includes the page URL, and a data: URI quotes the whole script back -
  so `"sentinel" in message` was true for a sentinel the listener had never
  logged, merely because it appeared in the address.

Those two faults compounded, and the measurement that settles it: with the
console listener commented out of `pwpf/plugin.py`, the previous version of this
file **passed all three of its tests** - the page-error record quoted the
missing sentinel back inside the URL, and the absence assertion held over an
empty capture. The version below fails three of four. That, rather than the
stale logger name, was the real defect here.
"""

import logging

import pytest

from pwpf import plugin

FRAMEWORK_LOGGER = plugin.LOGGER.name


def _framework_errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The messages the framework's own logger emitted at ERROR, and only those.

    Filtering by logger name and level is what makes these tests fail when the
    capture breaks: a record from somewhere else, or no record at all, is not
    evidence that the listeners did their job.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == FRAMEWORK_LOGGER and record.levelno == logging.ERROR
    ]


@pytest.mark.ui
def test_console_error_and_page_error_are_logged(page, caplog):
    with caplog.at_level(logging.ERROR, logger=FRAMEWORK_LOGGER):
        page.set_content(
            "<script>"
            "console.error('sentinel-console-error');"
            "throw new Error('sentinel-page-error');"
            "</script>"
        )

    messages = _framework_errors(caplog)
    assert messages, f"nothing was captured from {FRAMEWORK_LOGGER} at ERROR"
    assert any("sentinel-console-error" in m for m in messages)
    assert any("sentinel-page-error" in m for m in messages)


@pytest.mark.ui
def test_ordinary_console_messages_are_not_logged_as_errors(page, caplog):
    """`console.log` is not an error. The console.error in the same page is the
    control: without it, "the ordinary message was not logged" would also hold
    for a run that captured nothing."""
    with caplog.at_level(logging.ERROR, logger=FRAMEWORK_LOGGER):
        page.set_content(
            "<script>"
            "console.log('sentinel-ordinary-log');"
            "console.error('sentinel-real-error');"
            "</script>"
        )

    messages = _framework_errors(caplog)
    assert any("sentinel-real-error" in m for m in messages), (
        f"the control error was not captured from {FRAMEWORK_LOGGER}, so this test "
        "cannot tell silence apart from correct filtering"
    )
    assert not any("sentinel-ordinary-log" in m for m in messages)


@pytest.mark.ui
def test_the_logged_record_comes_from_the_framework_logger_at_error_level(page, caplog):
    """The capture contract itself, so a change in logger name, propagation or
    level shows up here instead of quietly emptying the assertions above."""
    with caplog.at_level(logging.ERROR, logger=FRAMEWORK_LOGGER):
        page.set_content("<script>console.error('sentinel-record-shape')</script>")

    matching = [
        record for record in caplog.records if "sentinel-record-shape" in record.getMessage()
    ]
    assert matching, f"no record carried the sentinel; captured: {[r.name for r in caplog.records]}"
    assert [r.name for r in matching] == [FRAMEWORK_LOGGER] * len(matching)
    assert all(r.levelno == logging.ERROR for r in matching)
    assert plugin.LOGGER.propagate is False, (
        "the framework's loggers are deliberately isolated from the root logger; "
        "if that changed, these tests capture through a different route than they document"
    )


@pytest.mark.ui
def test_console_and_page_error_listeners_do_not_fail_the_test(page):
    # The whole point of these listeners is passive observability - a console
    # error or an uncaught JS exception must never fail the test itself, and
    # the page must remain usable afterward.
    page.set_content(
        "<script>"
        "console.error('does-not-fail-the-test');"
        "throw new Error('does-not-fail-the-test-either');"
        "</script>"
    )
    assert page.evaluate("1 + 1") == 2
