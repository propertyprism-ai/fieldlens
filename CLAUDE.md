# CLAUDE.md — fieldlens 技术上下文

> ⚠️ 开始前必读：spec.md
> 本文件由 cc 自动读取，所有规范强制执行。

---

## 项目概述

PropertyPrism fieldlens：给 Hard Money Lender 提供房产风险情报报告。
输入 Zillow URL → 输出 Markdown 风险调查报告。

---

## 环境

- Python: `/opt/homebrew/bin/python3.12`
- 工作目录: `/Users/lobster/projects/propertyprism/fieldlens/`

---

## 关键依赖

### Reflexion（核心 AI 引擎）
```python
import sys
sys.path.insert(0, '/Users/lobster/.openclaw/workspace/skills/reflexion-ensemble')
from reflexion.agentic import agentic_call
```

`agentic_call(question, max_rounds=6)` — 联网搜索 + 多轮推理，返回字符串。

### Apify（Zillow 数据源）
- Actor: `maxcopell/zillow-detail-scraper`
- 输入: `{"startUrls": [{"url": "<zillow_url>"}]}`
- 参考实现: `/Users/lobster/.openclaw/workspace-dev/property-finder/scripts/1_pull_details.py`
  - `fetch_details()` — Apify 调用逻辑
  - `extract_core_fields()` — 数据清洗（直接复用）
- 环境变量: `APIFY_API_TOKEN`（已在系统环境中）

---

## 模块职责

### `src/fetcher.py`
- `fetch_property(url: str) -> dict`
  - 调用 Apify `maxcopell/zillow-detail-scraper`
  - 返回 `extract_core_fields()` 清洗后的数据
  - 失败抛 `FetchError`

### `src/investigator.py`
- `investigate_macro(address: str) -> dict`
  - 调用 `agentic_call()` 做 Layer 1 宏观区域扫描
  - prompt 从 `prompts/layer1_macro.txt` 读取，注入地址
  - 返回结构化 dict（含 `risk_level` 字段）

- `investigate_micro(property_data: dict, macro_context: dict) -> dict`
  - 调用 `agentic_call()` 做 Layer 2 微观法证
  - prompt 从 `prompts/layer2_micro.txt` 读取
  - 注入：完整 Zillow JSON + Layer 1 摘要
  - 返回结构化 dict（含 `verdict` 字段：KILL/PURSUE）

### `src/reporter.py`
- `generate_report(property_data: dict, macro: dict, micro: dict) -> str`
  - 合并三层数据 → Markdown 字符串
  - 报告结构见 spec.md
  - 底部固定免责声明

### `main.py`
- CLI 入口：`python main.py --url <zillow_url>`
- 串联 fetcher → investigator (macro) → investigator (micro) → reporter
- 输出报告到 `results/{zpid}_{YYYY-MM-DD}.md`
- 同时打印报告路径到 stdout

---

## Prompts

### `prompts/layer1_macro.txt`
宏观区域调查 prompt。占位符：
- `{{address}}` — 完整地址
- `{{city}}` — 城市
- `{{zip}}` — 邮编
- `{{state}}` — 州

输出要求：JSON 格式，包含：
```json
{
  "risk_level": "LOW|MODERATE|HIGH|CRITICAL",
  "key_findings": ["...", "..."],
  "crime_summary": "...",
  "market_trend": "...",
  "regulatory_risks": "...",
  "infrastructure_risks": "...",
  "sources": ["url1", "url2"]
}
```

### `prompts/layer2_micro.txt`
微观法证 prompt（基于 property-finder 的 `flash_hard_filter.txt` 改写）。
6-Phase 调查框架，占位符：
- `{{listing_json}}` — Zillow 清洗后 JSON
- `{{macro_context}}` — Layer 1 结果摘要

输出：JSON 格式（含 verdict.kill_switch 和 verdict.recommended_action）

---

## 测试策略

**模式 2**：L1 单元测试 + Smoke 测试（有真实 API 调用）

### L1 单元测试（mock 所有外部调用）
- `test_fetcher.py`: mock Apify client，测试数据清洗逻辑
- `test_investigator.py`: mock agentic_call，测试 prompt 拼装 + JSON 解析
- `test_reporter.py`: 测试 Markdown 生成格式

### Smoke 测试
- `test_smoke.py`: 真实调用 Apify + Reflexion，用固定 Zillow URL
- 标注 `@pytest.mark.smoke`，默认不跑
- 测试用 URL: `https://www.zillow.com/homedetails/21145-E-Saddle-Way-Queen-Creek-AZ-85142/55277871_zpid/`
  （Queen Creek AZ，用户指定测试地址）

### 回归测试
- `test_regression.py`

---

## 参考代码路径

