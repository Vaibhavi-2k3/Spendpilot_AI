import json

import httpx
import pytest

from app.providers.gemini_provider import GeminiError, GeminiProvider
from app.schemas.intelligence import GroundedComparison, ShoppingIntent
from app.services.shopping_intelligence import validate_grounding


INTENT = {
    "search_query": "noise cancelling headphones", "use_case": "commuting",
    "preferences": ["noise cancellation"],
}


def response_for(output):
    return {
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps(output)}]},
        }],
    }


@pytest.fixture
def mock_http(monkeypatch):
    original_client = httpx.Client

    def install(handler):
        def client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr("app.providers.gemini_provider.httpx.Client", client)

    return install


def test_intent_uses_structured_json_and_header_authentication(mock_http):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response_for(INTENT))

    mock_http(handler)
    provider = GeminiProvider("private-test-key", "gemini-3.8-flash")
    intent = provider.understand_intent("headphones for my commute", 5000, "INR")

    assert intent == ShoppingIntent.model_validate(INTENT)
    request = requests[0]
    assert request.headers["x-goog-api-key"] == "private-test-key"
    assert "private-test-key" not in str(request.url)
    body = json.loads(request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    schema = body["generationConfig"]["responseJsonSchema"]
    assert schema["additionalProperties"] is False
    assert "budget_amount" not in schema["properties"]
    context = json.loads(body["contents"][0]["parts"][0]["text"])
    assert context["budget_amount"] == 5000
    assert context["currency"] == "INR"


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_http_failures_do_not_expose_raw_errors_or_keys(mock_http, status):
    mock_http(lambda request: httpx.Response(
        status, json={"error": "private-test-key and internal details"},
    ))
    with pytest.raises(GeminiError) as exc:
        GeminiProvider("private-test-key", "gemini-3.8-flash").understand_intent(
            "headphones", 100, "USD",
        )
    assert "private-test-key" not in str(exc.value)
    assert "internal details" not in str(exc.value)


@pytest.mark.parametrize(
    "payload",
    [
        {}, [], {"candidates": []}, {"candidates": ["invalid"]},
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": [{"finishReason": "MAX_TOKENS"}]},
        response_for({**INTENT, "budget_amount": 999999}),
        response_for({**INTENT, "search_query": "   "}),
        response_for({**INTENT, "preferences": ["x"] * 9}),
    ],
)
def test_malformed_or_constraint_overriding_output_is_rejected(mock_http, payload):
    mock_http(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(GeminiError):
        GeminiProvider("test-key", "gemini-3.8-flash").understand_intent(
            "headphones", 100, "USD",
        )


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError])
def test_network_failures_are_safe(mock_http, exception):
    def handler(request):
        raise exception("private-test-key", request=request)

    mock_http(handler)
    with pytest.raises(GeminiError) as exc:
        GeminiProvider("private-test-key", "gemini-3.8-flash").understand_intent(
            "headphones", 100, "USD",
        )
    assert "private-test-key" not in str(exc.value)


def test_invalid_json_is_rejected(mock_http):
    mock_http(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(GeminiError):
        GeminiProvider("test-key", "gemini-3.8-flash").understand_intent(
            "headphones", 100, "USD",
        )


def grounded_report():
    return GroundedComparison.model_validate({
        "summary": "The listing explicitly mentions noise cancellation.",
        "recommended_product_id": "p1",
        "products": [{
            "product_id": "p1", "explanation": "Matches noise cancellation.",
            "evidence": [{"field": "description", "quote": "Noise cancellation"}],
        }],
    })


def test_comparison_uses_real_product_ids_and_verbatim_evidence(mock_http):
    context = {"products": [{
        "product_id": "p1", "name": "Headphones",
        "description": "Noise cancellation for commuting",
    }]}
    mock_http(lambda request: httpx.Response(
        200, json=response_for(grounded_report().model_dump()),
    ))
    report = GeminiProvider("test-key", "gemini-3.8-flash").compare(context)
    validate_grounding(report, context)
    assert report.recommended_product_id == "p1"


@pytest.mark.parametrize("field,value", [("price", "0.01"), ("checkout_eligible", True)])
def test_model_cannot_add_catalog_control_fields(mock_http, field, value):
    output = grounded_report().model_dump()
    output["products"][0][field] = value
    mock_http(lambda request: httpx.Response(200, json=response_for(output)))

    with pytest.raises(GeminiError):
        GeminiProvider("test-key", "gemini-3.8-flash").compare({"products": []})


@pytest.mark.parametrize(
    "change",
    ["unknown_product", "unknown_pick", "duplicate_product", "fabricated_quote", "wrong_field"],
)
def test_ungrounded_comparisons_are_rejected(change):
    report = grounded_report()
    if change == "unknown_product":
        report.products[0].product_id = "invented"
    elif change == "unknown_pick":
        report.recommended_product_id = "invented"
    elif change == "duplicate_product":
        report.products.append(report.products[0])
    elif change == "fabricated_quote":
        report.products[0].evidence[0].quote = "48-hour battery"
    else:
        report.products[0].evidence[0].field = "name"

    with pytest.raises(GeminiError):
        validate_grounding(report, {"products": [{
            "product_id": "p1", "name": "Headphones",
            "description": "Noise cancellation",
        }]})
