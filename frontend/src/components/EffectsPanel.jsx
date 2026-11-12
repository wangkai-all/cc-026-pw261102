import React from "react";
import { GroupDot, Legend, SectionHeading, StatTile, StatusPill } from "./common.jsx";
import {
  formatInt,
  formatMoney,
  formatPValue,
  formatPct,
  formatPp,
  formatSignedMoney,
  formatSignedPct,
  groupLabel,
} from "../format.js";

function IntervalChart({ revenue }) {
  const { ciLow, ciHigh, difference } = revenue;
  if (ciLow === null || ciHigh === null || difference === null) return null;
  const low = Math.min(0, ciLow, difference);
  const high = Math.max(0, ciHigh, difference);
  const span = high - low || 1;
  const domainLow = low - span * 0.12;
  const domainHigh = high + span * 0.12;
  const position = (value) => ((value - domainLow) / (domainHigh - domainLow)) * 100;

  return (
    <div className="interval-figure" aria-label="每用户收入差异的 95% bootstrap 区间">
      <div className="interval-track" aria-hidden="true">
        <div
          className="interval-band"
          style={{
            left: `${position(ciLow)}%`,
            width: `${Math.max(1, position(ciHigh) - position(ciLow))}%`,
          }}
        />
        <div className="interval-zero" style={{ left: `${position(0)}%` }} />
        <span className="interval-zero-label" style={{ left: `${position(0)}%` }}>
          0
        </span>
        <div
          className="interval-dot"
          style={{ left: `${position(difference)}%` }}
        />
      </div>
      <div className="interval-labels">
        <span>下限 {formatMoney(ciLow)}</span>
        <span className="interval-estimate">点估计 {formatSignedMoney(difference)}</span>
        <span>上限 {formatMoney(ciHigh)}</span>
      </div>
    </div>
  );
}