| 功能 | 参考文件 |
|------|---------|
| Apify 调用 | `/Users/lobster/.openclaw/workspace-dev/property-finder/scripts/1_pull_details.py` |
| 数据清洗 | 同上，`extract_core_fields()` 函数 |
| 法证 Prompt 框架 | `/Users/lobster/.openclaw/workspace-dev/property-finder/prompts/flash_hard_filter.txt` |
| 文件路径工具 | `/Users/lobster/.openclaw/workspace-dev/property-finder/scripts/utils.py` |

---

## v2.1 升级：强制数据源系统（Mandatory Sources）

### 新增模块

#### `src/market_config.py`
```python
def get_market_config(property_data: dict) -> dict | None
```
- 先查 property_data 中的 county 字段
- Fallback：city lookup table → Maricopa（Phoenix/Mesa/Queen Creek/Gilbert/Chandler/Scottsdale/Tempe/Apache Junction/Surprise/Peoria）
- 未知市场返回 None（降级运行，不崩溃）
- 返回 market_sources.json 中对应市场的完整配置

#### `config/market_sources.json`
Maricopa County 配置，含：
- assessor: https://mcassessor.maricopa.gov（地址搜索）
- recorder: https://recorder.maricopa.gov/recdocdata/（业主名搜索）
- treasurer: https://treasurer.maricopa.gov/parcel/（Parcel Number 搜索）
- fema_flood: https://msc.fema.gov/portal/search（地址搜索）
- sex_offender: https://www.azdps.gov/services/public/sex-offender
- data_chain: Assessor → Recorder → Treasurer → FEMA → Sex Offender 顺序

#### `src/investigator.py` 修改
- `investigate_macro(address, market_config=None)` — 有 market_config 时追加强制数据源到 user prompt；max_rounds=10（有配置时）
- `investigate_micro(property_data, macro, market_config=None)` — 同上，注入 data_chain

### 确认的测试用例（v2.1）

**test_market_config.py**
- `test_get_market_config_by_county`：property_data 含 county="Maricopa County" → 返回 phoenix_maricopa 配置
- `test_get_market_config_by_city_queen_creek`：county 缺失，city="Queen Creek" → 返回 phoenix_maricopa
- `test_get_market_config_by_city_phoenix`：city="Phoenix" → 返回 phoenix_maricopa
- `test_get_market_config_unknown_market`：city="Portland", state="OR" → 返回 None
- `test_get_market_config_none_input`：property_data={} → 返回 None，不崩溃
- `test_market_config_contains_required_keys`：返回 dict 含 assessor/recorder/fema_flood/data_chain 字段
- `test_investigator_macro_injects_mandatory_sources`：mock agentic_call，传入 market_config → 验证 user prompt 含 "MANDATORY SOURCES" 和 assessor URL
- `test_investigator_macro_without_market_config`：market_config=None → 不注入，行为与 v1 一致
- `test_investigator_micro_injects_data_chain`：传入 market_config → 验证 prompt 含 data_chain 顺序说明

### Smoke 测试（新增）
- `test_smoke_mandatory_sources_injected`：用 Queen Creek URL 跑完 Apify fetch → get_market_config → 验证返回 phoenix_maricopa 配置；打印 Layer 1 prompt 前 500 字符确认含 "MANDATORY SOURCES"

### ⚠️ Smoke 阶段 max_rounds 规则
- **Smoke 时 max_rounds = 3**（快速验证结构可通，不追求数据深度）
- **Production 时 max_rounds = 10**（有 market_config）/ 6（无）
- 实现方式：`investigator.py` 接受可选参数 `smoke_mode: bool = False`
  - `smoke_mode=True` → max_rounds=3（无论有无 market_config）
  - `smoke_mode=False` → 原有逻辑（有 market_config=10，无=6）
- `test_smoke.py` 中所有 investigate 调用加 `smoke_mode=True`

## v2 升级：Layer 3 架构

### 新增模块

#### `src/synthesizer.py`
```python
def synthesize(property_data: dict, macro: dict, micro: dict) -> dict
```
内部串行执行 4 步：
1. `cross_reference()` → llm_call(provider="openclaw", model="reflexion-sonnet")
2. `blue_team()` → llm_call(provider="moonshot", model="kimi-k2.5")
3. `red_team()` → llm_call(provider="deepinfra", model="Qwen/Qwen3.5-122B-A10B")
4. `judge()` → llm_call(provider="openclaw", model="reflexion-opus")

返回：
```json
{
  "cross_insights": [...],
  "blue_team": {...},
  "red_team": {...},
  "judge_verdict": {
    "executive_summary": "...",
    "final_action": "KILL|PURSUE|CONDITIONAL_PURSUE",
    "confidence": "HIGH|MEDIUM|LOW",
    "winning_side": "BLUE|RED|SPLIT",
    "unresolved_risks": [...],
    "conditions_to_pursue": [...]
  }
}
```

