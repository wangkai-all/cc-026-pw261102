"""Dataset discovery and loading for the local experiment scenarios."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "scenarios"
DATA_DIR = Path(os.environ.get("EXPERIMENT_DATA_DIR", DEFAULT_DATA_DIR))

REQUIRED_EXPOSURE_COLUMNS = {"experiment_id", "user_id", "group", "exposure_time"}
REQUIRED_ORDER_COLUMNS = {"order_id", "user_id", "order_time", "amount"}


class DatasetError(RuntimeError):
    """Raised when local scenario data is missing or malformed."""


@dataclass(frozen=True)
class Scenario:
    slug: str
    meta: dict[str, Any]
    exposures: pd.DataFrame
    orders: pd.DataFrame
    data_cutoff: pd.Timestamp

    @property
    def experiment_id(self) -> str:
        return str(self.meta["experiment_id"])

    @property
    def groups(self) -> list[str]:
        return sorted(self.exposures["group"].dropna().unique().tolist())


def _read_csv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise DatasetError(f"缺少数据文件: {path}")
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise DatasetError(f"{path.name} 缺少字段: {', '.join(sorted(missing))}")
    return frame


def _load_scenario(scenario_dir: Path) -> Scenario:
    meta_path = scenario_dir / "meta.json"
    if not meta_path.exists():
        raise DatasetError(f"缺少元数据文件: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    exposures = _read_csv(scenario_dir / "exposures.csv", REQUIRED_EXPOSURE_COLUMNS)
    orders = _read_csv(scenario_dir / "orders.csv", REQUIRED_ORDER_COLUMNS)

    try:
        exposures["exposure_time"] = pd.to_datetime(exposures["exposure_time"], errors="raise")
        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="raise")
        orders["amount"] = pd.to_numeric(orders["amount"], errors="raise")
    except (ValueError, TypeError) as exc:
        raise DatasetError(f"{scenario_dir.name} 时间或金额字段无法解析: {exc}") from exc

    if exposures.empty:
        raise DatasetError(f"{scenario_dir.name} 没有曝光数据")

    experiment_ids = exposures["experiment_id"].dropna().unique().tolist()
    if len(experiment_ids) != 1:
        raise DatasetError(
            f"{scenario_dir.name} 应只包含一个实验，实际为 {experiment_ids}"
        )
    if meta.get("experiment_id") not in experiment_ids:
        raise DatasetError(
            f"{scenario_dir.name} 的 meta.json 实验 ID 与曝光文件不一致"
        )

    experiment_users = set(exposures["user_id"].dropna().unique())
    order_times = orders.loc[orders["user_id"].isin(experiment_users), "order_time"]
    cutoff_candidates = [exposures["exposure_time"].max()]
    if not order_times.empty:
        cutoff_candidates.append(order_times.max())
    data_cutoff = max(cutoff_candidates)

    return Scenario(
        slug=scenario_dir.name,
        meta=meta,
        exposures=exposures,
        orders=orders,
        data_cutoff=pd.Timestamp(data_cutoff),
    )


@lru_cache(maxsize=1)
def load_scenarios() -> dict[str, Scenario]:
    if not DATA_DIR.exists():
        raise DatasetError(f"数据目录不存在: {DATA_DIR}")
    scenarios: dict[str, Scenario] = {}
    for scenario_dir in sorted(DATA_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue
        scenario = _load_scenario(scenario_dir)
        scenarios[scenario.experiment_id] = scenario
    if not scenarios:
        raise DatasetError(f"数据目录中没有可用场景: {DATA_DIR}")
    return scenarios


def first_exposure_table(exposures: pd.DataFrame) -> pd.DataFrame:
    """One row per user: the first exposure decides the group.

    Ties on the same timestamp are broken deterministically by group name. Such
    a tie is also a cross-group user, so it never enters the effect sample.
    """

    ordered = exposures.sort_values(
        ["exposure_time", "group", "user_id"], kind="stable"
    )
    first = ordered.drop_duplicates(subset="user_id", keep="first").copy()
    return first.rename(
        columns={"group": "first_group", "exposure_time": "first_time"}
    )[["user_id", "first_group", "first_time"]]


def experiment_summaries() -> list[dict[str, Any]]:
    summaries = []
    for scenario in load_scenarios().values():
        first = first_exposure_table(scenario.exposures)
        first_min = first["first_time"].min()
        first_max = first["first_time"].max()
        summaries.append(
            {
                "experimentId": scenario.experiment_id,
                "slug": scenario.slug,
                "title": scenario.meta.get("title", scenario.experiment_id),
                "description": scenario.meta.get("description", ""),
                "sortOrder": int(scenario.meta.get("sort_order", 99)),
                "groups": scenario.meta.get(
                    "groups",
                    {"control": "对照组", "treatment": "实验组"},
                ),
                "expectedControlPct": float(
                    scenario.meta.get("expected_control_pct", 50)
                ),
                "expectedTreatmentPct": float(
                    scenario.meta.get("expected_treatment_pct", 50)
                ),
                "firstExposureMinDate": first_min.strftime("%Y-%m-%d"),
                "firstExposureMaxDate": first_max.strftime("%Y-%m-%d"),
                "dataCutoff": scenario.data_cutoff.strftime("%Y-%m-%d %H:%M:%S"),
                "exposureEventRows": int(len(scenario.exposures)),
                "uniqueUsers": int(scenario.exposures["user_id"].nunique()),
            }
        )
    return sorted(summaries, key=lambda item: (item["sortOrder"], item["experimentId"]))


def get_scenario(experiment_id: str) -> Scenario:
    scenarios = load_scenarios()
    if experiment_id not in scenarios:
        raise KeyError(experiment_id)
    return scenarios[experiment_id]
