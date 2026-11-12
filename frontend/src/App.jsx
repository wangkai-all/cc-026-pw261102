import React, { useEffect, useRef, useState } from "react";
import { fetchAnalysis, fetchExperiments } from "./api.js";
import Filters from "./components/Filters.jsx";
import AssignmentPanel from "./components/AssignmentPanel.jsx";
import EffectsPanel from "./components/EffectsPanel.jsx";

const STORAGE_KEY = "experiment-analysis-theme";

function defaultFilters(experiment) {
  return {
    start: experiment.firstExposureMinDate,
    end: experiment.firstExposureMaxDate,
    expectedControlPct: String(experiment.expectedControlPct),
    expectedTreatmentPct: String(experiment.expectedTreatmentPct),
  };
}

function initialTheme() {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [experiments, setExperiments] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [filters, setFilters] = useState({
    start: "",
    end: "",
    expectedControlPct: "50",
    expectedTreatmentPct: "50",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState(initialTheme);
  const requestSeq = useRef(0);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  async function runAnalysis(params) {
    const seq = requestSeq.current + 1;
    requestSeq.current = seq;
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchAnalysis(params);
      if (requestSeq.current === seq) setResult(payload);
    } catch (caught) {
      if (requestSeq.current === seq) setError(caught.message);
    } finally {
      if (requestSeq.current === seq) setLoading(false);
    }
  }

  function applyExperiment(experiment) {
    setSelectedId(experiment.experimentId);
    const next = defaultFilters(experiment);
    setFilters(next);
    runAnalysis({ experimentId: experiment.experimentId, ...next });
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchExperiments(controller.signal)
      .then((payload) => {
        setExperiments(payload.experiments);
        if (payload.experiments.length) applyExperiment(payload.experiments[0]);
      })
      .catch((caught) => {
        if (caught.name !== "AbortError") setError(caught.message);
      });
    return () => controller.abort();
    // The initial load intentionally runs once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleExperimentChange(experimentId) {
    const experiment = experiments.find((item) => item.experimentId === experimentId);
    if (!experiment) return;
    applyExperiment(experiment);
  }

  function handleSubmit() {
    if (!selectedId) return;
    const control = Number(filters.expectedControlPct);
    const treatment = Number(filters.expectedTreatmentPct);
    if (!Number.isFinite(control) || !Number.isFinite(treatment)) {
      setError("预期分流比例必须是数字。");
      return;
    }
    if (control <= 0 || treatment <= 0 || Math.abs(control + treatment - 100) > 1e-6) {
      setError("预期分流比例之和必须为 100%，且两组均大于 0。");
      return;
    }
    if (filters.start > filters.end) {
      setError("首次曝光起始日期不能晚于结束日期。");
      return;
    }
    runAnalysis({ experimentId: selectedId, ...filters });
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <div>
              <h1>实验分析</h1>
              <p>Experiment Analysis</p>
            </div>
          </div>
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "切换到浅色模式" : "切换到深色模式"}
          >
            {theme === "dark" ? "浅色" : "深色"}
          </button>
        </div>
      </header>

      <main className="page">
        <div className="page-intro">
          <h2>先看分流，再看效果</h2>
          <p>
            从曝光与订单文件形成用户级样本：首次曝光决定分组，重复曝光不加人；跨组用户另列，
            未满七天者进入未成熟区；订单先筛窗口、再去重、最后汇总到用户。
          </p>
        </div>

        <Filters
          experiments={experiments}
          experimentId={selectedId}
          filters={filters}
          loading={loading}
          onExperimentChange={handleExperimentChange}
          onFilterChange={setFilters}
          onSubmit={handleSubmit}
        />

        {error ? (
          <div className="error-banner" role="alert">
            <strong>请求未完成</strong>
            <span>{error}</span>
          </div>
        ) : null}

        {!result && loading ? (
          <div className="loading-card" role="status">
            正在读取数据并计算…
          </div>
        ) : null}

        {result ? (
          <div className={`result-shell ${loading ? "is-loading" : ""}`}>
            {result.warnings.length ? (
              <div className="notice-strip">
                <span className="notice-strip-label">口径提示</span>
                <ul>
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <AssignmentPanel data={result} />
            <EffectsPanel data={result} />
          </div>
        ) : null}
      </main>

      <footer className="app-footer">
        <span>本地场景数据 · 所有分母按用户计 · 事件行与订单行仅用于口径核对</span>
        <span>
          数据截止 {result?.experiment.dataCutoff ?? "—"} · 观察期 7 天
        </span>
      </footer>
    </div>
  );
}
