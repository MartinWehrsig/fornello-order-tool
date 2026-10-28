import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    config = json.loads(
        Path(__file__).with_name(".local").joinpath("connection.json").read_text(encoding="utf-8-sig")
    )
    base_url = config["baseUrl"]

    def call(method: str, path: str, body: bytes | None, key: str | None) -> tuple[int, bytes]:
        headers = {"Content-Type": "application/json"}
        if key is not None:
            headers["x-functions-key"] = key
        request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=90) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    status, body = call("GET", "/openapi.json", None, None)
    assert status == 200, f"OpenAPI HTTP status: {status}"
    spec = json.loads(body)
    assert spec["servers"] == [{"url": base_url}], "OpenAPI server URL differs from deployed endpoint"
    assert spec["paths"]["/orders"]["post"]["operationId"] == "submit_order"
    print("PASS: public OpenAPI with deployed server URL and submit_order operation")

    payload = {
        "confirmed": True,
        "items": [{
            "item_code": "P01", "size": "large", "quantity": 1,
            "extra_toppings": ["mushrooms"], "variant": "",
        }],
    }
    data = json.dumps(payload).encode("utf-8")
    for key in (None, "invalid-test-key"):
        status, _ = call("POST", "/orders", data, key)
        assert status == 401, f"Expected 401 without a valid API key, received {status}"
    print("PASS: missing and incorrect API keys rejected with HTTP 401")

    status, body = call("POST", "/orders", data, config["apiKey"])
    assert status == 200, f"Order failed: HTTP {status}, body={body!r}"
    result = json.loads(body)
    assert result["demo"] is True and result["status"] == "accepted_demo"
    assert result["total_eur"] == "12.40", f"Incorrect menu price: {result['total_eur']}"
    assert result["order_id"].startswith("DEMO-")
    print(f"PASS: confirmed demo order {result['order_id']} accepted for EUR 12.40")

    for changed in (
        {**payload, "confirmed": False},
        {**payload, "items": [{**payload["items"][0], "item_code": "P99"}]},
        {**payload, "items": [{**payload["items"][0], "quantity": 11}]},
    ):
        status, _ = call("POST", "/orders", json.dumps(changed).encode("utf-8"), config["apiKey"])
        assert status == 422, f"Expected HTTP 422 for invalid order, received {status}"
    print("PASS: missing confirmation, unknown menu item and >10 pizzas rejected with HTTP 422")
    status, _ = call("POST", "/orders", b"not-json", config["apiKey"])
    assert status == 400, f"Expected HTTP 400 for malformed JSON, received {status}"
    print("PASS: malformed JSON rejected with HTTP 400")


if __name__ == "__main__":
    main()
