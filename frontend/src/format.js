export function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

export function formatPct(fraction, digits = 1) {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatPp(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} pp`;
}

export function formatSignedPct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatMoney(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value < 0 ? "−" : "";
  return `${sign}¥${Math.abs(value).toFixed(digits)}`;
}

export function formatSignedMoney(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}¥${Math.abs(value).toFixed(digits)}`;
}

export function formatPValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 0.0001) return "<0.0001";
  if (value < 0.001) return value.toFixed(5);
  if (value < 0.01) return value.toFixed(4);
  return value.toFixed(3);
}

export function formatDateTime(value) {
  if (!value) return "—";
  return value.slice(0, 16);
}

export function groupLabel(groups, group) {
  return groups?.[group] ?? (group === "control" ? "对照组" : "实验组");
}
