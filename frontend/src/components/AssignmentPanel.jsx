import React, { useState } from "react";
import {
  AlertIcon,
  CheckIcon,
  GroupDot,
  Legend,
  SectionHeading,
  StatusPill,
} from "./common.jsx";
import {
  formatDateTime,
  formatInt,
  formatPp,
  formatPct,
  formatPValue,
  groupLabel,
} from "../format.js";

function SrmStatusIcon({ status }) {
  if (status === "ok") {
    return (
      <span className="status-icon status-icon--good" aria-hidden="true">
        <CheckIcon />
      </span>
    );
  }
  if (status === "anomaly") {
    return (
      <span className="status-icon status-icon--critical" aria-hidden="true">
        <AlertIcon />
      </span>
    );
  }
  return (
    <span className="status-icon status-icon--warning" aria-hidden="true">
      <AlertIcon />
    </span>
  );
}

function statusCopy(srm) {
  if (srm.status === "anomaly") {
    return {
      tone: "critical",
      label: "分流异常",
      title: "样本比例失衡，效果结论暂停",
    };
  }
  if (srm.status === "ok") {
    return {
      tone: "good",
      label: "分流正常",
      title: "未发现样本比例失衡",
    };
  }
  return {
    tone: "warning",
    label: "无法检查",
    title: "当前范围不足以做分流检查",
  };
}

