import json
from pathlib import Path
from uuid import uuid4


PIZZAS = {
    "P01": ("Margherita", (850, 1090, 2190)),
    "P02": ("Marinara", (750, 950, 1890)),
    "P03": ("Salame", (990, 1250, 2490)),
    "P04": ("Prosciutto e Funghi", (1050, 1350, 2690)),
    "P05": ("Quattro Formaggi", (1150, 1450, 2890)),
    "P06": ("Diavola", (1150, 1450, 2890)),
    "P07": ("Tonno", (1090, 1390, 2750)),
    "P08": ("Vegetariana", (1090, 1390, 2750)),
    "P09": ("Hawaii", (1050, 1350, 2690)),
    "P10": ("Capricciosa", (1150, 1450, 2890)),
    "P11": ("Parma e Rucola", (1290, 1590, 3190)),
    "P12": ("Pollo BBQ", (1190, 1490, 2950)),
    "P13": ("Verde Vegana", (1150, 1450, 2890)),
    "P14": ("Frutti di Mare", (1390, 1690, 3390)),
}
STANDARD_ITEMS = {
    "P15": ("Calzone Classico", 1250),
    "S01": ("Garlic Bread", 490),
    "S02": ("Bruschetta", 590),
    "S03": ("Mozzarella Sticks", 650),
    "S04": ("Chicken Wings", 890),
    "S05": ("Insalata Mista", 690),
    "S06": ("Caprese", 850),
    "S07": ("Caesar Salad", 1090),
    "N01": ("Spaghetti Bolognese", 1090),
    "N02": ("Penne Arrabbiata", 950),
    "N03": ("Tagliatelle Carbonara", 1150),
    "N04": ("Lasagne al Forno", 1190),
    "N05": ("Gnocchi Sorrentina", 1050),
    "D01": ("Tiramisu", 550),
    "D02": ("Panna Cotta", 490),
    "D03": ("Pizza Dolce", 890),
    "D04": ("Gelato", 390),
    "G01": ("Soft drink 0.33 l", 250),
    "G02": ("Soft drink 1.0 l", 390),
    "G03": ("Water 0.5 l", 290),
    "G04": ("Water 1.0 l", 390),
    "G05": ("House lemonade 0.5 l", 450),
    "G06": ("Peroni beer 0.33 l (18+)", 350),
    "G07": ("Augustiner beer 0.5 l (18+)", 390),
    "G08": ("House wine 0.75 l (18+)", 1690),
}
TOPPING_GROUPS = (
    (("mushrooms", "onion", "peppers", "olives", "spinach", "jalapenos",
      "sweetcorn", "rocket"), (100, 150, 250)),
    (("mozzarella", "gorgonzola", "parmesan", "vegan_cheese"), (120, 180, 300)),
    (("ham", "salami", "chicken", "tuna", "anchovies"), (150, 200, 350)),
    (("parma_ham", "buffalo_mozzarella", "prawns", "burrata"), (250, 300, 500)),
)
TOPPINGS = {
    name: prices for names, prices in TOPPING_GROUPS for name in names
}
SIZES = ("small", "large", "family")
SIZE_LABELS = {
    "small": "Small 26 cm",
    "large": "Large 32 cm",
    "family": "Family 45 x 33 cm",
    "standard": "Einheitsgroesse",
}


def request_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["confirmed", "items"],
        "properties": {
            "confirmed": {
                "type": "boolean",
                "enum": [True],
                "description": "True only after the user explicitly confirms this exact demo order.",
            },
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["item_code", "size", "quantity", "extra_toppings", "variant"],
                    "properties": {
                        "item_code": {
                            "type": "string",
                            "enum": list(PIZZAS) + list(STANDARD_ITEMS),
                            "description": "Exact item code from the Pizzeria Fornello menu.",
                        },
                        "size": {
                            "type": "string",
                            "enum": [*SIZES, "standard"],
                            "description": "P01-P14: small/large/family. P15 and all other items: standard.",
                        },
                        "quantity": {"type": "integer", "minimum": 1, "maximum": 20},
                        "extra_toppings": {
                            "type": "array",
                            "maxItems": 5,
                            "uniqueItems": True,
                            "items": {"type": "string", "enum": list(TOPPINGS)},
                            "description": "Extra pizza toppings for P01-P14 only; [] otherwise. No replacements.",
                        },
                        "variant": {
                            "type": "string",
                            "maxLength": 80,
                            "description": "For drinks, wings, gelato or salad: selected menu flavour/type/sauce/dressing; otherwise empty string.",
                        },
                    },
                },
            },
        },
    }


VARIANTS = {
    "S04": ("BBQ", "hot"),
    "S05": ("house", "balsamic", "yoghurt-herb", "Caesar"),
    "S07": ("house", "balsamic", "yoghurt-herb", "Caesar"),
    "D04": ("vanilla", "chocolate", "pistachio", "lemon sorbet"),
    "G01": ("Coca-Cola", "Coca-Cola Zero", "Fanta", "Sprite"),
    "G02": ("Coca-Cola", "Coca-Cola Zero", "Fanta", "Sprite"),
    "G03": ("sparkling", "still"),
    "G04": ("sparkling", "still"),
    "G05": ("lemon-mint", "blood orange"),
    "G08": ("red", "white"),
}


