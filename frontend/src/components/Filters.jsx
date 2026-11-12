import React from "react";

export default function Filters({
  experiments,
  experimentId,
  filters,
  loading,
  onExperimentChange,
  onFilterChange,
  onSubmit,
}) {
  const selected = experiments.find((item) => item.experimentId === experimentId);

  const handleControl = (value) => {
    const next = { ...filters, expectedControlPct: value };
    const numeric = Number(value);
    if (value !== "" && Number.isFinite(numeric) && numeric >= 0 && numeric <= 100) {
      next.expectedTreatmentPct = String(Math.round((100 - numeric) * 10) / 10);
    }
    onFilterChange(next);
  };

  return (
    <section className="filter-card" aria-label="分析条件">
      <form
        className="filter-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label className="field field--experiment">
          <span className="field-label">实验</span>
          <select
            value={experimentId}
            onChange={(event) => onExperimentChange(event.target.value)}
          >
            {experiments.map((item) => (
              <option key={item.experimentId} value={item.experimentId}>
                {item.title} · {item.experimentId}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">首次曝光起始</span>
          <input
            type="date"
            value={filters.start}
            onChange={(event) => onFilterChange({ ...filters, start: event.target.value })}
            required
          />
        </label>

        <label className="field">
          <span className="field-label">首次曝光结束</span>
          <input
            type="date"
            value={filters.end}
            onChange={(event) => onFilterChange({ ...filters, end: event.target.value })}
            required
          />
        </label>

        <fieldset className="ratio-fields">
          <legend className="field-label">预期分流比例</legend>
          <label className="ratio-input">
            <span>对照</span>
            <input
              type="number"
              min="0.1"
              max="99.9"
              step="0.1"
              value={filters.expectedControlPct}
              onChange={(event) => handleControl(event.target.value)}
              required
            />
            <span className="unit">%</span>
          </label>
          <label className="ratio-input">
            <span>实验</span>
            <input
              type="number"
              min="0.1"
              max="99.9"
              step="0.1"
              value={filters.expectedTreatmentPct}
              onChange={(event) =>
                onFilterChange({ ...filters, expectedTreatmentPct: event.target.value })
              }
              required
            />
            <span className="unit">%</span>
          </label>
          <button
            type="button"
            className="ghost-button"
            onClick={() =>
              onFilterChange({
                ...filters,
                expectedControlPct: "50",
                expectedTreatmentPct: "50",
              })
            }
          >
            50 / 50
          </button>
        </fieldset>

        <button className="primary-button" type="submit" disabled={loading || !experiments.length}>
          {loading ? "计算中…" : "运行分析"}
        </button>
      </form>

      {selected ? (
        <p className="filter-description">
          <span>{selected.description}</span>
          <span className="dataset-facts">
            数据截止 {selected.dataCutoff} · 首次曝光 {selected.firstExposureMinDate} 至
            {selected.firstExposureMaxDate} · 曝光事件 {selected.exposureEventRows} 行 /
            {selected.uniqueUsers} 名用户
          </span>
        </p>
      ) : null}
    </section>
  );
}
