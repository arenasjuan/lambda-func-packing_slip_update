import json
import base64
import requests
import config
from config import SKU_REPLACEMENTS as SKU_REPLACEMENTS

auth_string = f"{config.SHIPSTATION_API_KEY}:{config.SHIPSTATION_API_SECRET}"
encoded_auth_string = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')


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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_auth_string}"
        }
        
        try:
            order_response = requests.get(resource_url, headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from resource_url: {e}")
            response["statusCode"] = 500
            response["body"] = json.dumps({"error": "Error fetching data from resource_url"})
        else:
            if order_response.status_code == 200:
                order_data = order_response.json()
                if "orders" in order_data:
                    orders = order_data["orders"]
                    print("Processing orders")
                    for order in orders:
                        process_order(order)

                    update_order(orders)  # Call the update_order function after processing all orders
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



def get_orders_by_order_number(order_number):
    url = "https://ssapi.shipstation.com/orders"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth_string}"
    }
    params = {
        "orderNumber": order_number
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        orders = response.json()["orders"]
        # Sort orders by the creation date in descending order
        sorted_orders = sorted(orders, key=lambda x: x['createDate'], reverse=True)
        return sorted_orders
    else:
        print(f"Error fetching orders: {response.content}")
        return None



def process_order(order):
    print("Processing individual order")

    for item in order["items"]:
        original_sku = item["sku"]
        if original_sku in SKU_REPLACEMENTS:
            if isLawnPlan(original_sku):
                order_number = order["orderNumber"]
                url_mlp = f"https://user-api-dev-qhw6i22s2q-uc.a.run.app/order?shopify_order_no={order_number}"
                response_mlp = requests.get(url_mlp)
                print("Sending request to:", url_mlp)
                print("Response status code from MLP API:", response_mlp.status_code)
                data_mlp = response_mlp.json()
                plan_details = data_mlp.get("plan_details", [])

                item['name'] = SKU_REPLACEMENTS[original_sku]
                
                for plan in plan_details:
                    products = plan.get("products", [])
                    print("Products count:", len(products))
                    print("Products:", products)
                    
                    # Iterate through products and append the formatted string
                    for product in products:
                        product_count = product.get("count", 0)
                        product_name = product.get("name", "")
                        item['name'] += f"\n\u00A0\u00A0\u00A0\u00A0• {product_count} {product_name}"

            else:
                replacement_name = SKU_REPLACEMENTS[original_sku]
                item["name"] = replacement_name

    print("Finished processing individual order")


def update_order(orders):
    print("Updating orders")
    url = "https://ssapi.shipstation.com/orders/createorder"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth_string}"
    }
    for order in orders:
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
