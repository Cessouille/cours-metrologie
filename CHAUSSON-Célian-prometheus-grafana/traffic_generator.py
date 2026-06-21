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
            return response.getcode(), response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.reason
    except Exception as e:
        return 0, str(e)

def run_traffic(base_url, mode, duration_sec):
    print(f"Starting traffic generator in '{mode}' mode targeting {base_url}...")
    start_time = time.time()
    
    while True:
        if duration_sec and (time.time() - start_time) > duration_sec:
            print(f"Completed requested duration of {duration_sec} seconds. Exiting.")
            break
            
        try:
            if mode == 'normal':
                # Normal mode: mostly 2xx (80%), some 4xx (15%), few 5xx (5%)
                # Backlog size oscillates
                rand = random.random()
                if rand < 0.50:
                    code, body = send_request(f"{base_url}/")
                    print(f"[Normal] GET / -> {code}")
                elif rand < 0.80:
                    code, body = send_request(f"{base_url}/api/data")
                    print(f"[Normal] GET /api/data -> {code}")
                elif rand < 0.95:
                    code, body = send_request(f"{base_url}/api/not-found")
                    print(f"[Normal] GET /api/not-found -> {code}")
                else:
                    code, body = send_request(f"{base_url}/api/error")
                    print(f"[Normal] GET /api/error -> {code}")
                
                # Keep backlog oscillating between 0 and 30
                if random.random() < 0.3:
                    if random.random() < 0.5:
                        code, body = send_request(f"{base_url}/api/queue/add", method='POST')
                        print(f"[Normal] POST /api/queue/add -> {code}")
                    else:
                        code, body = send_request(f"{base_url}/api/queue/process", method='POST')
                        print(f"[Normal] POST /api/queue/process -> {code}")
                        
            elif mode == 'high-errors':
                # High errors mode: heavy 5xx errors to trigger Alert 2
                rand = random.random()
                if rand < 0.80:
                    code, body = send_request(f"{base_url}/api/error")
                    print(f"[High-Errors] GET /api/error -> {code}")
                else:
                    code, body = send_request(f"{base_url}/")
                    print(f"[High-Errors] GET / -> {code}")
                    
            elif mode == 'high-backlog':
                # High backlog mode: constant queue addition to trigger Alert 4
                code, body = send_request(f"{base_url}/api/queue/add", method='POST')
                print(f"[High-Backlog] POST /api/queue/add -> {code}")
                
            elif mode == 'clear-backlog':
                # Clear backlog mode: constant processing to clear queue backlog
                code, body = send_request(f"{base_url}/api/queue/process", method='POST')
                print(f"[Clear-Backlog] POST /api/queue/process -> {code}")
                
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
    parser = argparse.ArgumentParser(description="Prometheus TP demo application")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the demo application")
    parser.add_argument("--mode", default="normal", choices=["normal", "high-errors", "high-backlog", "clear-backlog"], help="Traffic mode")
    parser.add_argument("--duration", type=int, default=0, help="Duration of traffic generation in seconds (0 for infinite)")
    
    args = parser.parse_args()
    run_traffic(args.url, args.mode, args.duration)