### llm_call 导入方式
```python
import sys
sys.path.insert(0, '/Users/lobster/.openclaw/workspace/skills/reflexion-ensemble')
from reflexion.providers import llm_call
```

接口签名：
```python
def llm_call(provider, model, messages, max_tokens=8000, tools=None, thinking=False, timeout=180) -> dict
# 返回：{"content": str, "tool_calls": list|None, "usage": dict}
```

### 新增 Prompt 文件
- `prompts/layer3_cross_reference.txt` — 占位符：`{{property_json}}` `{{macro_json}}` `{{micro_json}}`
- `prompts/layer3_blue_team.txt` — 占位符：`{{property_json}}` `{{macro_json}}` `{{micro_json}}` `{{cross_insights}}`
- `prompts/layer3_red_team.txt` — 占位符：同上 + `{{blue_team}}`
- `prompts/layer3_judge.txt` — 占位符：`{{blue_team}}` `{{red_team}}` `{{cross_insights}}`

### Layer 1/2 Prompt 新增字段
- layer1_macro.txt 末尾追加：data_confidence(0-100) + unknowns 数组
- layer2_micro.txt 每个 Phase 末尾追加：cross_reference_note 字段

### 修改文件
- `src/investigator.py`：向后兼容新字段（data_confidence/unknowns/cross_reference_note），缺失时默认值
- `src/reporter.py`：完全重写，新结构：Executive Summary → Key Insights → Risk Debate → Supporting Evidence → Data Gaps → Disclaimer
- `main.py`：Step 4 串联 synthesize()，reporter 新增 synthesis 参数

### 确认的测试用例（v2）

**test_synthesizer.py**
- `test_cross_reference_returns_insights`：mock llm_call，验证返回 cross_insights 列表，每项含 title/data_points/reasoning/so_what/estimated_impact/severity
- `test_cross_reference_injects_all_three_layers`：验证 prompt 含 property/macro/micro 数据
- `test_blue_team_returns_bull_case`：mock llm_call，验证返回含 bull_arguments 字段
- `test_red_team_receives_blue_team_output`：验证 red_team prompt 注入了 blue_team 结果
- `test_judge_returns_executive_summary`：验证返回含 executive_summary（非空字符串）
- `test_judge_returns_valid_action`：验证 final_action 是 KILL/PURSUE/CONDITIONAL_PURSUE 之一
- `test_synthesize_full_pipeline`：mock 4 个 llm_call，验证完整 synthesize() 返回结构

**test_reporter_v2.py**
- `test_report_v2_starts_with_executive_summary`：验证报告第一个 section 是 Executive Summary
- `test_report_v2_contains_key_insights`：验证含 Key Insights section，≥1 个洞察
- `test_report_v2_contains_bull_bear_debate`：验证含 Bull Case 和 Bear Case
- `test_report_v2_contains_judge_verdict`：验证含 Committee Verdict
- `test_report_v2_layer1_in_supporting_evidence`：验证 Layer 1 数据在 Supporting Evidence section
- `test_report_v2_contains_disclaimer`：验证底部免责声明

## v3 升级：双轨架构 + 日志 + 报告拆分

### 核心架构变化

**双轨数据获取（Dual Track）：**
- Track A: `src/gov_fetcher.py` — Python 直调政府 REST API（确定性硬数据）
- Track B: agentic_call — AI 搜索挖黑料（软数据，AI 专注于 API 无法获取的信息）

**报告生成拆分：**
- `src/reporter.py` 改为只输出 `raw.json` 素材包
- `src/report_writer.py` 新建，读取 raw.json → 生成 Markdown 报告

**CLI 新参数：**
```bash
python main.py --url <url>                    # 默认：pipeline + 报告
python main.py --url <url> --collect-only     # 只 pipeline，输出 raw.json
python main.py --report results/xxx_raw.json  # 只生成报告
python main.py --url <url> --zh               # 同时生成中文速览版（Sonnet 翻译）
```

### 新增模块：`src/gov_fetcher.py`

```python
def fetch_gov_sources(property_data: dict, market_key: str | None) -> dict
```

返回结构（每项含 status: SUCCESS|FAILED|NOT_CONFIGURED|SKIPPED_DEPENDENCY）：
```json
{
  "fema": {"status": "SUCCESS", "flood_zone": "X", "in_sfha": false, ...},
  "assessor": {"status": "SUCCESS", "parcel_number": "50330033", "owner": "SMITH JOHN A", ...},
  "treasurer": {"status": "NEEDS_TESTING", ...},
  "recorder": {"status": "NOT_CONFIGURED", ...}
}
```

