import pytest

from apps.sample_app.pages.sample_app_page import SampleAppPage
from pwpf.core.app_config import load_app_config


@pytest.mark.skip(
    reason="Manual check for failure-artifact capture (screenshot/trace/video) — "
    "fails on purpose. Remove the skip locally to verify capture, don't run in CI."
)
def test_failure_artifact(page):
    sample_page = SampleAppPage(page, load_app_config("sample_app"))
    sample_page.open()
    sample_page.enter_name("Ava")
    sample_page.submit()
    assert sample_page.message() == "Wrong message"
