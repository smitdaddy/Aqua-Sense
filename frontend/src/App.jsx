import { useEffect, useState } from "react";
import {
  Activity,
  Droplets,
  Thermometer,
  Gauge,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Waves,
  Brain,
  TrendingUp,
  TrendingDown,
  Clock,
  Database,
} from "lucide-react";

import { getLatestPrediction, getReadingHistory, getStats } from "./api";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import "./App.css";

const DEVICE_ID = "device-01";
const REFRESH_INTERVAL = 3000;

function formatTime(value) {
  if (!value) return "--";

  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDate(value) {
  if (!value) return "--";

  return new Date(value).toLocaleString();
}

function MetricCard({ title, value, unit, icon: Icon, color, subtitle }) {
  return (
    <div className="metric-card">
      <div className="metric-card-top">
        <span className="metric-title">{title}</span>

        <div className="metric-icon" style={{ color }}>
          <Icon size={20} />
        </div>
      </div>

      <div className="metric-value">
        {value ?? "--"}
        <span className="metric-unit">{unit}</span>
      </div>

      <div className="metric-subtitle">{subtitle}</div>
    </div>
  );
}

function DriverCard({ driver }) {
  const positive = driver.impact >= 0;

  return (
    <div className="driver-card">
      <div className="driver-top">
        <div>
          <div className="driver-name">{driver.name || driver.feature}</div>

          <div className="driver-feature">{driver.feature}</div>
        </div>

        <div
          className={`driver-direction ${positive ? "positive" : "negative"}`}
        >
          {positive ? <TrendingUp size={15} /> : <TrendingDown size={15} />}

          {positive ? "Increases" : "Decreases"}
        </div>
      </div>

      <div className="driver-description">
        {driver.interpretation ||
          driver.description ||
          "Feature contribution to the current prediction."}
      </div>

      <div className="driver-impact-row">
        <span>Model contribution</span>

        <strong>
          {positive ? "+" : ""}
          {Number(driver.impact).toFixed(3)}
        </strong>
      </div>
    </div>
  );
}

function App() {
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  async function fetchDashboardData() {
    try {
      const [predictionData, historyData, statsData] = await Promise.all([
        getLatestPrediction(),
        getReadingHistory(50, DEVICE_ID),
        getStats(DEVICE_ID),
      ]);

      setPrediction(predictionData);
      setHistory(Array.isArray(historyData?.data) ? historyData.data : []);
      setStats(statsData);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message || "Unable to connect to backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDashboardData();

    const interval = setInterval(fetchDashboardData, REFRESH_INTERVAL);

    return () => clearInterval(interval);
  }, []);

  const p = prediction?.prediction;
  const sensors = prediction?.sensor_values;
  const confidence = prediction?.confidence;
  const reliability = prediction?.model_reliability;
  const explainability = prediction?.explainability;

  const interval = p?.prediction_interval;

  const drivers = explainability?.top_drivers || [];

  const chartData = [...history]
    .reverse()
    .map((reading) => ({
      time: formatTime(reading.recorded_at || reading.timestamp),
      bod:
        reading.predicted_bod ??
        reading.prediction?.predicted_bod ??
        reading.bod,
      tds: reading.tds_ppm ?? reading.sensor_values?.tds_ppm,
      turbidity: reading.turbidity_ntu ?? reading.sensor_values?.turbidity_ntu,
      temperature:
        reading.temperature_c ?? reading.sensor_values?.temperature_c,
    }))
    .filter((item) => item.bod != null);

  const confidenceTier = confidence?.tier || "Unknown";

  const isLowConfidence = confidenceTier.toLowerCase() === "low";

  const predictionAvailable = prediction?.ready && p?.predicted_bod != null;

  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Waves size={22} />
          </div>

          <div>
            <h1>Smart-BOD</h1>
            <span>Water Intelligence</span>
          </div>
        </div>

        <div className="sidebar-label">MONITORING</div>

        <div className="nav-item active">
          <Activity size={18} />
          <span>Live Dashboard</span>
        </div>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot" />
            System Monitoring
          </div>

          <div className="sidebar-device">
            <Database size={15} />
            {DEVICE_ID}
          </div>
        </div>
      </aside>

      {/* MAIN */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              IOT · MACHINE LEARNING · WATER MONITORING
            </div>

            <h2>Live Monitoring Dashboard</h2>

            <p>Real-time sensor analytics and soft-sensor BOD estimation</p>
          </div>

          <div className="topbar-right">
            <div className="live-indicator">
              <span className="status-dot" />
              LIVE
            </div>

            <button
              className="refresh-button"
              onClick={fetchDashboardData}
              title="Refresh data"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* PREDICTION */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>BOD Prediction</h3>
              <p>Machine learning soft sensor output</p>
            </div>
          </div>

          <div className="prediction-grid">
            <div className="prediction-card">
              <div className="prediction-card-header">
                <div className="prediction-label">
                  <Brain size={17} />
                  Predicted Biochemical Oxygen Demand
                </div>

                <span
                  className={`confidence-badge ${
                    isLowConfidence ? "confidence-low" : "confidence-normal"
                  }`}
                >
                  {confidenceTier} Confidence
                </span>
              </div>

              {predictionAvailable ? (
                <>
                  <div className="prediction-main-value">
                    {Number(p.predicted_bod).toFixed(2)}
                    <span>mg/L</span>
                  </div>

                  <div className="prediction-interval">
                    <span>90% Prediction Interval</span>

                    <strong>
                      {interval?.low != null
                        ? Number(interval.low).toFixed(2)
                        : "--"}
                      {" — "}
                      {interval?.high != null
                        ? Number(interval.high).toFixed(2)
                        : "--"}
                      mg/L
                    </strong>
                  </div>

                  <div className="prediction-footer">
                    <span>
                      <Clock size={14} />
                      Updated {formatTime(prediction.recorded_at)}
                    </span>

                    <span>
                      Uncertainty:{" "}
                      {p.uncertainty != null
                        ? Number(p.uncertainty).toFixed(3)
                        : "--"}
                    </span>
                  </div>
                </>
              ) : (
                <div className="prediction-loading">
                  {loading
                    ? "Loading prediction..."
                    : "Waiting for sensor window..."}
                </div>
              )}
            </div>

            <div className="confidence-card">
              <div className="confidence-card-title">Prediction Confidence</div>

              <div className="confidence-score">
                {confidence?.score != null
                  ? Number(confidence.score).toFixed(1)
                  : "--"}
                <span>%</span>
              </div>

              <div className="confidence-track">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${Math.max(
                      0,
                      Math.min(100, confidence?.score || 0)
                    )}%`,
                  }}
                />
              </div>

              <div className="confidence-caption">
                {isLowConfidence
                  ? "Prediction reliability is currently low"
                  : "Model confidence score"}
              </div>

              {isLowConfidence && (
                <div className="confidence-warning">
                  <AlertTriangle size={15} />
                  Interpret this estimate cautiously
                </div>
              )}
            </div>
          </div>
        </section>

        {/* SENSOR METRICS */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>Sensor Readings</h3>
              <p>Current measurements from connected device</p>
            </div>
          </div>

          <div className="metrics-grid">
            <MetricCard
              title="Total Dissolved Solids"
              value={
                sensors?.tds_ppm != null
                  ? Number(sensors.tds_ppm).toFixed(2)
                  : "--"
              }
              unit="ppm"
              icon={Droplets}
              color="#56C5F0"
              subtitle="Dissolved substances"
            />

            <MetricCard
              title="Turbidity"
              value={
                sensors?.turbidity_ntu != null
                  ? Number(sensors.turbidity_ntu).toFixed(2)
                  : "--"
              }
              unit="NTU"
              icon={Gauge}
              color="#A78BFA"
              subtitle="Water cloudiness"
            />

            <MetricCard
              title="Temperature"
              value={
                sensors?.temperature_c != null
                  ? Number(sensors.temperature_c).toFixed(2)
                  : "--"
              }
              unit="°C"
              icon={Thermometer}
              color="#F59E0B"
              subtitle="Water temperature"
            />
          </div>
        </section>

        {/* MODEL RELIABILITY */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>Model Reliability</h3>
              <p>Input distribution and prediction uncertainty</p>
            </div>
          </div>

          <div className="reliability-grid">
            <div className="reliability-card">
              <div className="reliability-label">Mahalanobis Distance</div>

              <div className="reliability-value">
                {reliability?.mahalanobis_distance != null
                  ? Number(reliability.mahalanobis_distance).toFixed(3)
                  : "--"}
              </div>

              <p>
                Measures how far the sensor input is from the training-data
                distribution.
              </p>
            </div>

            <div className="reliability-card">
              <div className="reliability-label">OOD Factor</div>

              <div className="reliability-value">
                {reliability?.ood_factor != null
                  ? Number(reliability.ood_factor).toFixed(3)
                  : "--"}
              </div>

              <p>
                Indicates how unfamiliar the current sensor conditions are to
                the model.
              </p>
            </div>

            <div className="reliability-card reliability-status">
              <div className="reliability-label">Current Assessment</div>

              <div
                className={`assessment ${
                  isLowConfidence ? "assessment-warning" : "assessment-good"
                }`}
              >
                {isLowConfidence ? (
                  <AlertTriangle size={18} />
                ) : (
                  <CheckCircle2 size={18} />
                )}

                {isLowConfidence ? "Use with caution" : "Model estimate"}
              </div>

              <p>
                {reliability?.explanation ||
                  "Reliability metrics evaluate how closely current sensor inputs resemble model training conditions."}
              </p>
            </div>
          </div>
        </section>

        {/* CHART */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>BOD Trend</h3>
              <p>Historical model predictions</p>
            </div>
          </div>

          <div className="chart-card">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={chartData}
                  margin={{
                    top: 10,
                    right: 20,
                    left: 0,
                    bottom: 5,
                  }}
                >
                  <CartesianGrid stroke="#263244" strokeDasharray="3 3" />

                  <XAxis
                    dataKey="time"
                    stroke="#718096"
                    tick={{ fill: "#718096", fontSize: 12 }}
                  />

                  <YAxis
                    stroke="#718096"
                    tick={{ fill: "#718096", fontSize: 12 }}
                  />

                  <Tooltip
                    contentStyle={{
                      background: "#111827",
                      border: "1px solid #263244",
                      borderRadius: 10,
                    }}
                  />

                  <Line
                    type="monotone"
                    dataKey="bod"
                    name="Predicted BOD"
                    stroke="#32D6C5"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">
                <Activity size={24} />
                <span>Waiting for historical predictions...</span>
              </div>
            )}
          </div>
        </section>

        {/* SENSOR HISTORY */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>Sensor Trends</h3>
              <p>Historical sensor behaviour</p>
            </div>
          </div>

          <div className="sensor-chart-grid">
            <div className="chart-card">
              <h4>TDS</h4>

              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#263244" strokeDasharray="3 3" />
                  <XAxis dataKey="time" hide />
                  <YAxis
                    stroke="#718096"
                    tick={{ fill: "#718096", fontSize: 11 }}
                  />
                  <Tooltip />
                  <Line
                    dataKey="tds"
                    stroke="#56C5F0"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-card">
              <h4>Turbidity</h4>

              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#263244" strokeDasharray="3 3" />
                  <XAxis dataKey="time" hide />
                  <YAxis
                    stroke="#718096"
                    tick={{ fill: "#718096", fontSize: 11 }}
                  />
                  <Tooltip />
                  <Line
                    dataKey="turbidity"
                    stroke="#A78BFA"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-card">
              <h4>Temperature</h4>

              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#263244" strokeDasharray="3 3" />
                  <XAxis dataKey="time" hide />
                  <YAxis
                    stroke="#718096"
                    tick={{ fill: "#718096", fontSize: 11 }}
                  />
                  <Tooltip />
                  <Line
                    dataKey="temperature"
                    stroke="#F59E0B"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* EXPLAINABILITY */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>Prediction Explainability</h3>
              <p>Feature contributions to the current prediction</p>
            </div>
          </div>

          <div className="explainability-grid">
            {drivers.length > 0 ? (
              drivers
                .slice(0, 5)
                .map((driver, index) => (
                  <DriverCard key={driver.feature || index} driver={driver} />
                ))
            ) : (
              <div className="chart-empty">
                <Brain size={24} />
                <span>
                  Explainability data will appear when a prediction is
                  available.
                </span>
              </div>
            )}
          </div>

          <div className="explainability-disclaimer">
            <AlertTriangle size={15} />
            Feature contributions describe model behaviour and do not establish
            causal relationships in water.
          </div>
        </section>

        {/* STATISTICS */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>System Statistics</h3>
              <p>Aggregated device data</p>
            </div>
          </div>

          <div className="stats-grid">
            <div className="stat-card">
              <span>Total Readings</span>
              <strong>{stats?.total_readings ?? "--"}</strong>
            </div>

            <div className="stat-card">
              <span>Average BOD</span>
              <strong>
                {stats?.metrics?.predicted_bod?.average != null
                  ? Number(stats.metrics.predicted_bod.average).toFixed(2)
                  : "--"}
                <small> mg/L</small>
              </strong>
            </div>

            <div className="stat-card">
              <span>Average TDS</span>
              <strong>
                {stats?.metrics?.tds_ppm?.average != null
                  ? Number(stats.metrics.tds_ppm.average).toFixed(2)
                  : "--"}
                <small> ppm</small>
              </strong>
            </div>

            <div className="stat-card">
              <span>Average Turbidity</span>
              <strong>
                {stats?.metrics?.turbidity_ntu?.average != null
                  ? Number(stats.metrics.turbidity_ntu.average).toFixed(2)
                  : "--"}
                <small> NTU</small>
              </strong>
            </div>
          </div>
        </section>

        {/* RECENT READINGS */}
        <section className="section">
          <div className="section-heading">
            <div>
              <h3>Recent Readings</h3>
              <p>Latest measurements received from device</p>
            </div>
          </div>

          <div className="table-card">
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>TDS (ppm)</th>
                    <th>Turbidity (NTU)</th>
                    <th>Temperature (°C)</th>
                    <th>BOD (mg/L)</th>
                  </tr>
                </thead>

                <tbody>
                  {history.slice(0, 10).map((reading, index) => (
                    <tr key={reading.id || index}>
                      <td>
                        {formatDate(reading.recorded_at || reading.timestamp)}
                      </td>

                      <td>
                        {(reading.tds_ppm ?? reading.sensor_values?.tds_ppm) !=
                        null
                          ? Number(
                              reading.tds_ppm ?? reading.sensor_values?.tds_ppm
                            ).toFixed(2)
                          : "--"}
                      </td>

                      <td>
                        {(reading.turbidity_ntu ??
                          reading.sensor_values?.turbidity_ntu) != null
                          ? Number(
                              reading.turbidity_ntu ??
                                reading.sensor_values?.turbidity_ntu
                            ).toFixed(2)
                          : "--"}
                      </td>

                      <td>
                        {(reading.temperature_c ??
                          reading.sensor_values?.temperature_c) != null
                          ? Number(
                              reading.temperature_c ??
                                reading.sensor_values?.temperature_c
                            ).toFixed(2)
                          : "--"}
                      </td>

                      <td>
                        {(reading.predicted_bod ??
                          reading.prediction?.predicted_bod) != null
                          ? Number(
                              reading.predicted_bod ??
                                reading.prediction?.predicted_bod
                            ).toFixed(2)
                          : "--"}
                      </td>
                    </tr>
                  ))}

                  {history.length === 0 && (
                    <tr>
                      <td colSpan="5" className="table-empty">
                        No readings available yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* FOOTER */}
        <footer className="dashboard-footer">
          <div>
            <span className="status-dot" />
            Smart-BOD monitoring system
          </div>

          <div>
            Last refresh:{" "}
            {lastUpdated ? lastUpdated.toLocaleTimeString() : "--"}
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
