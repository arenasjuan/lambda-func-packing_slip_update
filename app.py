import json
import base64
import requests
import config
from config import SKU_REPLACEMENTS as SKU_REPLACEMENTS
from concurrent.futures import ThreadPoolExecutor

auth_string = f"{config.SHIPSTATION_API_KEY}:{config.SHIPSTATION_API_SECRET}"
encoded_auth_string = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')


headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {encoded_auth_string}"
}

mlp_data = {}  # Define as a global variable

def lambda_handler(event, context):
    response = {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Webhook received and processed"}),
    }

    payload = json.loads(event["body"])

    if "resource_url" in payload:
        resource_url = payload["resource_url"]
        print(f"Fetching data from resource_url: {resource_url}")

        try:
            order_response = requests.get(resource_url, headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from resource_url: {e}")
            response["statusCode"] = 500
            response["body"] = json.dumps({"error": "Error fetching data from resource_url"})
        else:
            if order_response.status_code == 200:
                order_data = order_response.json()
                print(order_data)
                if "orders" in order_data:
                    order = order_data["orders"][0]
                    print("Processing order")

                    has_lawn_plan = any(isLawnPlan(item["sku"]) for item in order["items"])
                    if has_lawn_plan:
                        print("This order has a lawn plan")
                        url_mlp = f"https://user-api-dev-qhw6i22s2q-uc.a.run.app/order?shopify_order_no={order['orderNumber']}"
                        response_mlp = requests.get(url_mlp)
                        data_mlp = response_mlp.json()
                        plan_details = data_mlp.get("plan_details", [])
                        for detail in plan_details:
                            for product in detail['products']:
                                mlp_data[detail['sku']] = {
                                    'name': product['name'],
                                    'count': product['count']
                                }
                        print(mlp_data[detail['sku']])
                    process_items_and_update_order(order)
                        
                else:
                    print("No orders key found in order_data")
                    print(f"Order data: {order_data}")
                    response["statusCode"] = 400
                    response["body"] = json.dumps({"error": "No 'orders' key found in order data"})
            else:
                print(f"Error fetching data from resource_url: {order_response.status_code}")
                response["statusCode"] = 500
                response["body"] = json.dumps({"error": "Error fetching data from resource_url"})
    else:
        print("No resource_url found in payload")
        print(f"Payload: {payload}")
        response["statusCode"] = 400
        response["body"] = json.dumps({"error": "No 'resource_url' key found in webhook payload"})

    return response




def isLawnPlan(sku):
    return (sku.startswith('SUB') or sku in ['05000', '10000', '15000']) and sku not in ["SUB - LG - D", "SUB - LG - S", "SUB - LG - G"]

def get_plan_details_from_url_mlp(order_number):
    url_mlp = f"https://user-api-dev-qhw6i22s2q-uc.a.run.app/order?shopify_order_no={order_number}"
    response_mlp = requests.get(url_mlp)
    print("Sending request to:", url_mlp)
    print("Response status code from MLP API:", response_mlp.status_code)
    data_mlp = response_mlp.json()
    plan_details = data_mlp.get("plan_details", [])
    return plan_details


def process_item(item):
    global mlp_data 
    print("Processing individual item")
    original_sku = item["sku"]
    if original_sku in SKU_REPLACEMENTS:
        if isLawnPlan(original_sku) and original_sku in mlp_data:
            product_info = mlp_data[original_sku]
            item['name'] = SKU_REPLACEMENTS[original_sku] + f"\n\u00A0\u00A0\u00A0\u00A0• {product_info['count']} {product_info['name']}"
        else:
            replacement_name = SKU_REPLACEMENTS[original_sku]
            item["name"] = replacement_name

    print("Finished processing individual item")

def process_items_and_update_order(order):
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Process items concurrently
        executor.map(process_item, order["items"])
    update_order(order)


def update_order(order):
    print("Updating order")
    url = "https://ssapi.shipstation.com/orders/createorder"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth_string}"
    }
    print(json.dumps(order))
    try:
        response = requests.post(url, headers=headers, data=json.dumps(order))
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating order {order['orderNumber']} in Shipstation: {e}")
    else:
        if response.status_code != 200:
            print(f"Failed to update order {order['orderNumber']} in Shipstation: {response.content}")
        else:
            print(f"Successfully updated order {order['orderNumber']} in Shipstation")