function AssignmentStatusCard({ srm, conclusion, expectedShare }) {
  const copy = statusCopy(srm);
  return (
    <div className={`card srm-card srm-card--${copy.tone}`}>
      <div className="srm-main">
        <div className="srm-title-row">
          <SrmStatusIcon status={srm.status} />
          <div>
            <StatusPill tone={copy.tone}>{copy.label}</StatusPill>
            <h3>{copy.title}</h3>
          </div>
        </div>
        <p className="srm-note">{srm.note}</p>
        <p className="srm-rule">
          用所选范围内<b>所有首次曝光用户</b>做卡方拟合优度检验；预期对照
          {(expectedShare.control * 100).toFixed(1)}%，p &lt; {srm.alpha} 时报警并暂停效果结论。
        </p>
        {conclusion.paused ? (
          <div className="pause-callout" role="status">
            <AlertIcon />
            <div>
              <strong>效果结论已暂停</strong>
              <span>分流异常，下面的转化与收入明细仍可查看，但不应作为实验结论。</span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="srm-hero">
        <span className="srm-hero-label">p 值</span>
        <span className="srm-hero-value">{formatPValue(srm.pValue)}</span>
        <span className="srm-hero-foot">阈值 {srm.alpha}</span>
      </div>
    </div>
  );
}

function SrmShareCard({ srm, groups }) {
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>实际分流 vs 预期</h3>
          <p>分母为所有首次曝光用户，跨组与未成熟用户也计入分流检查。</p>
        </div>
        <Legend groups={groups} />
      </div>

      <div className="share-chart">
        {Object.keys(groups).map((group) => {
          const share = srm.observedShare[group];
          const expected = srm.expectedShare[group];
          const deviation = srm.deviationPp[group];
          return (
            <div className="share-row" key={group}>
              <div className="share-row-head">
                <span className="share-name">
                  <GroupDot group={group} />
                  {groupLabel(groups, group)}
                </span>
                <span className="share-count">
                  {formatInt(srm.observed[group])} 人 · 实际 {formatPct(share)}
                </span>
              </div>
              <div className="share-track" aria-hidden="true">
                {share !== null ? (
                  <div
                    className={`share-bar share-bar--${group}`}
                    style={{ width: `${share * 100}%` }}
                  />
                ) : null}
                {expected !== null ? (
                  <div
                    className="expected-marker"
                    style={{ left: `${expected * 100}%` }}
                  />
                ) : null}
              </div>
              <div className="share-row-foot">
                <span>预期 {formatPct(expected)}</span>
                <span>偏差 {formatPp(deviation)}</span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="chart-key">色条为实际占比，灰色竖线为预期占比。</p>
    </div>
  );
}

function FunnelCard({ funnel, groups, rules }) {
  const steps = funnel.steps;
  const byGroup = funnel.byGroup;
  return (
    <div className="card funnel-card">
      <div className="card-head">
        <div>
          <h3>样本分层：每一步剩下多少人</h3>
          <p>人数按用户计。重复曝光只增加事件行，不增加用户。</p>
        </div>
        <span className="method-pill">单位：用户</span>
      </div>

      <div className="event-context">
        <span>
          实验曝光事件 <b>{formatInt(funnel.exposureEventRows)}</b> 行
        </span>
        <span className="context-arrow" aria-hidden="true">
          →
        </span>
        <span>
          实验内独立用户 <b>{formatInt(funnel.uniqueUsersInExperiment)}</b> 人
        </span>
        <span>
          所选范围首次曝光 <b>{formatInt(funnel.firstExposureUsers)}</b> 人
        </span>
        <span className="context-muted">
          范围内重复曝光 {formatInt(funnel.repeatExposureRows)} 行，不加人
        </span>
      </div>

      <div className="funnel-steps">
        {steps.map((step, index) => (
          <div className="funnel-step" key={step.key}>
            <div className="funnel-step-head">
              <span className="step-number">{index + 1}</span>
              <div className="step-label">
                <span>{step.label}</span>
                <small>{step.note}</small>
              </div>
              <span
                className={`step-removed ${step.removed > 0 ? "" : "is-empty"}`}
                aria-hidden={step.removed > 0 ? undefined : "true"}
              >
                {step.removed > 0 ? `−${formatInt(step.removed)}` : "—"}
              </span>
              <span className="step-count">{formatInt(step.count)} 人</span>
              <span className="step-share">{formatPct(step.share)}</span>
            </div>
            <div className="funnel-track" aria-hidden="true">
              <div
                className="funnel-bar"
                style={{
                  width: `${Math.max(0, (step.share ?? 0) * 100)}%`,
                  background: `var(--funnel-${index + 1})`,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="funnel-foot">
        <span>
          {groupLabel(groups, "control")}成熟 <b>{formatInt(byGroup.control.mature)}</b> 人
        </span>
        <span>
          {groupLabel(groups, "treatment")}成熟 <b>{formatInt(byGroup.treatment.mature)}</b> 人
        </span>
        <span className="context-muted">
          观察期：首次曝光时间 ≤ 数据截止 − {rules.observationDays} 天
        </span>
      </div>
    </div>
  );
}

function CrossGroupCard({ crossGroup, groups }) {
  const [open, setOpen] = useState(false);
  const rows = crossGroup.users;
  return (
    <div className="card list-card">
      <div className="card-head">
        <div>
          <h3>跨组用户</h3>
          <p>
            同时出现在两组的用户另列，并从效果分析排除。首次曝光仍决定其分流检查分组。
          </p>
        </div>
        <span className="count-badge">{formatInt(crossGroup.count)} 人</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty-note">未发现跨组用户。</p>
      ) : (
        <>
          <button
            type="button"
            className="disclosure-button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? "收起名单" : "查看跨组名单"}
            <span aria-hidden="true">{open ? "↑" : "↓"}</span>
          </button>
          {open ? (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>用户</th>
                    <th>首次分组</th>
                    <th>首次曝光</th>
                    <th>对照曝光</th>
                    <th>实验曝光</th>
                    <th>合计事件</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.userId}>
                      <td className="mono">{row.userId}</td>
                      <td>
                        <span className="inline-group">
                          <GroupDot group={row.firstGroup} />
                          {groupLabel(groups, row.firstGroup)}
                        </span>
                      </td>
                      <td className="mono">{formatDateTime(row.firstExposure)}</td>
                      <td className="num">{formatInt(row.exposureCounts.control)}</td>
                      <td className="num">{formatInt(row.exposureCounts.treatment)}</td>
                      <td className="num">{formatInt(row.totalExposureRows)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {crossGroup.truncated ? (
            <p className="table-note">名单最多展示 500 人，完整数量见上方计数。</p>
          ) : null}
        </>
      )}
    </div>
  );
}

function ImmatureCard({ immature, groups }) {
  const [open, setOpen] = useState(false);
  const rows = immature.users;
  return (
    <div className="card list-card">
      <div className="card-head">
        <div>
          <h3>未成熟区</h3>
          <p>首次曝光不足七天观察期，不进入效果样本，也不计为未转化。</p>
        </div>
        <span className="count-badge count-badge--warning">
          {formatInt(immature.count)} 人
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="empty-note">没有观察期不足的用户。</p>
      ) : (
        <>
          <button
            type="button"
            className="disclosure-button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? "收起名单" : "查看未成熟名单"}
            <span aria-hidden="true">{open ? "↑" : "↓"}</span>
          </button>
          {open ? (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>用户</th>
                    <th>首次分组</th>
                    <th>首次曝光</th>
                    <th>已观察（天）</th>
                    <th>还差（天）</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.userId}>
                      <td className="mono">{row.userId}</td>
                      <td>
                        <span className="inline-group">
                          <GroupDot group={row.firstGroup} />
                          {groupLabel(groups, row.firstGroup)}
                        </span>
                      </td>
                      <td className="mono">{formatDateTime(row.firstExposure)}</td>
                      <td className="num">{row.observedDays}</td>
                      <td className="num">{row.daysRemaining}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {immature.truncated ? (
            <p className="table-note">名单最多展示 500 人，完整数量见上方计数。</p>
          ) : null}
        </>
      )}
    </div>
  );
}

function OrderLedger({ orders, groups }) {
  return (
    <div className="card order-card">
      <div className="card-head">
        <div>
          <h3>订单口径（仅效果样本）</h3>
          <p>
            先限定首次曝光后七天内，再按订单号去重，最后汇总到用户。更早与更晚的订单都不计。
          </p>
        </div>
        <span className="method-pill">订单 ≠ 用户</span>
      </div>

      <div className="order-ledger">
        <div className="ledger-table">
          <div className="ledger-row">
            <span>样本用户原始订单行</span>
            <b>{formatInt(orders.rawOrderRows)}</b>
          </div>
          <div className="ledger-row ledger-row--minus">
            <span>排除：早于首次曝光</span>
            <b>−{formatInt(orders.beforeFirstExposureRows)}</b>
          </div>
          <div className="ledger-row ledger-row--minus">
            <span>排除：七天窗口之外</span>
            <b>−{formatInt(orders.outsideWindowRows)}</b>
          </div>
          <div className="ledger-row">
            <span>七天窗口内订单行</span>
            <b>{formatInt(orders.inWindowRows)}</b>
          </div>
          <div className="ledger-row ledger-row--minus">
            <span>按订单号去重移除</span>
            <b>−{formatInt(orders.duplicateRowsRemoved)}</b>
          </div>
          <div className="ledger-row ledger-row--strong">
            <span>有效订单数</span>
            <b>{formatInt(orders.countedOrders)}</b>
          </div>
          <div className="ledger-row ledger-row--strong">
            <span>购买用户数（分子）</span>
            <b>{formatInt(orders.buyers)}</b>
          </div>
          <div className="ledger-row">
            <span>未购买补零用户（分母其余部分）</span>
            <b>{formatInt(orders.zeroRevenueUsers)}</b>
          </div>
        </div>

        <div className="order-group-summary">
          {Object.keys(groups).map((group) => (
            <div className="order-group" key={group}>
              <span className="share-name">
                <GroupDot group={group} />
                {groupLabel(groups, group)}
              </span>
              <div>
                <span className="order-group-value">{formatInt(orders.byGroup[group].buyers)}</span>
                <span className="order-group-unit"> 名购买用户</span>
              </div>
              <span className="context-muted">
                {formatInt(orders.byGroup[group].zeroRevenueUsers)} 人收入补零
              </span>
            </div>
          ))}
          <div className="ledger-callout">
            <b>{formatInt(orders.countedOrders)}</b> 条有效订单来自
            <b> {formatInt(orders.buyers)}</b> 名用户；转化率与每用户收入的分母都是成熟用户数。
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AssignmentPanel({ data }) {
  const groups = data.experiment.groups;
  return (
    <section className="analysis-section" aria-labelledby="assignment-title">
      <SectionHeading
        index="01"
        title="分流检查"
        subtitle="先确认用户是否按预期比例进入两组，再决定效果数值能不能解读。"
        aside={<span className="method-pill">卡方拟合优度 · α = 0.01</span>}
      />

      <AssignmentStatusCard
        srm={data.srm}
        conclusion={data.conclusion}
        expectedShare={data.srm.expectedShare}
      />

      <div className="grid-2">
        <SrmShareCard srm={data.srm} groups={groups} />
        <FunnelCard funnel={data.funnel} groups={groups} rules={data.rules} />
      </div>

      <div className="grid-2 grid-2--lists">
        <CrossGroupCard crossGroup={data.crossGroup} groups={groups} />
        <ImmatureCard immature={data.immature} groups={groups} />
      </div>

      <OrderLedger orders={data.orders} groups={groups} />
    </section>
  );
}
