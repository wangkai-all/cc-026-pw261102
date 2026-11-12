# 实验分析页：分流检查 → 转化与每用户收入

一个可本地运行的实验分析页。页面先回答「分流有没有问题」，再展示转化与收入变化。数据来自曝光文件与订单文件，所有分母都按**独立用户**计，事件行数只用于核对口径。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 重新生成四组本地场景数据（已提交，可跳过）
.venv/bin/python backend/scripts/generate_data.py

# 构建 React 前端
cd frontend
npm install
npm run build
cd ..

# FastAPI 同时提供 API 和已构建的前端
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。

前端开发模式（Vite 代理 `/api` 到 8000 端口）：

```bash
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
cd frontend && npm run dev     # http://127.0.0.1:5173
```

运行后端测试：

```bash
.venv/bin/python -m pytest backend/tests -q
```

## 页面顺序与口径

选择实验、首次曝光日期范围和预期分流比例后，按用户形成分析样本。页面严格按以下顺序处理：

1. **首次曝光决定分组。** 同一用户重复曝光只增加事件行，不增加人数。一个用户在实验内出现过两个不同分组时，列入「跨组用户」并从效果分析排除；其首次曝光分组仍计入分流检查。
2. **完整七天观察期。** 只有 `首次曝光时间 ≤ 数据截止时间 − 7 天` 的用户进入效果样本；其余进入「未成熟区」，不算作未转化。数据截止时间取该实验曝光与订单事件的最大时间戳。
3. **订单窗口与去重。** 对效果样本用户，只保留 `[首次曝光, 首次曝光 + 7 天)` 内的订单；早于首次曝光、晚于窗口的订单均排除；窗口内先按 `order_id` 去重，再按用户汇总金额。没有有效订单的用户收入补 0。

### 分流检查

- 样本为**所选日期范围内所有首次曝光用户**（包含跨组用户与未成熟用户）。
- 使用卡方拟合优度检验比较实际人数与按预期比例算出的期望人数。
- `p < 0.01` 时标记「分流异常」并暂停效果结论；转化与收入明细仍会计算并展示，便于核对，但不作为实验结论。
- 空范围时给出「无法检查」，不伪造 p 值。

### 效果统计

- **转化**：七天内至少一笔有效订单的用户。组间比较使用双侧 Fisher 精确检验，同时展示两组转化率、绝对差（百分点）和相对提升。对照组转化率为 0 时，相对提升明确标为无法定义。
- **每用户收入**：按用户汇总有效订单金额，未购买补 0。组间均值差采用**用户级 bootstrap**：每组按原样本量有放回重抽样，固定随机种子 `20261112`，迭代 10,000 次，取 2.5% / 97.5% 百分位作为 95% 区间。
- 任一组没有成熟用户时，直接说明无法计算，不返回 0 或空区间。

## 四组本地数据

每组数据位于 `backend/data/scenarios/<slug>/`，包含 `exposures.csv`、`orders.csv`、`meta.json` 和 `manifest.json`。数据由 `backend/scripts/generate_data.py` 确定性生成。

| 场景 | 实验 ID | 曝光事件 / 用户 | 跨组 | 成熟（对照/实验） | 未成熟 | 有效订单 / 购买用户 | 分流检查 |
|---|---|---|---|---|---|---|---|
| 正常分流 | `exp_normal` | 2,259 / 2,000 | 0 | 1,800（900/900） | 200 | 294 / 234 | 1,000:1,000，p=1.000 |
| 明显偏流 | `exp_srm` | 2,091 / 1,900 | 0 | 1,700（600/1,100） | 200 | 270 / 225 | 700:1,200，p≈1.8e-30 |
| 跨组曝光 | `exp_cross_group` | 1,837 / 1,600 | 40 | 1,520（760/760） | 40 | 250 / 198 | 800:800，p=1.000 |
| 观察期不足 | `exp_immature` | 661 / 600 | 0 | 300（150/150） | 300 | 52 / 39 | 300:300，p=1.000 |

`manifest.json` 记录了每一层的人数、订单口径与转化真值；测试逐项复核，确保页面展示的是用户数而不是事件条数。例如正常场景有 2,259 条曝光事件但只有 2,000 人，294 条有效订单只来自 234 名购买用户。

## 数据文件格式

`exposures.csv`：

```csv
experiment_id,user_id,group,exposure_time
exp_normal,normal_c_0001,control,2026-09-15 03:20:11
```

`orders.csv`：

```csv
order_id,user_id,order_time,amount
normal_o_00001,normal_c_0012,2026-09-16 09:42:27,42.00
```

分组名固定为 `control` / `treatment`。每个场景目录内只放一个实验；新增场景时，放入 `backend/data/scenarios/<slug>/` 并设置 `meta.json` 的 `experiment_id`、标题、描述和默认预期比例即可被自动发现。

## API

- `GET /api/health`
- `GET /api/experiments`：实验列表、首次曝光日期范围、数据截止、默认预期比例。
- `GET /api/analysis?experiment_id=exp_normal&start=2026-09-15&end=2026-11-09&expected_control_pct=50&expected_treatment_pct=50`

`/api/analysis` 返回：

- `funnel`：每一步的用户数与分组明细；
- `orders`：订单行口径（原始、早于曝光、窗口外、窗口内、去重、有效订单、购买用户、补零用户）；
- `srm`：观测/期望人数、比例、偏差和卡方 p 值；
- `conversion`：两组 n、转化人数、转化率、绝对差 pp、相对提升、 Fisher p；
- `revenue`：两组每用户收入均值、均值差、bootstrap 区间、种子与迭代次数；
- `crossGroup` / `immature`：另列名单与计数；
- `conclusion.paused`：分流异常时暂停效果结论。

## 目录

```
backend/
  app/            FastAPI、数据加载、分析逻辑
  data/scenarios/ 四组本地数据与 manifest
  scripts/        确定性数据生成脚本
  tests/          口径与统计复核
frontend/
  src/            React 页面与样式
  dist/           已构建产物（FastAPI 直接提供）
```