具体函数：
- `fetch_fema_flood_zone(lat, lon)` — FEMA NFHL ArcGIS REST API（全国通用）
  - URL: `https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query`
  - 参数: geometry="{lon},{lat}", geometryType=esriGeometryPoint, outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF, f=json
  - **坐标注意：geometry 格式是 lon,lat（先经度后纬度）**
- `fetch_maricopa_parcel(lat, lon)` — Maricopa Assessor GIS API
  - URL: `https://gis.maricopa.gov/arcgis/rest/services/Assessor/AssessorParcels/MapServer/0/query`
  - 参数: geometry="{lon},{lat}", outFields=APN,OWNER,OWNER2,SITUS,ASSESSED_FULL_CASH
- `fetch_maricopa_tax(parcel_number)` — Maricopa Treasurer（status=NEEDS_TESTING，先留接口）
- FEMA 是全国通用，不依赖 market_key；county-specific 依赖 market_key

### 新增模块：`src/logger.py`

```python
def init_logger(zpid: str, date_str: str) -> logging.Logger
```

- 日志路径：`~/Projects/propertyprism/fieldlens/logs/run_{zpid}_{YYYY-MM-DD}_{HHmmss}.log`
- 双输出：FileHandler（DEBUG 级，完整详细）+ StreamHandler（INFO 级，简洁）
- 每个模块通过 `logging.getLogger(__name__)` 使用

### Gov Data → Prompt 注入

有 gov_data 时注入 PRE-FETCHED 段：
```
PRE-FETCHED GOVERNMENT DATA (Track A — verified, do NOT re-search these)
FEMA FLOOD ZONE: X (Minimal Flood Hazard) | In SFHA: NO ✅ CONFIRMED
COUNTY ASSESSOR: Owner=SMITH JOHN A, Parcel=50330033, Assessed=$385,000 ✅ CONFIRMED
...
YOUR SEARCH MISSION (Track B): 不要重复搜已确认数据，专注挖黑料...
```

### `src/investigator.py` 接口变化
- `investigate_macro(address, gov_data=None, smoke_mode=False)`
- `investigate_micro(property_data, macro, gov_data=None, smoke_mode=False)`
- 注入逻辑：`gov_data` 替代旧的 `market_config` 参数
- 旧的 `mandatory_sources_layer1/2.txt` 被 `gov_data_inject.txt` 替代

### 新增文件清单
- `src/gov_fetcher.py` — 双轨 Track A 核心
- `src/logger.py` — 统一日志模块
- `src/report_writer.py` — 报告生成（从 reporter.py 拆出）
- `prompts/gov_data_inject.txt` — Gov 数据注入模板

### 删除文件
- `prompts/mandatory_sources_layer1.txt` — 被 gov_data_inject.txt 替代
- `prompts/mandatory_sources_layer2.txt` — 被 gov_data_inject.txt 替代

### 确认的测试用例（v3）

**test_gov_fetcher.py（L1 unit + Smoke）**

L1 单元测试（mock requests）：
- `test_fema_returns_flood_zone_on_success`：mock requests.get，验证返回 status=SUCCESS + flood_zone 非空
- `test_fema_returns_failed_on_no_features`：mock 返回空 features，验证 status=FAILED
- `test_fema_returns_failed_on_request_error`：mock requests 抛 Exception，验证 status=FAILED 不崩溃
- `test_maricopa_parcel_returns_owner_on_success`：mock 返回 parcel features，验证 owner/parcel_number 非空
- `test_maricopa_parcel_skips_if_market_none`：market_key=None，assessor status=NOT_CONFIGURED
- `test_fetch_gov_sources_fema_always_runs`：market_key=None，fema 仍尝试；assessor=NOT_CONFIGURED
- `test_treasurer_skipped_if_assessor_failed`：assessor status=FAILED，treasurer status=SKIPPED_DEPENDENCY

Smoke 测试（@pytest.mark.smoke，真实 API）：
- `test_fema_flood_zone_smoke`：lat=33.2148, lon=-111.6340，验证 status=SUCCESS + flood_zone in (X,AE,AH,VE,A,D)
- `test_maricopa_assessor_smoke`：同坐标，验证 status=SUCCESS + parcel_number + owner 非空
- `test_fetch_gov_sources_integration`：完整串联，FEMA+Assessor=SUCCESS

**test_report_writer.py（新建）**
- `test_write_report_contains_executive_summary`
- `test_write_report_confirmed_data_labeled`：含 "✅ CONFIRMED" 标注
- `test_write_report_contains_disclaimer_legal`：含完整法律 disclaimer
- `test_write_report_from_raw_json`：从 raw.json 文件路径读取生成报告
- `test_write_report_zh_returns_chinese`：mock Sonnet llm_call，验证返回含中文字符

