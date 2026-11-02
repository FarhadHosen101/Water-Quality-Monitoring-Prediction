"""
ESP32 Node Hardware Simulator.
Simulates real ESP32 edge nodes sending telemetry over HTTP POST to the backend.
Can be run continuously or used to inject test pollution events.
"""

import time
import random
import math
import argparse
import json
import urllib.request
import urllib.error
import sys

API_URL = "http://127.0.0.1:8000/api/readings"
API_KEY = "CHANGE_ME"

NODES = [
    {"id": "node-01", "name": "Buriganga River", "base": {"ph": 6.8, "turb": 38.0, "do": 3.2, "temp": 28.5, "tds": 720.0}},
    {"id": "node-02", "name": "Turag River",     "base": {"ph": 7.1, "turb": 24.0, "do": 4.8, "temp": 27.8, "tds": 490.0}},
    {"id": "node-03", "name": "Dhanmondi Lake",  "base": {"ph": 7.5, "turb": 8.5,  "do": 6.9, "temp": 26.2, "tds": 240.0}},
    {"id": "node-04", "name": "Gulshan Lake",    "base": {"ph": 7.3, "turb": 14.0, "do": 5.5, "temp": 26.8, "tds": 360.0}},
    {"id": "node-05", "name": "Shitalakshya",   "base": {"ph": 6.4, "turb": 42.0, "do": 2.9, "temp": 29.1, "tds": 840.0}},
]


def send_reading(node_id, ph, turbidity, do_val, temp, tds, api_url=API_URL, api_key=API_KEY):
    payload = {
        "node_id": node_id,
        "ph": round(ph, 2),
        "turbidity": round(turbidity, 1),
        "do": round(do_val, 2),
        "temp": round(temp, 2),
        "tds": round(tds, 1)
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 201:
                res_data = json.loads(response.read().decode("utf-8"))
                anomaly_flag = "⚠️ ANOMALY!" if res_data.get("is_anomaly") else "✅ Normal"
                print(f"[{node_id}] WQI: {res_data.get('wqi'):.1f} ({res_data.get('risk_level')}) | pH={payload['ph']}, Turb={payload['turbidity']} NTU, DO={payload['do']} mg/L, TDS={payload['tds']} ppm | {anomaly_flag}")
                return True
            else:
                print(f"[{node_id}] Server returned status: {response.status}")
                return False
    except urllib.error.HTTPError as e:
        print(f"[{node_id}] HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[{node_id}] Connection error: {e}")
        return False


def run_simulation(interval=10, anomaly_chance=0.1, api_url=API_URL):
    print(f"🌊 Starting Water Quality IoT Node Simulator")
    print(f"📡 Target API: {api_url}")
    print(f"⏱️ Interval: {interval} seconds | Anomaly chance: {anomaly_chance * 100}%")
    print("Press Ctrl+C to stop.\n" + "-" * 60)

    step = 0
    while True:
        step += 1
        hour = (time.localtime().tm_hour + step / 10.0) % 24
        temp_cycle = math.sin((hour - 8) * math.pi / 12) * 2.5
        do_cycle = math.sin((hour - 10) * math.pi / 12) * 1.0

        for node in NODES:
            base = node["base"]
            ph = base["ph"] + random.uniform(-0.1, 0.1)
            turb = max(1.0, base["turb"] + random.uniform(-2.0, 2.0))
            do_val = max(0.5, base["do"] + do_cycle + random.uniform(-0.2, 0.2))
            temp = base["temp"] + temp_cycle + random.uniform(-0.3, 0.3)
            tds = max(50.0, base["tds"] + random.uniform(-15.0, 15.0))

            # Trigger synthetic contamination anomaly
            if random.random() < anomaly_chance:
                event = random.choice(["acid_spill", "turbidity_spike", "organic_depletion"])
                if event == "acid_spill":
                    ph = random.uniform(4.2, 5.4)
                    print(f"🚨 INJECTING ANOMALY: Acid discharge event at {node['id']}")
                elif event == "turbidity_spike":
                    turb = random.uniform(110.0, 240.0)
                    tds *= 1.8
                    print(f"🚨 INJECTING ANOMALY: Silt/Industrial runoff at {node['id']}")
                elif event == "organic_depletion":
                    do_val = random.uniform(0.6, 1.8)
                    tds = random.uniform(1100.0, 1500.0)
                    print(f"🚨 INJECTING ANOMALY: Severe DO depletion event at {node['id']}")

            send_reading(node["id"], ph, turb, do_val, temp, tds, api_url=api_url)
            time.sleep(1)  # small gap between nodes

        time.sleep(interval)


def inject_anomaly_command(node_id, anomaly_type, api_url=API_URL):
    print(f"Injecting single {anomaly_type} event into {node_id}...")
    if anomaly_type == "acid":
        send_reading(node_id, ph=4.3, turbidity=35.0, do_val=4.0, temp=29.0, tds=780.0, api_url=api_url)
    elif anomaly_type == "sludge":
        send_reading(node_id, ph=7.2, turbidity=195.0, do_val=1.2, temp=31.5, tds=1450.0, api_url=api_url)
    elif anomaly_type == "alkaline":
        send_reading(node_id, ph=9.8, turbidity=45.0, do_val=3.5, temp=28.0, tds=920.0, api_url=api_url)
    else:
        print("Unknown anomaly type. Choose from: acid, sludge, alkaline")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Water Quality IoT Node Simulator")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between reading rounds")
    parser.add_argument("--anomaly-rate", type=float, default=0.1, help="Chance of anomaly (0.0 to 1.0)")
    parser.add_argument("--url", type=str, default=API_URL, help="API readings endpoint URL")
    parser.add_argument("--inject", choices=["acid", "sludge", "alkaline"], help="Inject immediate anomaly")
    parser.add_argument("--node", type=str, default="node-01", help="Target node for injection")

    args = parser.parse_args()

    if args.inject:
        inject_anomaly_command(args.node, args.inject, api_url=args.url)
    else:
        try:
            run_simulation(interval=args.interval, anomaly_chance=args.anomaly_rate, api_url=args.url)
        except KeyboardInterrupt:
            print("\nSimulator stopped.")
            sys.exit(0)
