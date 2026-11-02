# AI-Based Water Quality Monitoring & Pollution Prediction System

An end-to-end IoT and AI-driven environmental platform that monitors water bodies (rivers, lakes, municipal supply networks) in real time. It senses physical and chemical parameters, streams telemetry to the cloud/edge server, automatically detects pollution anomalies using **Isolation Forest**, forecasts 24-hour contamination trajectories using **Random Forest**, and visualizes insights on an interactive GIS dashboard.

---

## 🌟 Key Features

1. **Continuous Multi-Parameter Sensing**:
   - pH (0 – 14)
   - Turbidity (0 – 3000 NTU)
   - Dissolved Oxygen (DO in mg/L)
   - Water Temperature (°C via DS18B20)
   - Total Dissolved Solids (TDS in ppm)
2. **Automated Water Quality Index (WQI)**:
   - Uses the weighted arithmetic formula:
     $$\text{WQI} = \frac{\sum_{i=1}^{n} q_i w_i}{\sum_{i=1}^{n} w_i}$$
   - Maps to 4 health categories: **Good** ($\le 25$), **Moderate** ($26 - 50$), **Poor** ($51 - 75$), and **Critical** ($> 75$).
3. **AI Anomaly Detection**:
   - Real-time **Isolation Forest** flags sudden industrial discharges, acid dumps, or sewage contamination.
4. **24-Hour Pollution Forecasting**:
   - Multi-target **Random Forest Regressors** predict upcoming WQI, dissolved oxygen, and turbidity trajectories with confidence intervals.
5. **Interactive GIS Dashboard**:
   - Real-time **Leaflet map** of monitoring stations with animated risk markers.
   - Dynamic **Chart.js** telemetry graphs and 24-hour prediction trajectories.
   - WHO Potable Water Compliance radar analysis.
   - Ground-truth lab validation benchmark table (Tap water vs Natural Pond vs Industrial Contaminated Bucket Test).
   - Live automated threshold and anomaly alerts feed.
   - One-click CSV historical data report export.
   - Interactive anomaly simulation modal to test real-time alerting directly from the browser.
   - Bilingual support: **English & Bangla (বাংলা)** interface toggle.

---

## 🏗️ System Architecture

```
[ ESP32 Sensor Node ] ──(WiFi / HTTP POST JSON)──▶ [ FastAPI Server ]
  ├── pH Sensor (Pin 34)                                  │
  ├── Turbidity (Pin 35)                                  ├── SQLite Database (6 Tables)
  ├── TDS Sensor (Pin 32)                                 ├── Isolation Forest (Anomaly AI)
  ├── Dissolved Oxygen (Pin 33)                           ├── Random Forest (Forecaster AI)
  └── DS18B20 Temp (Pin 4)                                └── WQI Engine
                                                                  │
                                                     [ Interactive Dashboard ]
                                                      ├── Leaflet GIS Map
                                                      ├── Chart.js Visualizations
                                                      └── Real-time Alerts Feed
```

---

## 📁 Project Structure

```
Project Ai/
├── backend/
│   ├── main.py               # FastAPI entry point & lifespan
│   ├── database.py           # SQLAlchemy engine & session dependency
│   ├── models/
│   │   ├── database.py       # 6-table ORM schema (users, nodes, readings, predictions, alerts, locations)
│   │   └── schemas.py        # Pydantic validation schemas
│   ├── routes/
│   │   ├── readings.py       # Ingestion endpoint for ESP32 & queries
│   │   ├── nodes.py          # Station & GIS location management
│   │   ├── predictions.py    # AI forecasting & model status
│   │   ├── alerts.py         # Notifications & CSV export
│   │   └── dashboard.py      # Summary metrics & lab benchmarks
│   ├── ml/
│   │   └── engine.py         # Isolation Forest & Random Forest models
│   └── utils/
│       ├── wqi.py            # WQI calculation & WHO thresholds
│       └── seed_data.py      # Realistic monitoring stations & 5-day seed data
├── frontend/
│   ├── index.html            # Single-page web dashboard
│   ├── css/
│   │   └── style.css         # Glassmorphic dark design system
│   └── js/
│       └── app.js            # Leaflet map, Chart.js & API controller
├── data/                     # Database file & serialized ML models (.pkl)
├── simulator.py              # Hardware simulator to test without ESP32
├── water_quality_node.ino    # Arduino ESP32 firmware sketch
├── requirements.txt          # Python dependencies
├── .env                      # Configuration file
└── run.sh                    # One-command startup script
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.9+ installed (`python3 --version`)
- Arduino IDE (if deploying physical ESP32 hardware)

### 2. Launch the System (Automated)

Run the included startup script:
```bash
chmod +x run.sh
./run.sh
```

Or manually:
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run FastAPI server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to:
- **Interactive Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

*Note: On first launch, the database automatically seeds with 5 realistic monitoring stations (Buriganga, Turag, Dhanmondi Lake, Gulshan Lake, Shitalakshya) and 5 days of hourly readings, and automatically trains the baseline ML models!*

---

## 🧪 Testing with the IoT Node Simulator

You can test the entire platform without physical hardware using `simulator.py`:

```bash
source venv/bin/activate