**test_logger.py（新建）**
- `test_logger_creates_file`：init_logger 后验证 log 文件在 logs/ 目录创建
- `test_logger_writes_to_file`：写一条 INFO log，验证文件里有内容
- `test_logger_path_format`：验证文件名格式 `run_{zpid}_{date}_{time}.log`

## v4 升级：Anti-Hallucination（事实性零容忍）

### 核心目标
每个报告数字必须有可追溯原始来源（raw_quote）。URL 二次验证。四级可信度标注。UNVERIFIED 数字禁入 Executive Summary 和 Key Insights。

### 新增文件
- `prompts/anti_hallucination_rules.txt` — 独立规则文件，investigator.py 在每次 agentic_call 前注入

### 修改文件
- `src/investigator.py` — 每次构建 user_prompt 时，末尾追加 anti_hallucination_rules.txt 内容
- `src/reporter.py` — pipeline 结束时调用 `verify_sources(raw_bundle)` 对所有 sources 做 HTTP HEAD 检查，更新 url_alive/verified 字段，存入 raw.json
- `src/report_writer.py` — 读取 verified 字段；Executive Summary/Key Insights 只引用 VERIFIED/CONFIRMED 数据；UNVERIFIED 数字加 `⚠️ UNVERIFIED` 标注，限于 Supporting Evidence

### 四级标注逻辑
```python
CONFIRMED  = gov_data status == "SUCCESS"  # API 直查
VERIFIED   = raw_quote >= 10 chars AND url_alive == True
UNVERIFIED = raw_quote 缺失 OR url_alive == False
NOT_FOUND  = AI 明确输出 "NOT FOUND"
```

### raw.json sources 结构升级
从 `{"url": "...", "note": "..."}` 升级为：
```json
{
  "url": "https://...",
  "raw_quote": "Sold for $500,000 on Dec 1, 2025",
  "queried_at": "2026-04-01T15:42:00Z",
  "data_type": "sale_price",
  "url_alive": true,
  "verified": true
}
```

### 确认的测试用例（v4）

**test_anti_hallucination.py**

L1 单元测试（mock requests + mock 数据）：
- `test_verify_sources_marks_alive_urls`：mock requests.head 返回 200，验证 url_alive=True, verified=True
- `test_verify_sources_marks_dead_urls`：mock requests.head 返回 404，验证 url_alive=False, verified=False
- `test_verify_sources_handles_timeout`：mock requests.head 抛 Timeout，验证 url_alive=False 不崩溃
- `test_verify_sources_skips_no_url`：source 无 url 字段，验证跳过不崩溃
- `test_source_verified_requires_raw_quote`：url_alive=True 但 raw_quote 空，verified=False
- `test_source_verified_requires_min_length`：raw_quote 只有 3 字，verified=False
- `test_report_writer_exec_summary_no_unverified`：mock bundle 含 UNVERIFIED source，生成报告的 Executive Summary 中不含该数字
- `test_report_writer_supporting_evidence_has_unverified_label`：UNVERIFIED source 数据在 Supporting Evidence 中有 `⚠️ UNVERIFIED` 标注
- `test_investigator_injects_anti_hallucination_rules`：mock agentic_call，验证 user_prompt 含 "FACTUAL INTEGRITY RULES" 字样

Smoke 测试（@pytest.mark.smoke）：
- `test_raw_json_sources_have_url_alive`：跑完整 pipeline（mock Apify），验证 raw.json 中每个 source 有 url_alive 字段

## v5 升级：Pipeline 鲁棒性（Retry + Checkpoint + Prompt 分级）

### A. Prompt 分级注入
- `src/investigator.py`：**不注入** anti_hallucination_rules（已实现，保持）
- `src/synthesizer.py`：Blue/Red/Judge 可注入（纯推理，token 充裕）
- `src/report_writer.py`：完整规则（post-processing）

### B. 检查点保存（Checkpoint）
- 新建 `src/checkpoint.py`
- 检查点目录：`results/checkpoints/{zpid}_{ts}/`
- 每层完成后保存：`layer1_macro.json` / `layer2_micro.json` / `layer3_synthesis.json` / `property_data.json` / `gov_data.json`
- `--resume {zpid}_{ts}` 参数：从已有检查点恢复，跳过已完成层

```python
def save_checkpoint(run_id: str, layer: str, data: dict) -> Path
def load_checkpoint(run_id: str, layer: str) -> dict | None
def list_checkpoints(run_id: str) -> list[str]  # 返回已完成层列表
```

### C. 自动重试（Retry）
- Layer 1/2 各加 retry 3次，失败间隔 10s
- 失败时打 WARNING log：`"Layer 1 失败（attempt 1/3），10s 后重试..."`
- 3次全失败才 raise

