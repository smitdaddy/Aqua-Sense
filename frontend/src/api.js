const API_BASE_URL = "http://localhost:8000";

async function fetchJSON(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

// Latest raw sensor reading
export async function getLatestReading() {
  return fetchJSON(`${API_BASE_URL}/api/readings/latest`);
}

// Enhanced latest BOD prediction with confidence,
// prediction interval, SHAP values, and OOD metrics
export async function getLatestPrediction() {
  return fetchJSON(`${API_BASE_URL}/api/prediction/latest`);
}

// Historical readings for charts and tables
export async function getReadingHistory(limit = 50, deviceId = "device-01") {
  const url = new URL(`${API_BASE_URL}/api/readings/history`);

  url.searchParams.set("limit", limit);

  if (deviceId) {
    url.searchParams.set("device_id", deviceId);
  }

  return fetchJSON(url);
}

// Aggregated statistics
export async function getStats(deviceId = "device-01") {
  const url = new URL(`${API_BASE_URL}/api/stats`);

  if (deviceId) {
    url.searchParams.set("device_id", deviceId);
  }

  return fetchJSON(url);
}
