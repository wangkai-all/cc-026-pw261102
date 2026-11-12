async function request(path, signal) {
  const response = await fetch(path, { signal });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail = payload?.detail || `请求失败（HTTP ${response.status}）`;
    throw new Error(detail);
  }
  return payload;
}

export function fetchExperiments(signal) {
  return request("/api/experiments", signal);
}

export function fetchAnalysis(params, signal) {
  const query = new URLSearchParams({
    experiment_id: params.experimentId,
    start: params.start,
    end: params.end,
    expected_control_pct: String(params.expectedControlPct),
    expected_treatment_pct: String(params.expectedTreatmentPct),
  });
  return request(`/api/analysis?${query.toString()}`, signal);
}
