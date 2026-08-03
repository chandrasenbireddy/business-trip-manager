"""Unit tests for browser-use AgentHistoryList → list[dict] parsing."""

from types import SimpleNamespace

from scrapers.browser_results import listings_from_browser_result


def test_listings_from_plain_list():
    assert listings_from_browser_result([{"listing_id": "a"}]) == [{"listing_id": "a"}]


def test_listings_from_final_result_json_array():
    history = SimpleNamespace(
        final_result=lambda: '[{"listing_id": "abc", "lat": 1.0, "lng": 2.0}]',
        extracted_content=lambda: [],
    )
    assert listings_from_browser_result(history) == [{"listing_id": "abc", "lat": 1.0, "lng": 2.0}]


def test_listings_from_markdown_fenced_json():
    history = SimpleNamespace(
        final_result=lambda: 'Here you go:\n```json\n[{"price": 120, "airline": "SV"}]\n```',
        extracted_content=lambda: [],
    )
    assert listings_from_browser_result(history) == [{"price": 120, "airline": "SV"}]


def test_listings_from_wrapped_object_key():
    history = SimpleNamespace(
        final_result=lambda: '{"listings": [{"listing_id": "x"}]}',
        extracted_content=lambda: [],
    )
    assert listings_from_browser_result(history) == [{"listing_id": "x"}]


def test_string_result_no_longer_iterated_as_chars():
    """Regression: iterating a final_result str caused TypeError on listing['lat']."""
    history = SimpleNamespace(
        final_result=lambda: '[{"listing_id": "abc", "lat": 24.7, "lng": 46.6}]',
        extracted_content=lambda: [],
    )
    listings = listings_from_browser_result(history)
    assert listings[0]["lat"] == 24.7
