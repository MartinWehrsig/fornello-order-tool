import json
import unittest
from pathlib import Path

import azure.functions as func

from function_app import openapi, orders
from orders import PIZZAS, STANDARD_ITEMS, VARIANTS, openapi_document, submit_order


def item(code="P01", size="large", quantity=1, extras=None, variant=""):
    return {
        "item_code": code, "size": size, "quantity": quantity,
        "extra_toppings": extras or [], "variant": variant,
    }


class OrderTests(unittest.TestCase):
    def test_exact_pizza_and_topping_prices(self):
        result = submit_order({"confirmed": True, "items": [
            item(quantity=2, extras=["mushrooms", "burrata"]),
            item("G01", "standard", variant="Coca-Cola Zero"),
        ]})
        self.assertEqual(result["total_eur"], "33.30")
        self.assertEqual(result["items"][0]["unit_price_eur"], "15.40")
        self.assertTrue(result["demo"])
        self.assertIn("keine echte Bestellung", result["message"])
        self.assertIn("2 x Margherita", result["message"])

    def test_every_menu_code_and_pizza_size_is_supported(self):
        for code, (_, prices) in PIZZAS.items():
            for size, price in zip(("small", "large", "family"), prices):
                result = submit_order({"confirmed": True, "items": [item(code, size)]})
                self.assertEqual(result["total_eur"], f"{price / 100:.2f}")
        for code, (_, price) in STANDARD_ITEMS.items():
            variant = VARIANTS[code][0] if code in VARIANTS else ""
            result = submit_order({"confirmed": True, "items": [
                item(code, "standard", variant=variant),
            ]})
            self.assertEqual(result["total_eur"], f"{price / 100:.2f}")
        self.assertEqual(len(PIZZAS) + len(STANDARD_ITEMS), 39)

    def test_invalid_orders_are_rejected(self):
        invalid = [
            {"confirmed": False, "items": [item()]},
            {"confirmed": True, "items": []},
            {"confirmed": True, "items": [item("P99")]},
            {"confirmed": True, "items": [item(quantity=True)]},
            {"confirmed": True, "items": [item(quantity=0)]},
            {"confirmed": True, "items": [item(quantity=11)]},
            {"confirmed": True, "items": [item("P15", "large")]},
            {"confirmed": True, "items": [item("S01", "standard", extras=["ham"])]},
            {"confirmed": True, "items": [item(extras=["ham"] * 2)]},
            {"confirmed": True, "items": [item(extras=["unknown"])]},
            {"confirmed": True, "items": [item("G01", "standard", variant="unknown")]},
            {"confirmed": True, "items": [item()], "delivery_address": "not supported"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                submit_order(payload)

    def test_schema_snapshot_matches_implementation(self):
        saved = json.loads(Path(__file__).with_name("openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, openapi_document())
        self.assertEqual(saved["paths"]["/orders"]["post"]["operationId"], "submit_order")

    def test_http_validation_and_openapi_server(self):
        response = orders(func.HttpRequest(method="POST", url="https://example.test/api/orders",
                                          body=b'{"confirmed":false,"items":[]}'))
        self.assertEqual(response.status_code, 422)
        response = orders(func.HttpRequest(method="POST", url="https://example.test/api/orders",
                                          body=b'not-json'))
        self.assertEqual(response.status_code, 400)
        response = openapi(func.HttpRequest(method="GET", url="https://example.test/api/openapi.json",
                                           body=b""))
        self.assertEqual(json.loads(response.get_body())["servers"],
                         [{"url": "https://example.test/api"}])


if __name__ == "__main__":
    unittest.main()