# Continuously stream live readings from all 5 stations (every 10 seconds):
python3 simulator.py --interval 10 --anomaly-rate 0.1

# Or inject a specific pollution anomaly immediately:
python3 simulator.py --inject acid --node node-01
python3 simulator.py --inject sludge --node-02
```

You can also click the **"⚡ Simulate Event"** button directly on the web dashboard to trigger test anomalies and watch the alerts appear in real time!

---

## 🔌 Hardware Setup (ESP32 Node)

To deploy physical nodes using `water_quality_node.ino`:

### Pinout Mapping
| Sensor | ESP32 Pin | Voltage Range | Note |
|---|---|---|---|
| pH Sensor Analog Out | GPIO 34 (ADC1) | 0–3.3V via divider | 10k/20k voltage divider if 5V module |
| Turbidity Analog Out | GPIO 35 (ADC1) | 0–3.3V via divider | 10k/20k voltage divider if 5V module |
| TDS Analog Out | GPIO 32 (ADC1) | 0–3.3V | Direct connection |
| Dissolved Oxygen Out | GPIO 33 (ADC1) | 0–3.3V | Set `ENABLE_DO true` in sketch |
| DS18B20 Temperature | GPIO 4 | Digital 1-Wire | 4.7kΩ pull-up resistor to 3.3V |

### Arduino Configuration
1. Open `water_quality_node.ino` in Arduino IDE.
2. Install libraries:
   - `OneWire` (by Paul Stoffregen)
   - `DallasTemperature` (by Miles Burton)
3. Set your WiFi credentials in lines 23–26:
   ```cpp
   const char* WIFI_SSID  = "YOUR_WIFI_NAME";
   const char* WIFI_PASS  = "YOUR_WIFI_PASSWORD";
   const char* SERVER_URL = "http://YOUR_COMPUTER_IP:8000/api/readings";
   const char* API_KEY    = "CHANGE_ME";
   const char* NODE_ID    = "node-01";
   ```
4. Select Board: **"ESP32 Dev Module"**, connect via USB, and click **Upload**.

---

## 📊 Database Schema (6 Tables)

1. `users`: Authentication and access levels (`admin`, `authority`, `public`).
2. `locations`: Geographical coordinates, water body type (river, lake, pond, municipal supply).
3. `sensor_nodes`: Deployed hardware devices, status, last seen heartbeat.
4. `sensor_readings`: Raw measurements (pH, turbidity, DO, temp, TDS), calculated WQI, and anomaly flag.
5. `predictions`: AI-generated forecasted WQI, parameters, and confidence scores.
6. `alerts`: Threshold violations and ML anomaly events.

---

## 📈 Machine Learning Models

### 1. Anomaly Detection: Isolation Forest
- **Purpose**: Detects multi-dimensional pollution spikes without requiring labeled failure datasets.
- **Features**: Normalized $[ \text{pH}, \text{Turbidity}, \text{DO}, \text{Temperature}, \text{TDS} ]$.
- **Contamination**: Configured at $0.10$ with auto-recalibration.

### 2. Time-Series Forecasting: Random Forest Regressor
- **Purpose**: Projects water quality up to 24 hours in advance to alert authorities before ecological damage occurs.
- **Features**: Lagged historical observations ($t-1, \dots, t-6$), rolling means, standard deviations, and diurnal temporal features.