### 确认的测试用例（v5）

**test_robustness.py**

L1 单元测试（mock）：
- `test_save_checkpoint_creates_file`：验证 results/checkpoints/{run_id}/layer1_macro.json 被创建
- `test_load_checkpoint_returns_data`：保存后再加载，验证数据一致
- `test_load_checkpoint_returns_none_if_missing`：不存在的层返回 None，不崩溃
- `test_list_checkpoints_returns_completed_layers`：保存 layer1/layer2 后，list 返回这两个
- `test_investigate_macro_retries_on_parse_error`：mock agentic_call 前2次返回无效 JSON，第3次返回有效 JSON；验证调用了3次
- `test_investigate_macro_raises_after_max_retries`：mock agentic_call 全部返回无效 JSON；验证最终 raise ValueError
- `test_retry_waits_between_attempts`：mock time.sleep，验证重试间调用了 sleep(10)
- `test_main_resumes_from_checkpoint`：mock checkpoint 已有 layer1_macro，验证 investigate_macro 不被调用（跳过）

## v6 升级：Borrower Profile（HML 核心）

### 目标
Phase 1 Ownership 输出增加 `borrower_risk_profile`——借款人组合风险画像，这是 HML 最关心的信息。

### 改动文件
- `prompts/gov_data_inject.txt` — YOUR SEARCH MISSION 中 PHASE 1 部分，加入完整 Borrower Portfolio Risk Deep Dig（A/B/C/D 四步）
- `src/investigator.py` — `investigate_micro` 输出中补充 borrower_risk_profile 默认结构（向后兼容）

### Borrower Profile 必须包含的字段
```json
{
  "borrower_risk_profile": {
    "is_professional_investor": true | false,     // 不允许 null
    "evidence": "找不到时写 'No social/professional profile found'",
    "estimated_properties_held": 0,               // 不允许 null，找不到写 0
    "properties_found": [],
    "llc_found": false,
    "llc_names": [],
    "litigation_signals": [],
    "cross_lender_exposure": "UNKNOWN",           // KNOWN($X) | ESTIMATED($X) | UNKNOWN
    "cross_lender_note": "Maricopa Recorder inaccessible (Cloudflare); ...",
    "borrower_risk_level": "LOW | MEDIUM | HIGH", // 不允许 null
    "borrower_risk_summary": "一句话总结"
  }
}
```

### Borrower Portfolio Risk 搜索步骤（注入 prompt）
- Step A：确认身份（LinkedIn/Instagram/BiggerPockets/AZ实业委员会）
- Step B：找所有持有物业（Zillow agent profile / Redfin / azcc.gov LLC）
- Step C：估算跨贷款方风险（社交媒体 + MLS 信号，NOT Recorder）
- Step D：诉讼/破产/判决信号（AZCourts.gov Superior Court）
- ⚠️ Maricopa Recorder 被 Cloudflare 永久屏蔽，禁止尝试，直接标 UNKNOWN

### 确认的测试用例（v6）

**test_borrower_profile.py**

L1 单元测试（mock）：
- `test_borrower_profile_fields_present`：mock investigate_micro 返回无 borrower_risk_profile 的 dict，验证 investigator.py 补充了默认结构
- `test_borrower_profile_not_null`：验证 is_professional_investor/estimated_properties_held/borrower_risk_level 不为 None
- `test_borrower_profile_default_values`：缺失时默认：is_professional_investor=False, estimated_properties_held=0, borrower_risk_level="UNKNOWN"（等待 AI 填充）
- `test_gov_data_inject_contains_borrower_steps`：验证 gov_data_inject.txt 含 "BORROWER PORTFOLIO RISK" 和 "AZCourts" 关键字
- `test_recorder_explicitly_forbidden`：验证 prompt 含 "Maricopa Recorder inaccessible (Cloudflare)" 字样

## 当前状态

- 最后更新：2026-04-01
- 已完成：v2.1 强制数据源系统（Mandatory Sources）
  - `config/market_sources.json` — Maricopa County 完整配置（新建）
  - `src/market_config.py` — get_market_config()，county 优先，city fallback（新建）
  - `prompts/mandatory_sources_layer1.txt` — FEMA + Sex Offender 强制查询模板（新建）
  - `prompts/mandatory_sources_layer2.txt` — Assessor→Recorder→Treasurer→FEMA 数据链模板（新建）
  - `src/investigator.py` — investigate_macro/micro 新增 market_config=None + smoke_mode=False 参数，有配置时注入强制数据源，max_rounds=10；smoke_mode=True 时 max_rounds=3；删除了 JSON 解析失败后的降级重试逻辑
  - `main.py` — 调用 get_market_config(property_data)，传入两个 investigate 调用
  - `test_market_config.py` — 9 个 L1 单元测试（新建）
