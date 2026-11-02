/**
 * AI-Based Water Quality Monitoring & Pollution Prediction System
 * Frontend Application Controller
 */

// ── State Management ──────────────────────────────────────────────
const state = {
  activeNodeId: "node-01",
  nodes: [],
  locations: [],
  selectedHours: 24,
  map: null,
  markers: {},
  charts: {
    trends: null,
    forecast: null,
    radar: null
  },
  lang: "en", // "en" | "bn"
  autoRefreshInterval: null,
  lastTimestamps: {}
};

// ── Translations Dictionary (Bangla & English) ───────────────────
const i18n = {
  en: {
    title: "AquaAI",
    subtitle: "AI Water Quality & Pollution Prediction",
    live_badge: "LIVE TELEMETRY",
    kpi_avg_wqi: "System Water Quality Index",
    kpi_active_nodes: "Active Stations",
    kpi_anomalies: "AI Anomalies (24h)",
    kpi_alerts: "Active Alerts",
    map_title: "Water Bodies & IoT Stations Map",
    station_details: "Station Real-Time Telemetry",
    trends_title: "Multi-Parameter Time Series Analysis",
    forecast_title: "24-Hour AI Pollution Forecast (Random Forest)",
    standards_title: "WHO Compliance Radar",
    lab_title: "Lab Ground-Truth Benchmarks (Bucket Test Validation)",
    alerts_title: "Real-time Alerts & Notifications",
    export_btn: "Export CSV",
    sim_btn: "Simulate Anomaly",
    btn_predict: "Run AI Forecast"
  },
  bn: {
    title: "অ্যাকুয়া-এআই",
    subtitle: "কৃত্রিম বুদ্ধিমত্তা ভিত্তিক পানি পর্যবেক্ষণ ও পূর্বাভাস",
    live_badge: "লাইভ টেলিমეტ্রি",
    kpi_avg_wqi: "গড় পানি গুণমান সূচক (WQI)",
    kpi_active_nodes: "সক্রিয় পর্যবেক্ষণ কেন্দ্র",
    kpi_anomalies: "এআই শনাক্তকৃত ত্রুটি (২৪ ঘণ্টা)",
    kpi_alerts: "সতর্কবার্তা",
    map_title: "জলাশয় ও আইওটি নোড ম্যাপ",
    station_details: "লাইভ সেন্সর পরিমাপ",
    trends_title: "পানির গুণমানের পরিবর্তনশীল চার্ট",
    forecast_title: "২৪-ঘণ্টার এআই পূর্বাভাস (র‍্যান্ডম ফরেস্ট)",
    standards_title: "ডব্লিউএইচও মানদণ্ড রাডার",
    lab_title: "ল্যাব নমুনা ও ফিল্ড ভ্যালিডেশন (বাকেট টেস্ট)",
    alerts_title: "জরুরি সতর্কবার্তা ও নোটিফিকেশন",
    export_btn: "সিএসভি ডাউনলোড",
    sim_btn: "ত্রুটি সিমুলেট করুন",
    btn_predict: "পূর্বাভাস দেখুন"
  }
};

// ── Color Helpers ────────────────────────────────────────────────
function getRiskColor(riskLevel) {
  switch (riskLevel) {
    case "Good": return "#10b981";
    case "Moderate": return "#f59e0b";
    case "Poor": return "#f97316";
    case "Critical": return "#ef4444";
    default: return "#3b82f6";
  }
}

function getRiskBadgeClass(riskLevel) {
  switch (riskLevel) {
    case "Good": return "badge-good";
    case "Moderate": return "badge-moderate";
    case "Poor": return "badge-poor";
    case "Critical": return "badge-critical";
    default: return "badge-good";
  }
}

// ── App Initialization ───────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initMap();
  initEventListeners();
  await loadDashboardData();
  await loadLabBenchmarks();

  // Auto-refresh telemetry every 8 seconds
  state.autoRefreshInterval = setInterval(async () => {
    await refreshTelemetry();
  }, 8000);
});