def submit_order(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"confirmed", "items"}:
        raise ValueError("Provide only confirmed and items. This API supports demo pickup orders only.")
    if payload["confirmed"] is not True:
        raise ValueError("An explicit user confirmation is required before submitting.")
    items = payload["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise ValueError("An order must contain between 1 and 20 line items.")
    priced_items = []
    total = 0
    pizza_count = 0
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "item_code", "size", "quantity", "extra_toppings", "variant"
        }:
            raise ValueError("Each item needs item_code, size, quantity, extra_toppings and variant only.")
        code, size, quantity = item["item_code"], item["size"], item["quantity"]
        extras, variant = item["extra_toppings"], item["variant"]
        if not isinstance(code, str) or code not in PIZZAS.keys() | STANDARD_ITEMS.keys():
            raise ValueError("Unknown menu item_code.")
        if type(quantity) is not int or not 1 <= quantity <= 20:
            raise ValueError("quantity must be an integer between 1 and 20.")
        if not isinstance(extras, list) or len(extras) > 5:
            raise ValueError("At most five extra toppings are allowed per pizza.")
        if any(not isinstance(extra, str) or extra not in TOPPINGS for extra in extras):
            raise ValueError("Unknown extra topping; use only the documented topping codes.")
        if len(set(extras)) != len(extras):
            raise ValueError("Duplicate extra toppings are not supported.")
        if not isinstance(variant, str) or len(variant) > 80:
            raise ValueError("variant must be a string of at most 80 characters.")
        allowed_variants = VARIANTS.get(code)
        if allowed_variants and variant not in allowed_variants:
            raise ValueError(f"{code}: variant must be one of {', '.join(allowed_variants)}.")
        if not allowed_variants and variant != "":
            raise ValueError(f"{code}: variant must be empty.")
        if code in PIZZAS:
            if size not in SIZES:
                raise ValueError(f"{code}: choose small, large or family.")
            name, prices = PIZZAS[code]
            size_index = SIZES.index(size)
            unit_price = prices[size_index] + sum(TOPPINGS[extra][size_index] for extra in extras)
            pizza_count += quantity
        else:
            if size != "standard" or extras:
                raise ValueError(f"{code}: only standard size and no extra toppings are supported.")
            name, unit_price = STANDARD_ITEMS[code]
            if code == "P15":
                pizza_count += quantity
        if pizza_count > 10:
            raise ValueError("More than 10 pizzas require 24 hours' notice and a direct phone call per the menu.")
        line_total = unit_price * quantity
        total += line_total
        priced_items.append({
            "item_code": code, "name": name, "size": size, "quantity": quantity,
            "extra_toppings": extras, "variant": variant,
            "unit_price_eur": f"{unit_price // 100}.{unit_price % 100:02d}",
            "line_total_eur": f"{line_total // 100}.{line_total % 100:02d}",
        })
    summary = "; ".join(
        f"{item['quantity']} x {item['name']} ({SIZE_LABELS[item['size']]})"
        + (f" + {', '.join(item['extra_toppings'])}" if item["extra_toppings"] else "")
        + (f" [{item['variant']}]" if item["variant"] else "")
        for item in priced_items
    )
    return {
        "demo": True,
        "order_id": f"DEMO-{uuid4().hex[:12].upper()}",
        "status": "accepted_demo",
        "message": f"Demo-Bestellung von {summary} ist eingegangen und wird simuliert vorbereitet. "
                   "Sie steht in der Demo bald zur Abholung bereit. Es wurde keine echte Bestellung aufgegeben.",
        "fulfillment": "pickup",
        "items": priced_items,
        "total_eur": f"{total // 100}.{total % 100:02d}",
        "currency": "EUR",
        "promotions_applied": False,
        "notice": "Hackathon-Simulation ohne Speicherung, Zahlung oder echte Restaurantanbindung. "
                  "Keine Rabatte, Lieferung, Sonderboeden, Ersetzungen oder Half-and-half. "
                  "Die Kueche verarbeitet alle 14 Allergene; Spuren koennen nicht ausgeschlossen werden.",
    }


def openapi_document() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Pizzeria Fornello Demo Orders",
            "version": "1.0.0",
            "description": "Shared hackathon API. Simulated pickup orders only; no real preparation, storage or payments.",
        },
        "servers": [{"url": "https://YOUR-FUNCTION-APP.azurewebsites.net/api"}],
        "paths": {
            "/orders": {
                "post": {
                    "operationId": "submit_order",
                    "summary": "Submit a confirmed demo pickup order",
                    "description": "Call only after explicit user confirmation of exact items, sizes, quantities, extras and price. "
                                   "Use menu codes, not names. P01-P14 support small/large/family and up to five extra toppings. "
                                   "P15 and all other dishes use standard with no extras. At most ten pizzas. "
                                   "No delivery, discounts, replacement cheese, special dough or half-and-half. "
                                   "Variant choices: " + json.dumps(VARIANTS) + ". All other variants must be empty.",
                    "security": [{"function_key": []}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": request_schema()}},
                    },
                    "responses": {
                        "200": {
                            "description": "Simulated order accepted; never a real restaurant order.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "demo": {"type": "boolean"},
                                            "order_id": {"type": "string"},
                                            "status": {"type": "string"},
                                            "message": {"type": "string"},
                                            "total_eur": {"type": "string"},
                                            "currency": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                        "400": {"description": "Malformed JSON or request too large."},
                        "401": {"description": "Missing or invalid x-functions-key."},
                        "422": {"description": "Unsupported menu item, size, topping, quantity or confirmation."},
                    },
                },
            },
        },
        "components": {
            "securitySchemes": {
                "function_key": {"type": "apiKey", "in": "header", "name": "x-functions-key"},
            },
        },
    }


if __name__ == "__main__":
    Path(__file__).with_name("openapi.json").write_text(
        json.dumps(openapi_document(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