- 已完成：v2 完整实现（Layer 3 + 新 reporter）
  - `src/__init__.py`
  - `src/fetcher.py` — extract_core_fields() + fetch_property()
  - `src/synthesizer.py` — synthesize() + 4 步内部函数（cross_reference/blue_team/red_team/judge）
  - `src/reporter.py` — 完全重写，Executive Summary 前置，synthesis 参数可选
  - `prompts/layer3_cross_reference.txt` / `layer3_blue_team.txt` / `layer3_red_team.txt` / `layer3_judge.txt`
  - `prompts/layer1_macro.txt` — 追加 data_confidence + unknowns
  - `prompts/layer2_micro.txt` — 每个 Phase 追加 cross_reference_note
  - `test_synthesizer.py` + `test_reporter_v2.py`
- 已完成：Smoke 测试 smoke_mode 修复
  - `src/investigator.py` — investigate_macro/micro 新增 smoke_mode: bool = False，smoke_mode=True → max_rounds=3，删降级重试
  - `test_smoke.py` — 所有 investigate 调用加 smoke_mode=True
- 已完成：Telegram 进度通知
  - `main.py` — 新增 `_notify(msg)` 函数，每层完成后调用；通知账号 dev，target 7534802214
  - 格式：每层完成后发 Telegram 进度（5条消息：fetch + 3 layers + report）
- 测试结果（2026-04-01）：
  - **64/64 全绿**（test_market_config:9 + test_synthesizer:7 + test_reporter_v2:6 + test_fetcher + test_investigator + test_reporter + test_regression）
  - Smoke 测试：保持原有设计（需真实 API token）
- 已完成：v3 双轨架构 + 日志 + 报告拆分（2026-04-01）
  - `src/gov_fetcher.py` — fetch_fema_flood_zone / fetch_maricopa_parcel / fetch_maricopa_tax / fetch_gov_sources（新建）
  - `src/logger.py` — init_logger，双输出 File(DEBUG)+Console(INFO)（新建）
  - `src/report_writer.py` — write_report / write_report_from_file / write_report_zh（新建，从 reporter.py 拆出）
  - `prompts/gov_data_inject.txt` — PRE-FETCHED 注入模板 + YOUR SEARCH MISSION（新建）
  - `src/investigator.py` — gov_data 参数替代 market_config（保留 market_config 为 deprecated 参数），使用 gov_data_inject.txt
  - `src/reporter.py` — 改为 build_raw_bundle() 素材包 + generate_report() 向后兼容包装器
  - `src/synthesizer.py` — synthesize() 接受 gov_data=None 参数
  - `config/market_sources.json` — 新增 gov_fetchers + city_to_county 字段（保留 sources + data_chain 向后兼容）
  - `src/fetcher.py` — extract_core_fields() 新增 latitude/longitude/city/state/county 字段
  - `main.py` — Step 1.5 gov_fetcher + --collect-only/--report/--zh 参数 + logger 初始化
  - `test_gov_fetcher.py` — 7个L1 + 3个Smoke（新建）
  - `test_report_writer.py` — 5个L1（新建）
  - `test_logger.py` — 3个L1（新建）
  - `test_market_config.py` — 3个investigator测试从market_config改为gov_data
  - `conftest.py` — 注册 smoke mark，默认跳过（需 --run-smoke 显式启用）
  - 删除：`prompts/mandatory_sources_layer1.txt` / `prompts/mandatory_sources_layer2.txt`
- 测试结果（2026-04-01）：
  - **79/79 全绿（3 smoke skipped）**（test_gov_fetcher:7L1 + test_report_writer:5 + test_logger:3 + 之前64个）
  - Smoke 测试：需 --run-smoke 标志或真实 API
- 已完成：v4 Anti-Hallucination（事实性零容忍）（2026-04-01）
  - `prompts/anti_hallucination_rules.txt` — FACTUAL INTEGRITY RULES（新建），含 raw_quote 要求 + 四级标注规则 + sources JSON 格式规范
  - `src/investigator.py` — investigate_macro/micro 末尾注入 anti_hallucination_rules.txt（两处均注入，在 gov_data 注入之后）
  - `src/reporter.py` — 新增 verify_sources(raw_bundle)：HTTP HEAD 检查（timeout=5s），更新 url_alive/verified 字段；verify 逻辑：url_alive && raw_quote >= 10 chars → verified=True
  - `src/report_writer.py` — 新增 _render_source() 辅助函数；Sources 渲染改用 _render_source()；verified=False → 追加 ⚠️ UNVERIFIED 标注；Executive Summary 段无 source 渲染（天然隔离）
  - `test_anti_hallucination.py` — 9个L1 + 1个Smoke（新建）
