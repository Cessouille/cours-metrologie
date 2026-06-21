import urllib.request
import urllib.error
import time
import random
import argparse
import json

def send_request(url, method='GET', data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        json_data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
        req.data = json_data
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            req_id = response.headers.get('X-Request-ID', 'N/A')
            return response.getcode(), response.read().decode('utf-8'), req_id
    except urllib.error.HTTPError as e:
        req_id = e.headers.get('X-Request-ID', 'N/A')
        return e.code, e.reason, req_id
    except Exception as e:
        return 0, str(e), 'N/A'

def run_traffic(base_url, mode, duration_sec):
    print(f"Starting ELK TP Traffic Generator in '{mode}' mode targeting {base_url}...")
    print("Press Ctrl+C to stop.\n")
    start_time = time.time()
    
    while True:
        if duration_sec and (time.time() - start_time) > duration_sec:
            print(f"Completed requested duration of {duration_sec} seconds. Exiting.")
            break
            
        try:
            if mode == 'normal':
                # Normal mode: 75% 200, 15% 404, 10% 500
                rand = random.random()
                if rand < 0.50:
                    code, body, req_id = send_request(f"{base_url}/")
                    print(f"[Normal] GET / -> {code} | Request-ID: {req_id}")
                elif rand < 0.75:
                    code, body, req_id = send_request(f"{base_url}/api/data")
                    print(f"[Normal] GET /api/data -> {code} | Request-ID: {req_id}")
                elif rand < 0.90:
                    code, body, req_id = send_request(f"{base_url}/api/not-found")
                    print(f"[Normal] GET /api/not-found -> {code} | Request-ID: {req_id}")
                else:
                    code, body, req_id = send_request(f"{base_url}/api/error")
                    print(f"[Normal] GET /api/error -> {code} | Request-ID: {req_id}")
                
                # Intermittent queue backlog oscillation (30% chance)
                if random.random() < 0.3:
                    if random.random() < 0.5:
                        code, body, req_id = send_request(f"{base_url}/api/queue/add", method='POST')
                        print(f"[Normal] POST /api/queue/add -> {code} | Request-ID: {req_id} | Body: {body.strip()}")
                    else:
                        code, body, req_id = send_request(f"{base_url}/api/queue/process", method='POST')
                        print(f"[Normal] POST /api/queue/process -> {code} | Request-ID: {req_id} | Body: {body.strip()}")
                        
            elif mode == 'high-errors':
                # High errors mode: heavy 5xx errors
                rand = random.random()
                if rand < 0.80:
                    code, body, req_id = send_request(f"{base_url}/api/error")
                    print(f"[High-Errors] GET /api/error -> {code} | Request-ID: {req_id}")
                else:
                    code, body, req_id = send_request(f"{base_url}/")
                    print(f"[High-Errors] GET / -> {code} | Request-ID: {req_id}")
                    
            elif mode == 'client-errors':
                # High client errors mode: heavy 4xx errors
                code, body, req_id = send_request(f"{base_url}/api/not-found")
                print(f"[Client-Errors] GET /api/not-found -> {code} | Request-ID: {req_id}")
                
            elif mode == 'high-backlog':
                # High backlog mode: constant queue addition
                code, body, req_id = send_request(f"{base_url}/api/queue/add", method='POST')
                print(f"[High-Backlog] POST /api/queue/add -> {code} | Request-ID: {req_id} | Body: {body.strip()}")
                
            elif mode == 'clear-backlog':
                # Clear backlog mode: constant processing to empty the queue
                code, body, req_id = send_request(f"{base_url}/api/queue/process", method='POST')
                print(f"[Clear-Backlog] POST /api/queue/process -> {code} | Request-ID: {req_id} | Body: {body.strip()}")
                
            else:
                print(f"Unknown mode: {mode}")
                break
                
            time.sleep(random.uniform(0.1, 0.5))
            
        except KeyboardInterrupt:
            print("\nTraffic generator stopped by user.")
            break
        except Exception as e:
            print(f"Error during execution: {e}")
            time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ELK Stack TP traffic generator")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the application")
    parser.add_argument("--mode", default="normal", choices=["normal", "high-errors", "client-errors", "high-backlog", "clear-backlog"], help="Traffic pattern mode")
    parser.add_argument("--duration", type=int, default=0, help="Duration in seconds (0 for infinite)")
    
    args = parser.parse_args()
    run_traffic(args.url, args.mode, args.duration)
