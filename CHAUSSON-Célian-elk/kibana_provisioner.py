import urllib.request
import json
import time

def create_data_view(kibana_url, title, name, time_field):
    url = f"{kibana_url}/api/data_views/data_view"
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true"
    }
    payload = {
        "data_view": {
            "title": title,
            "name": name,
            "timeFieldName": time_field
        }
    }
    
    req = urllib.request.Request(url, method="POST", headers=headers, data=json.dumps(payload).encode("utf-8"))
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Successfully created Data View: {name} (Title: {title})")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        if "already exists" in body or e.code == 409:
            print(f"Data View already exists: {name}")
            return True
        else:
            print(f"Failed to create Data View {name}: {e.code} - {e.reason}")
            print(f"Error details: {body}")
            return False
    except Exception as e:
        print(f"Error connecting to Kibana: {e}")
        return False

def wait_for_kibana(kibana_url, timeout_sec=120):
    print("Waiting for Kibana to be ready...")
    start_time = time.time()
    while True:
        try:
            req = urllib.request.Request(f"{kibana_url}/api/status")
            with urllib.request.urlopen(req) as response:
                body = json.loads(response.read().decode("utf-8"))
                if body.get("status", {}).get("overall", {}).get("level") == "available":
                    print("Kibana is available!")
                    return True
        except Exception:
            pass
            
        if time.time() - start_time > timeout_sec:
            print("Timeout waiting for Kibana.")
            return False
        time.sleep(5)

if __name__ == "__main__":
    kibana_url = "http://localhost:5601"
    if wait_for_kibana(kibana_url):
        create_data_view(kibana_url, "app-logs-*", "app-logs-*", "@timestamp")
        create_data_view(kibana_url, "air-quality-data", "air-quality-*", "@timestamp")