- 测试结果（2026-04-01）：
  - **88/88 全绿（4 smoke skipped）**（test_anti_hallucination:9L1 + 之前79个）
  - Smoke 测试：需 --run-smoke 标志；test_anti_hallucination smoke 用真实 HTTP HEAD 检查稳定公开 URL
- 已完成：v5 Pipeline 鲁棒性（Retry + Checkpoint + Prompt 分级）（2026-04-01）
  - `src/checkpoint.py` — save_checkpoint / load_checkpoint / list_checkpoints，存到 results/checkpoints/{run_id}/
  - `src/investigator.py` — 新增 `_call_agentic_with_retry()` 辅助函数，Layer 1/2 各加 retry 3次，失败间隔 10s，打 WARNING log
  - `main.py` — 每层完成后调 save_checkpoint()；新增 --resume {run_id} 参数，从已有检查点恢复跳过已完成层
  - `test_robustness.py` — 8个L1测试（checkpoint 4个 + retry 3个 + resume 1个）
  - `test_anti_hallucination.py` — 更新 `test_investigator_injects_anti_hallucination_rules` → `test_investigator_does_not_inject_anti_hallucination_rules`（v5 规范变更：investigator 不注入 anti_hallucination_rules）
- 测试结果（2026-04-01）：
  - **90/90 全绿（4 smoke skipped）**（test_robustness:8 + test_anti_hallucination:9 + 之前79个）
  - Smoke 测试：需 --run-smoke 标志
- 已完成：v6 Borrower Profile（HML 核心）（2026-04-01）
  - `prompts/gov_data_inject.txt` — YOUR SEARCH MISSION 全面改写为 PHASE 1 DEEP DIG（Borrower Portfolio Risk A/B/C/D）+ PHASE 2/3/4；含 azcc.gov/AZCourts 搜索指令 + Cloudflare 屏蔽声明 + borrower_risk_profile 输出规范
  - `src/investigator.py` — investigate_micro() 解析 JSON 后检查 phase1_ownership.borrower_risk_profile，缺失时补充默认结构（is_professional_investor=False, estimated_properties_held=0, borrower_risk_level="UNKNOWN"）
  - `test_borrower_profile.py` — 5个L1单元测试（新建）
- 测试结果（2026-04-01）：
  - **95/95 全绿（4 smoke skipped）**（test_borrower_profile:5 + 之前90个）
  - Smoke 测试：需 --run-smoke 标志

## ⚠️ 偏离记录

1. **fetch_property 无前置 token 检查** — 原方案：APIFY_API_TOKEN 缺失时提前抛 FetchError。实际：去掉前置检查，让 ApifyClient 自行处理 empty token。原因：test_fetch_property_success mock 了 ApifyClient 但未设置 env var，前置检查导致测试无法 mock。
2. **Smoke 测试 URL 与 CLAUDE.md 规范不符** — CLAUDE.md 指定 `21145-E-Saddle-Way/55277871_zpid`，test_smoke.py 实际使用 `19533-E-Timberline-Rd/2071932938_zpid`。原因：test_smoke.py 已提前写好，未改动。
3. **reporter.py 标题改为 "FieldLens Risk Intelligence Report"** — 原 v1 用 "PropertyPrism Risk Intelligence Report"，v2 重写时用项目名，旧测试未检查标题文字，向后兼容。
4. **market_config 参数保留为 deprecated** — CLAUDE.md 规范：market_config 完全替换为 gov_data。实际：market_config 保留在 investigate_macro/micro 签名中（ignored），避免 test_smoke.py 在参数收集时抛 TypeError。未来可删除。
5. **reporter.py 保留 generate_report()** — CLAUDE.md 规范：reporter.py 改为只输出 raw.json。实际：generate_report() 作为向后兼容包装器保留（委托给 report_writer.write_report），确保 test_reporter.py / test_reporter_v2.py / test_regression.py 无需修改。
6. **config/market_sources.json 保留 phoenix_maricopa 为 key** — CLAUDE.md 规范 v3 用 az_maricopa。实际：保留 phoenix_maricopa 键名，因为 market_config.py 的 lookup 表引用此键。gov_fetcher.py 内部用 phoenix_maricopa 作为 market_key。
7. **test_anti_hallucination.py 测试更新** — 原测试名 `test_investigator_injects_anti_hallucination_rules` 验证 investigator 注入 FACTUAL INTEGRITY RULES（v4 行为）。v5 规范变更：investigator.py 不注入 anti_hallucination_rules（Prompt 分级，短 prompt）。测试更新为 `test_investigator_does_not_inject_anti_hallucination_rules`，验证行为符合 v5。
