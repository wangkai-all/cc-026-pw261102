import React from "react";

export function GroupDot({ group }) {
  return <span className={`group-dot group-dot--${group}`} aria-hidden="true" />;
}

export function Legend({ groups }) {
  return (
    <div className="legend" aria-label="分组图例">
      {Object.entries(groups).map(([key, label]) => (
        <span className="legend-item" key={key}>
          <GroupDot group={key} />
          {label}
        </span>
      ))}
    </div>
  );
}

export function StatusPill({ tone = "neutral", children }) {
  return (
    <span className={`status-pill status-pill--${tone}`}>
      {tone === "good" ? <CheckIcon /> : null}
      {tone === "critical" || tone === "warning" ? <AlertIcon /> : null}
      {children}
    </span>
  );
}

export function SectionHeading({ index, title, subtitle, aside }) {
  return (
    <div className="section-heading">
      <div className="section-heading-main">
        <span className="section-index">{index}</span>
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      {aside ? <div className="section-aside">{aside}</div> : null}
    </div>
  );
}

export function StatTile({ label, value, note, accent, className = "" }) {
  return (
    <div className={`stat-tile ${className}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={accent ? { "--tile-accent": accent } : undefined}>
        {accent ? <span className="stat-accent" aria-hidden="true" /> : null}
        {value}
      </div>
      {note ? <div className="stat-note">{note}</div> : null}
    </div>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path
        d="M3.2 8.3 6.3 11.3 12.8 4.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AlertIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
      <path d="M8 1.8 14.8 14H1.2L8 1.8Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 6.1v3.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="8" cy="11.8" r="0.95" fill="currentColor" />
    </svg>
  );
}
