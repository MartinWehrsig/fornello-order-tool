import json
import logging
from urllib.parse import urlsplit

import azure.functions as func

from orders import openapi_document, submit_order


app = func.FunctionApp()


@app.function_name(name="submit_order")
@app.route(route="orders", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def orders(req: func.HttpRequest) -> func.HttpResponse:
    if len(req.get_body()) > 32768:
        logging.warning("Rejected demo order: request exceeds 32 KiB.")
        return func.HttpResponse('{"error":"Request body exceeds 32 KiB."}', status_code=400,
                                 mimetype="application/json")
    try:
        payload = req.get_json()
    except ValueError:
        logging.warning("Rejected demo order: malformed JSON.")
        return func.HttpResponse('{"error":"Invalid JSON."}', status_code=400,
                                 mimetype="application/json")
    try:
        result = submit_order(payload)
    except ValueError as error:
        logging.warning("Rejected demo order: %s", error)
        return func.HttpResponse(json.dumps({"error": str(error)}), status_code=422,
                                 mimetype="application/json")
    logging.info("Accepted demo order %s.", result["order_id"])
    return func.HttpResponse(json.dumps(result), mimetype="application/json")


@app.function_name(name="openapi")
@app.route(route="openapi.json", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def openapi(req: func.HttpRequest) -> func.HttpResponse:
    document = openapi_document()
    url = urlsplit(req.url)
    document["servers"] = [{"url": f"{url.scheme}://{url.netloc}/api"}]
    return func.HttpResponse(json.dumps(document), mimetype="application/json")