function ConversionCard({ conversion, groups }) {
  return (
    <div className="card effect-card">
      <div className="card-head">
        <div>
          <h3>转化差异</h3>
          <p>转化为首次曝光后七天内至少一笔有效订单；分母是各组成熟用户数。</p>
        </div>
        <span className="method-pill">双侧 Fisher</span>
      </div>

      {conversion.available ? (
        <>
          <div className="group-stat-grid">
            {Object.keys(groups).map((group) => {
              const item = conversion.groups[group];
              return (
                <div className={`group-stat group-stat--${group}`} key={group}>
                  <div className="group-stat-title">
                    <GroupDot group={group} />
                    {groupLabel(groups, group)}
                  </div>
                  <div className="group-stat-value">{formatPct(item.conversionRate)}</div>
                  <div className="group-stat-sub">
                    {formatInt(item.converters)} / {formatInt(item.n)} 人转化
                  </div>
                  <div className="meter" aria-hidden="true">
                    <div
                      className="meter-fill"
                      style={{ width: `${(item.conversionRate ?? 0) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="compare-grid">
            <StatTile
              label="绝对差（实验组 − 对照组）"
              value={formatPp(conversion.absoluteDifferencePp)}
            />
            <StatTile
              label="相对提升"
              value={formatSignedPct(conversion.relativeLiftPct)}
              note={conversion.relativeLiftNote}
            />
            <StatTile
              label="Fisher 双侧 p 值"
              value={formatPValue(conversion.pValue)}
              note="不做额外显著性判断"
            />
          </div>

          <details className="raw-detail">
            <summary>查看 2×2 明细</summary>
            <table className="mini-table">
              <thead>
                <tr>
                  <th>分组</th>
                  <th>已转化</th>
                  <th>未转化</th>
                  <th>合计</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(groups).map((group) => (
                  <tr key={group}>
                    <td>{groupLabel(groups, group)}</td>
                    <td className="num">{formatInt(conversion.fisherTable[group].converted)}</td>
                    <td className="num">{formatInt(conversion.fisherTable[group].notConverted)}</td>
                    <td className="num">
                      {formatInt(
                        conversion.fisherTable[group].converted +
                          conversion.fisherTable[group].notConverted,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {conversion.oddsRatio !== null ? (
              <p className="raw-note">
                Fisher 优势比（实验组 / 对照组）：{conversion.oddsRatio.toFixed(3)}
              </p>
            ) : null}
          </details>
        </>
      ) : (
        <p className="unavailable-note">
          <strong>无法计算转化差异。</strong> {conversion.reason}
        </p>
      )}
    </div>
  );
}

function RevenueCard({ revenue, groups }) {
  return (
    <div className="card effect-card">
      <div className="card-head">
        <div>
          <h3>每用户收入差异</h3>
          <p>按用户汇总七天内去重后的收入，未购买补 0；区间由用户级 bootstrap 给出。</p>
        </div>
        <span className="method-pill">95% 区间</span>
      </div>

      {revenue.available ? (
        <>
          <div className="group-stat-grid">
            {Object.keys(groups).map((group) => {
              const item = revenue.groups[group];
              return (
                <div className={`group-stat group-stat--${group}`} key={group}>
                  <div className="group-stat-title">
                    <GroupDot group={group} />
                    {groupLabel(groups, group)}
                  </div>
                  <div className="group-stat-value">{formatMoney(item.meanRevenue)}</div>
                  <div className="group-stat-sub">
                    每用户均值 · {formatInt(item.n)} 人 · 合计 {formatMoney(item.totalRevenue)}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="compare-grid compare-grid--two">
            <StatTile
              label="均值差（实验组 − 对照组）"
              value={formatSignedMoney(revenue.difference)}
              note="每用户收入，含补零用户"
            />
            <StatTile
              label="95% bootstrap 区间"
              value={`[${formatMoney(revenue.ciLow)}, ${formatMoney(revenue.ciHigh)}]`}
              note={`${formatInt(revenue.iterations)} 次重抽样 · 种子 ${revenue.seed}`}
            />
          </div>

          <IntervalChart revenue={revenue} />
          <p className="chart-key">圆点为均值差，色带为 95% 百分位区间，灰线为 0。</p>

          {revenue.notes?.length ? (
            <p className="raw-note">{revenue.notes.join(" ")}</p>
          ) : null}
          <p className="method-note">
            方法：用户级 bootstrap（每组按原样本量有放回重抽样），固定随机种子
            {revenue.seed}，迭代 {formatInt(revenue.iterations)} 次，取 2.5% 与 97.5% 分位。
          </p>
        </>
      ) : (
        <p className="unavailable-note">
          <strong>无法计算收入差异。</strong> {revenue.reason}
        </p>
      )}
    </div>
  );
}

function EffectSummary({ data }) {
  const { conversion, revenue, conclusion, srm } = data;
  const pieces = [];

  if (conversion.available) {
    pieces.push({
      key: "转化",
      text: `实验组转化率 ${formatPct(conversion.groups.treatment.conversionRate)}，较对照组绝对差 ${formatPp(
        conversion.absoluteDifferencePp,
      )}（相对提升 ${formatSignedPct(conversion.relativeLiftPct)}），双侧 Fisher p = ${formatPValue(
        conversion.pValue,
      )}。`,
    });
  } else {
    pieces.push({ key: "转化", text: conversion.reason });
  }

  if (revenue.available) {
    pieces.push({
      key: "收入",
      text: `每用户收入均值差 ${formatSignedMoney(revenue.difference)}，95% bootstrap 区间 [${formatMoney(
        revenue.ciLow,
      )}, ${formatMoney(revenue.ciHigh)}]。`,
    });
  } else {
    pieces.push({ key: "收入", text: revenue.reason });
  }

  let badge;
  if (conclusion.paused) {
    badge = <StatusPill tone="critical">结论暂停</StatusPill>;
  } else if (srm.status === "ok") {
    badge = <StatusPill tone="good">分流通过</StatusPill>;
  } else {
    badge = <StatusPill tone="warning">仅供参考</StatusPill>;
  }

  return (
    <div className={`card effect-summary ${conclusion.paused ? "is-paused" : ""}`}>
      <div className="effect-summary-head">
        <h3>结论摘要</h3>
        {badge}
      </div>
      {conclusion.paused ? (
        <p className="paused-summary-note">
          分流检查异常，以下数值不构成效果结论；明细仅用于核对口径。
        </p>
      ) : null}
      <div className="summary-rows">
        {pieces.map((piece) => (
          <div className="summary-row" key={piece.key}>
            <span className="summary-key">{piece.key}</span>
            <span>{piece.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EffectsPanel({ data }) {
  const groups = data.experiment.groups;
  const paused = data.conclusion.paused;
  return (
    <section className="analysis-section" aria-labelledby="effects-title">
      <SectionHeading
        index="02"
        title="效果分析"
        subtitle="在分流检查之后读取转化与每用户收入；所有分母均为成熟用户。"
        aside={<Legend groups={groups} />}
      />

      {paused ? (
        <div className="pause-banner" role="status">
          <AlertIconInline />
          <div>
            <strong>分流异常：效果结论暂停</strong>
            <span>
              仍展示转化与收入明细，便于核对人数、分母和区间；请不要据此宣布实验胜负。
            </span>
          </div>
        </div>
      ) : null}

      <EffectSummary data={data} />

      <div className="grid-2">
        <ConversionCard conversion={data.conversion} groups={groups} />
        <RevenueCard revenue={data.revenue} groups={groups} />
      </div>
    </section>
  );
}

function AlertIconInline() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path d="M8 1.8 14.8 14H1.2L8 1.8Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 6.1v3.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="8" cy="11.8" r="0.95" fill="currentColor" />
    </svg>
  );
}
