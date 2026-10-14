import pytest

from core.api_client import api_request_context


@pytest.mark.api
def test_json_placeholder_posts():
    with api_request_context(base_url="https://jsonplaceholder.typicode.com") as api:
        response = api.get("/posts/1")
        assert response.ok
        payload = response.json()
        assert payload["id"] == 1


@pytest.mark.api
def test_json_placeholder_nonexistent_post_returns_404():
    # api_request_context is a thin passthrough to Playwright's own
    # APIRequestContext, which does not raise on a non-2xx response - the
    # negative contract to verify is on the response object itself, not an
    # exception.
    with api_request_context(base_url="https://jsonplaceholder.typicode.com") as api:
        response = api.get("/posts/999999")
        assert not response.ok
        assert response.status == 404