// ── Leaflet GIS Map ──────────────────────────────────────────────
function initMap() {
  // Center around Dhaka waterways
  state.map = L.map("map", {
    zoomControl: true,
    attributionControl: false
  }).setView([23.755, 90.395], 11);

  // Free Dark Canvas tiles (Esri Dark Gray - 100% Free, No API Key Required)
  const darkCanvas = L.layerGroup([
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16,
      attribution: "Tiles &copy; Esri"
    }),
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16
    })
  ]);

  // OpenStreetMap standard tiles
  const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  });

  // Default to Dark Canvas
  darkCanvas.addTo(state.map);

  // Layer control for easy switching between Dark and Street map
  L.control.layers({
    "🌙 Dark Mode": darkCanvas,
    "🗺️ Street Map": osm
  }, null, { position: "topright" }).addTo(state.map);
}

function updateMapMarkers(markersData) {
  markersData.forEach(item => {
    if (!item.lat || !item.lng) return;

    const color = getRiskColor(item.risk_level);
    const pulseRing = item.is_anomaly
      ? `<div style="position:absolute; width:34px; height:34px; border:2px solid #ef4444; border-radius:50%; animation:pulseAnimation 1.5s infinite; top:-7px; left:-7px;"></div>`
      : "";

    const customIcon = L.divIcon({
      className: "custom-map-marker",
      html: `
        <div style="position:relative; width:20px; height:20px;">
          ${pulseRing}
          <div style="width:20px; height:20px; background-color:${color}; border:2px solid #ffffff; border-radius:50%; box-shadow:0 0 12px ${color};"></div>
        </div>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    const popupContent = `
      <div style="font-family:'Plus Jakarta Sans',sans-serif; color:#0f172a; padding:4px;">
        <h4 style="margin:0 0 4px; font-size:14px; font-weight:700;">${item.name}</h4>
        <p style="margin:0 0 6px; font-size:11px; color:#64748b;">📍 ${item.location_name} (${item.water_body_type})</p>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span style="font-size:12px; font-weight:600;">WQI Index:</span>
          <span style="font-size:13px; font-weight:800; color:${color};">${item.wqi ? item.wqi.toFixed(1) : "N/A"} (${item.risk_level})</span>
        </div>
        <button onclick="selectStation('${item.node_id}')" style="width:100%; background:#06b6d4; color:#fff; border:none; padding:6px 10px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;">
          Select Station
        </button>
      </div>
    `;

    if (state.markers[item.node_id]) {
      state.markers[item.node_id].setLatLng([item.lat, item.lng]);
      state.markers[item.node_id].setIcon(customIcon);
      state.markers[item.node_id].setPopupContent(popupContent);
    } else {
      const marker = L.marker([item.lat, item.lng], { icon: customIcon })
        .addTo(state.map)
        .bindPopup(popupContent);

      marker.on("click", () => selectStation(item.node_id));
      state.markers[item.node_id] = marker;
    }
  });
}

// ── Data Loading & API Calls ─────────────────────────────────────
async function loadDashboardData() {
  try {
    // 1. Fetch top KPIs
    const statsRes = await fetch("/api/dashboard/stats");
    const stats = await statsRes.json();
    renderKpis(stats);

    // 2. Fetch Map Markers
    const markersRes = await fetch("/api/dashboard/map-markers");
    const markers = await markersRes.json();
    updateMapMarkers(markers);

    // 3. Fetch Node list for dropdown
    const nodesRes = await fetch("/api/nodes");
    state.nodes = await nodesRes.json();
    populateNodeSelect(state.nodes);

    // 4. Load initial station details & charts
    await updateStationView(state.activeNodeId);

    // 5. Load Alerts
    await loadAlerts();

  } catch (err) {
    console.error("Error loading dashboard data:", err);
  }
}

async function refreshTelemetry() {
  try {
    const [statsRes, markersRes, nodesRes] = await Promise.all([
      fetch("/api/dashboard/stats"),
      fetch("/api/dashboard/map-markers"),
      fetch("/api/nodes")
    ]);
    const stats = await statsRes.json();
    renderKpis(stats);

    const markers = await markersRes.json();
    updateMapMarkers(markers);

    state.nodes = await nodesRes.json();

    // Check if new data has arrived for active node
    const activeNode = state.nodes.find(n => n.id === state.activeNodeId);
    const newTs = activeNode?.latest_reading?.timestamp;
    const oldTs = state.lastTimestamps ? state.lastTimestamps[state.activeNodeId] : null;
    const dataChanged = newTs && newTs !== oldTs;
    if (dataChanged && state.lastTimestamps) {
      state.lastTimestamps[state.activeNodeId] = newTs;
    }

    await updateStationView(state.activeNodeId, dataChanged);
    await loadAlerts();
  } catch (err) {
    console.error("Telemetry refresh tick failed:", err);
  }
}

function renderKpis(stats) {
  const avgWqiEl = document.getElementById("kpi-avg-wqi");
  if (avgWqiEl) {
    avgWqiEl.textContent = stats.avg_wqi ? stats.avg_wqi.toFixed(1) : "--";
    const statusSubEl = document.getElementById("kpi-avg-wqi-sub");
    if (statusSubEl) {
      let risk = "Good";
      if (stats.avg_wqi > 75) risk = "Critical";
      else if (stats.avg_wqi > 50) risk = "Poor";
      else if (stats.avg_wqi > 25) risk = "Moderate";
      statusSubEl.textContent = `Overall Status: ${risk}`;
      statusSubEl.className = `kpi-subtext status-${risk.toLowerCase()}`;
    }
  }

  const activeNodesEl = document.getElementById("kpi-active-nodes");
  if (activeNodesEl) {
    activeNodesEl.textContent = `${stats.active_nodes} / ${stats.total_nodes}`;
  }

  const anomaliesEl = document.getElementById("kpi-anomalies");
  if (anomaliesEl) {
    anomaliesEl.textContent = stats.anomalies_today;
  }

  const alertsEl = document.getElementById("kpi-unread-alerts");
  if (alertsEl) {
    alertsEl.textContent = stats.unread_alerts;
  }
}

function populateNodeSelect(nodes) {
  const select = document.getElementById("station-select");
  if (!select) return;

  select.innerHTML = "";
  nodes.forEach(n => {
    const opt = document.createElement("option");
    opt.value = n.id;
    opt.textContent = `${n.name} (${n.location_name})`;
    if (n.id === state.activeNodeId) opt.selected = true;
    select.appendChild(opt);
  });
}

window.selectStation = function(nodeId) {
  state.activeNodeId = nodeId;
  const select = document.getElementById("station-select");
  if (select) select.value = nodeId;
  updateStationView(nodeId);

  // Pan map to selected node
  const node = state.nodes.find(n => n.id === nodeId);
  if (node && node.latitude && node.longitude && state.map) {
    state.map.flyTo([node.latitude, node.longitude], 13, { duration: 1.2 });
  }
};

async function updateStationView(nodeId, redrawCharts = true) {
  const node = state.nodes.find(n => n.id === nodeId);
  if (!node) return;

  // Render Telemetry meters
  const r = node.latest_reading || {};
  document.getElementById("meter-ph").textContent = r.ph ? r.ph.toFixed(2) : "--";
  document.getElementById("meter-turb").textContent = r.turbidity ? r.turbidity.toFixed(1) : "--";
  document.getElementById("meter-do").textContent = r.dissolved_oxygen ? r.dissolved_oxygen.toFixed(2) : "--";
  document.getElementById("meter-temp").textContent = r.temperature ? r.temperature.toFixed(1) : "--";
  document.getElementById("meter-tds").textContent = r.tds ? r.tds.toFixed(0) : "--";

  // WQI Hero Box
  const wqiVal = node.latest_wqi;
  const risk = node.latest_risk || "Good";
  const wqiScoreEl = document.getElementById("station-wqi-score");
  if (wqiScoreEl) {
    wqiScoreEl.textContent = wqiVal ? wqiVal.toFixed(1) : "--";
    wqiScoreEl.style.color = getRiskColor(risk);
  }

  const badgeEl = document.getElementById("station-risk-badge");
  if (badgeEl) {
    badgeEl.textContent = risk;
    badgeEl.className = `badge-risk ${getRiskBadgeClass(risk)}`;
  }

  const statusEl = document.getElementById("station-status-text");
  if (statusEl) {
    statusEl.textContent = `Station: ${node.name} • Location: ${node.location_name} (${node.water_body_type})`;
  }

  // Update progress bars (percent of max standard limit)
  setBarWidth("bar-ph", r.ph ? (r.ph / 14.0) * 100 : 50);
  setBarWidth("bar-turb", r.turbidity ? Math.min(100, (r.turbidity / 50.0) * 100) : 20);
  setBarWidth("bar-do", r.dissolved_oxygen ? Math.min(100, (r.dissolved_oxygen / 14.0) * 100) : 60);
  setBarWidth("bar-temp", r.temperature ? (r.temperature / 40.0) * 100 : 60);
  setBarWidth("bar-tds", r.tds ? Math.min(100, (r.tds / 1000.0) * 100) : 30);

  renderRadarChart(r);

  if (redrawCharts) {
    await renderTrendsChart(nodeId, state.selectedHours);
    await renderForecastChart(nodeId);
  }
}

function setBarWidth(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = `${Math.max(5, Math.min(100, pct))}%`;
}

// ── Chart.js Visualizations ──────────────────────────────────────
async function renderTrendsChart(nodeId, hours = 24) {
  const ctx = document.getElementById("trendsChart");
  if (!ctx) return;

  try {
    const res = await fetch(`/api/readings?node_id=${nodeId}&hours=${hours}&limit=300`);
    const data = await res.json();
    data.reverse(); // Chronological order

    const labels = data.map(d => {
      const t = new Date(d.timestamp);
      return `${t.getHours().toString().padStart(2, "0")}:${t.getMinutes().toString().padStart(2, "0")}`;
    });

    const phData = data.map(d => d.ph);
    const turbData = data.map(d => d.turbidity);
    const doData = data.map(d => d.dissolved_oxygen);
    const tdsData = data.map(d => d.tds);
    const wqiData = data.map(d => d.wqi);

    if (state.charts.trends) {
      state.charts.trends.destroy();
    }

    state.charts.trends = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "WQI Score",
            data: wqiData,
            borderColor: "#06b6d4",
            backgroundColor: "rgba(6, 182, 212, 0.08)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            yAxisID: "y"
          },
          {
            label: "pH Level",
            data: phData,
            borderColor: "#10b981",
            borderWidth: 2,
            tension: 0.35,
            yAxisID: "y1"
          },
          {
            label: "Dissolved Oxygen (mg/L)",
            data: doData,
            borderColor: "#3b82f6",
            borderWidth: 2,
            tension: 0.35,
            yAxisID: "y1"
          },
          {
            label: "Turbidity (NTU)",
            data: turbData,
            borderColor: "#f59e0b",
            borderWidth: 1.5,
            borderDash: [4, 4],
            yAxisID: "y"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#94a3b8", font: { size: 11, family: "Plus Jakarta Sans" } }
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            titleColor: "#f8fafc",
            bodyColor: "#cbd5e1",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#64748b", maxTicksLimit: 12 }
          },
          y: {
            type: "linear",
            position: "left",
            title: { display: true, text: "WQI / Turbidity", color: "#64748b" },
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#64748b" }
          },
          y1: {
            type: "linear",
            position: "right",
            title: { display: true, text: "pH / DO (mg/L)", color: "#64748b" },
            grid: { drawOnChartArea: false },
            ticks: { color: "#64748b" }
          }
        }
      }
    });

  } catch (err) {
    console.error("Trends chart render error:", err);
  }
}

async function renderForecastChart(nodeId) {
  const ctx = document.getElementById("forecastChart");
  if (!ctx) return;

  try {
    const res = await fetch(`/api/predictions/timeline/${nodeId}`);
    const data = await res.json();
    const timeline = data.timeline || [];

    const labels = timeline.map(t => `+${t.hour_offset}h`);
    const wqiForecast = timeline.map(t => t.predicted_wqi);
    const confidence = timeline.map(t => t.confidence * 100);

    if (state.charts.forecast) {
      state.charts.forecast.destroy();
    }

    state.charts.forecast = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Predicted WQI",
            data: wqiForecast,
            borderColor: "#8b5cf6",
            backgroundColor: "rgba(139, 92, 246, 0.15)",
            borderWidth: 3,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: "#8b5cf6",
            pointRadius: 5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#94a3b8", font: { size: 11, family: "Plus Jakarta Sans" } }
          },
          tooltip: {
            callbacks: {
              afterLabel: function(ctx) {
                const item = timeline[ctx.dataIndex];
                return `Risk: ${item.risk_level}\nAI Confidence: ${(item.confidence * 100).toFixed(0)}%`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#64748b" }
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#64748b" },
            title: { display: true, text: "Water Quality Index", color: "#64748b" }
          }
        }
      }
    });

  } catch (err) {
    console.error("Forecast chart error:", err);
  }
}

function renderRadarChart(reading) {
  const ctx = document.getElementById("radarChart");
  if (!ctx) return;

  const currentPhNorm = reading.ph ? (reading.ph / 14) * 100 : 50;
  const currentTurbNorm = reading.turbidity ? (reading.turbidity / 50) * 100 : 20;
  const currentDoNorm = reading.dissolved_oxygen ? (reading.dissolved_oxygen / 14) * 100 : 50;
  const currentTempNorm = reading.temperature ? (reading.temperature / 40) * 100 : 50;
  const currentTdsNorm = reading.tds ? (reading.tds / 1000) * 100 : 25;

  if (state.charts.radar) {
    state.charts.radar.destroy();
  }

  state.charts.radar = new Chart(ctx, {
    type: "radar",
    data: {
      labels: ["pH Balance", "Turbidity Clarity", "Dissolved Oxygen", "Temperature", "TDS Mineral Load"],
      datasets: [
        {
          label: "Current Sensor Reading",
          data: [currentPhNorm, currentTurbNorm, currentDoNorm, currentTempNorm, currentTdsNorm],
          backgroundColor: "rgba(6, 182, 212, 0.25)",
          borderColor: "#06b6d4",
          borderWidth: 2,
          pointBackgroundColor: "#06b6d4"
        },
        {
          label: "WHO Potable Benchmark",
          data: [50, 10, 70, 55, 30],
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          borderColor: "#10b981",
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointBackgroundColor: "#10b981"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: "rgba(255, 255, 255, 0.08)" },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          pointLabels: { color: "#94a3b8", font: { size: 10, family: "Plus Jakarta Sans" } },
          ticks: { display: false, max: 100, min: 0 }
        }
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94a3b8", font: { size: 10 } }
        }
      }
    }
  });
}

// ── Alerts Feed ──────────────────────────────────────────────────
async function loadAlerts() {
  const container = document.getElementById("alerts-container");
  if (!container) return;

  try {
    const res = await fetch("/api/alerts?limit=100");
    const alerts = await res.json();

    if (alerts.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:2rem; color:#64748b;">No active alerts. All monitoring stations normal.</div>`;
      return;
    }

    container.innerHTML = "";
    alerts.forEach(a => {
      const timeStr = new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const item = document.createElement("div");
      item.className = `alert-item ${a.severity.toLowerCase()}`;
      item.innerHTML = `
        <div class="alert-content">
          <div class="alert-top">
            <span class="alert-node">Station: ${a.node_id}</span>
            <span class="alert-time">${timeStr}</span>
          </div>
          <div class="alert-msg">${a.message}</div>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error("Alerts load error:", err);
  }
}

// ── Lab Validation Benchmarks (Bucket Test) ──────────────────────
async function loadLabBenchmarks() {
  const tbody = document.getElementById("lab-benchmarks-tbody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/dashboard/lab-benchmark");
    const data = await res.json();

    tbody.innerHTML = "";
    data.samples.forEach(s => {
      const color = getRiskColor(s.risk_level);
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><strong>${s.name}</strong><br><small style="color:#64748b;">${s.description}</small></td>
        <td>${s.ph.toFixed(1)}</td>
        <td>${s.turbidity.toFixed(1)} NTU</td>
        <td>${s.dissolved_oxygen.toFixed(1)} mg/L</td>
        <td>${s.tds.toFixed(0)} ppm</td>
        <td><strong style="color:${color};">${s.wqi.toFixed(1)}</strong> (${s.risk_level})</td>
        <td>${s.safe_drinking ? "✅ Potable" : s.safe_aquatic ? "⚠️ Aquatic Only" : "❌ Dangerous"}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error("Lab benchmark fetch error:", err);
  }
}

// ── Interactive Controls & Modals ────────────────────────────────
function initEventListeners() {
  // Station select dropdown
  const select = document.getElementById("station-select");
  if (select) {
    select.addEventListener("change", (e) => {
      selectStation(e.target.value);
    });
  }

  // Time range filter buttons
  document.querySelectorAll(".pill-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".pill-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      state.selectedHours = parseInt(e.target.dataset.hours, 10);
      renderTrendsChart(state.activeNodeId, state.selectedHours);
    });
  });

  // Export CSV
  const exportBtn = document.getElementById("btn-export-csv");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      window.location.href = `/api/alerts/export/csv?node_id=${state.activeNodeId}&days=7`;
    });
  }

  // Clear / Mark All Alerts Read
  const markAllBtn = document.getElementById("btn-mark-all-read");
  if (markAllBtn) {
    markAllBtn.addEventListener("click", async () => {
      markAllBtn.textContent = "Clearing...";
      try {
        await fetch("/api/alerts/mark-all-read", { method: "PUT" });
        await refreshTelemetry();
      } catch (err) {
        console.error(err);
      } finally {
        markAllBtn.textContent = "✓ Clear / Mark Read";
      }
    });
  }

  // Simulation Modal toggles
  const simBtn = document.getElementById("btn-open-sim");
  const modal = document.getElementById("sim-modal");
  const closeBtn = document.getElementById("modal-close-btn");

  if (simBtn && modal) {
    simBtn.addEventListener("click", () => modal.classList.add("active"));
  }
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
  }
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("active");
    });
  }

  // Trigger Anomaly simulation buttons inside modal
  document.querySelectorAll(".btn-sim-action").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const type = e.target.dataset.type;
      const targetNode = state.activeNodeId;
      try {
        const res = await fetch(`/api/simulate/anomaly/${targetNode}?anomaly_type=${type}`, { method: "POST" });
        const result = await res.json();
        alert(`⚡ ${result.message}\nCheck the live alert feed and charts!`);
        modal.classList.remove("active");
        await refreshTelemetry();
      } catch (err) {
        alert("Failed to inject simulation event.");
      }
    });
  });

  // Manual Forecast Trigger
  const forecastBtn = document.getElementById("btn-run-forecast");
  if (forecastBtn) {
    forecastBtn.addEventListener("click", async () => {
      forecastBtn.textContent = "Forecasting...";
      try {
        await fetch(`/api/predictions/forecast/${state.activeNodeId}`, { method: "POST" });
        await renderForecastChart(state.activeNodeId);
      } catch (err) {
        console.error(err);
      } finally {
        forecastBtn.textContent = i18n[state.lang].btn_predict;
      }
    });
  }

  // Language toggle (Bangla / English)
  const langBtn = document.getElementById("btn-toggle-lang");
  if (langBtn) {
    langBtn.addEventListener("click", () => {
      state.lang = state.lang === "en" ? "bn" : "en";
      langBtn.textContent = state.lang === "en" ? "বাং" : "EN";
      applyTranslations();
    });
  }
}

function applyTranslations() {
  const dict = i18n[state.lang];
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (dict[key]) el.textContent = dict[key];
  });
}
