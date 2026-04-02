# FieldLens v2 — 需求文档

> 目标：从"数据搬运工"升级为"风险分析师"。报告要有洞察，不只有数据。

---

## 一、核心问题诊断

### v1 报告的致命缺陷

1. **列事实，不连线** — "20年单一业主" 和 "无装修记录" 分开列，没有推导出 "屋顶/HVAC 大概率需要更换 = 隐性成本"
2. **留悬念，不闭环** — 6 个 Data Gaps 全是 "需确认"，HML 看完觉得你没做完
3. **无对抗，无深度** — 单次 AI 调用，没人挑战结论。说 LOW 就 LOW，没有压力测试
4. **千篇一律** — 不同房产出来的报告结构一模一样，没有针对性洞察

### v2 目标

> Tyler Larson（HML CIO）看完后的反应应该是：
> "这份报告告诉了我 3 件我没想到的事情，而且给了我结论，不是待办清单。"

---

## 二、架构升级：增加 Layer 3（Synthesis + Adversarial Debate）

### 新流程

```
输入: Zillow URL
    ↓
[Step 1] Apify 拉取房产数据（不变）
    ↓
[Step 2] Layer 1 — 宏观区域扫描（不变，但 prompt 微调）
    ↓
[Step 3] Layer 2 — 微观房产法证（不变，但 prompt 微调）
    ↓
[Step 4] 🆕 Layer 3 — Cross-Reference Synthesis（交叉推理 + 对抗博弈）
    ↓
[Step 5] 报告生成（新模板，洞察驱动）
```

### Layer 3 详细设计

Layer 3 分两个子步骤：

#### Step 4a: Cross-Reference Engine（交叉推理）

**输入：** Layer 1 JSON + Layer 2 JSON + 原始 Zillow 数据

**任务：** 将分散的数据点连接成因果链。

**Prompt 核心指令：**

```
你是一个高级 underwriting 分析师。你面前有两层调查结果。
你的任务不是重复事实，而是找到数据之间的隐含关联。

规则：
1. 每个洞察必须引用至少 2 个来自不同层/Phase 的数据点
2. 必须给出 "So What" — 对贷方意味着什么
3. 必须量化影响（估算金额、百分比、时间）

示例推理模式：
- [Layer2.Phase1: 20年单一业主] + [Layer2.Phase2: 无装修记录] + [Zillow: 2003年建]
  → 屋顶（设计寿命25年）和HVAC（设计寿命20年）大概率需要更换
  → 估计更换成本: 屋顶 $8,000-$15,000 + HVAC $5,000-$10,000
  → 对贷方意味着：如借款人计划翻修退出，预算至少需额外 $13,000-$25,000

- [Layer1: 房价 -1.1% YoY] + [Layer2.Phase5: 租金保守] + [Zillow: 1023 DOM]
  → 1023天在市 = 卖不出去。但租金有上行空间。
  → 这不是价格问题，是定价策略问题。
  → 对贷方意味着：退出策略应优先考虑租赁持有，非快速转售
```

**输出结构：**

```json
{
  "cross_insights": [
    {
      "title": "洞察标题",
      "data_points": ["来源1: 数据", "来源2: 数据"],
      "reasoning": "因果推理链",
      "so_what": "对贷方/投资者意味着什么",
      "estimated_impact": "$金额 或 百分比",
      "severity": "HIGH | MEDIUM | LOW"
    }
  ],
  "revised_risk_factors": [...],
  "revised_verdict": {
    "action": "KILL | PURSUE | CONDITIONAL_PURSUE",
    "confidence": "HIGH | MEDIUM | LOW",
    "conditions": ["条件1", "条件2"]
  }
}
```

#### Step 4b: Adversarial Challenge（对抗博弈）

**机制：Red Team vs Blue Team + Judge**

这是报告质量的核心升级。用 3 次独立的 agentic_call 实现：

**Call 1 — Blue Team（看多方）:**

```
你是这笔交易的支持者。基于以下数据，构建最强的"应该放贷"论证。
- 必须引用具体数据
- 必须反驳 Red Team 可能的攻击点
- 给出你认为的合理 LTV 和退出策略
```

**Call 2 — Red Team（看空方）:**

```
你是风险否决官。你的工作是找到这笔交易的每一个隐患。
- 逐一攻击 Blue Team 的论点
- 找出数据中的矛盾和可疑模式
- 构建最坏情况（worst case scenario）并量化损失
- 明确回答：如果这笔贷款违约，我们会亏多少？
```

**Call 3 — Judge（裁判）:**

```
你是 Investment Committee 主席。你刚听完 Blue Team 和 Red Team 的辩论。

Blue Team 论点：{blue_team_output}
Red Team 论点：{red_team_output}

你的任务：
1. 谁的论证更有说服力？为什么？
2. Red Team 提出了哪些 Blue Team 无法反驳的风险？
3. 给出最终判决和具体条件
4. 写一段 "Executive Summary"（3-5句话，直接给决策者看的）
```

**为什么这比单次调用好：**
- Blue Team 被迫构建正面逻辑链（不是罗列绿灯）
- Red Team 被迫找漏洞和矛盾（不是罗列黄灯）
- Judge 被迫在两种对立观点中做取舍（不是和稀泥）
- 最终判决经过了压力测试，confidence 更可信

---

## 三、强制数据源（Mandatory Sources） — 最关键的改动

### 问题根因（v2 实测已确认）

v1 报告有 6 个 "Data Gaps / 待确认"。v2 通过 prompt 强制要求 AI 去查这些政府网站，
**AI 确实尝试了，但因技术限制失败：**

- FEMA msc.fema.gov：JS 渲染页面，Jina reader 只拿到 shell
- Maricopa Assessor：找到 Parcel # 但业主名无法提取（interactive browser 限制）
- Maricopa Recorder：依赖 Assessor 的业主名，上游失败导致跳过

**结论：靠 prompt 逼 AI 用搜索工具去查这些政府网站行不通。**
这不是 AI 偷懒，是 agentic_call 的搜索工具（Jina/Tavily）无法处理 JS 渲染的交互式页面。

### 解决方案：双轨架构（Dual Track）

数据获取分为两条独立的 track，**并行运行，结果合并**：

```
Track A: Gov Fetcher（硬数据 — 程序直调 API）
  → FEMA Zone、业主名、Parcel Number、税务状态、评估价值
  → Python requests 直调 REST API，确定性高，速度快
  → 每个数据源必须有 smoke test 确保联通

Track B: Agentic AI Search（软数据 — AI 搜索挖掘）
  → 业主/LLC 诉讼记录、破产历史、犯罪新闻、承包商记录
  → 街区级犯罪事件、性罪犯、环境污染
  → 市场趋势、监管变化、区域开发计划
  → 这些没有 API，只能靠 AI 搜索引擎 + 推理
  → 也是"黑料"来源——HML 最想看到的意外发现

两条 track 独立运行 → 结果合并 → 注入 Layer 1/2 prompt → AI 做分析
```

```
v1 架构（单轨，失败）:
  agentic_call 一个人干所有事 → 硬数据搜不到 → "待确认"

v2 架构（双轨，正确）:
  Track A: gov_fetcher.py ──→ 硬数据（FEMA Zone X ✅）
  Track B: agentic_call ────→ 软数据（业主诉讼记录、犯罪事件等）
                    ↓ 合并 ↓
  Layer 1/2 prompt（硬数据作为已确认事实 + AI 继续挖软数据）
                    ↓
  Layer 3（Cross-Reference + 对抗博弈）
```

**关键原则：**
- Track A 解决"能用 API 拿到的就不要让 AI 搜"
- Track B 解决"API 拿不到的才让 AI 去挖"
- AI 的角色从"搜索员+分析师"变成"挖掘员+分析师"——硬数据已有，AI 专注挖黑料和做推理
- Layer 1/2 的 agentic_call **不取消**，但 prompt 里注入硬数据后，AI 不再浪费搜索轮次在已确认的数据上，可以把全部精力放在挖掘背景信息

#### 3.1 新增模块：`src/gov_fetcher.py`

统一入口 + 按市场分发到具体的 fetcher 函数。

```python
def fetch_gov_sources(property_data: dict, market_key: str | None) -> dict:
    """
    程序直调政府 REST API，获取强制数据源。
    
    Args:
        property_data: Apify 返回的 Zillow 数据（含 lat/lon）
        market_key: 市场标识（如 "az_maricopa"），None 时只查全国通用源
    
    Returns:
        {
            "fema": {
                "status": "SUCCESS" | "FAILED" | "NOT_CONFIGURED",
                "flood_zone": "X",           # X, AE, AH, VE, etc.
                "zone_subtype": "...",
                "in_sfha": false,             # Special Flood Hazard Area
                "source": "FEMA NFHL ArcGIS REST API",
                "query": {"lat": 33.21, "lon": -111.63}
            },
            "assessor": {
                "status": "SUCCESS" | "FAILED" | "NOT_CONFIGURED",
                "parcel_number": "50330033",
                "owner": "John Smith",
                "owner2": null,
                "assessed_value": 385000,
                "situs_address": "21145 E SADDLE WAY",
                "source": "Maricopa County Assessor GIS API"
            },
            "treasurer": {
                "status": "SUCCESS" | "FAILED" | "NOT_CONFIGURED",
                "tax_status": "CURRENT" | "DELINQUENT",
                "amount_due": 0,
                "last_paid": "2025-10-15",
                "source": "Maricopa County Treasurer"
            },
            "recorder": {
                "status": "SUCCESS" | "FAILED" | "NOT_CONFIGURED",
                "deeds_of_trust": [...],
                "liens": [...],
                "lis_pendens": [],
                "source": "Maricopa County Recorder"
            }
        }
    """
```

#### 3.2 具体 API 实现

**FEMA Flood Zone（全国通用，不依赖市场配置）：**

```python
import requests

def fetch_fema_flood_zone(lat: float, lon: float) -> dict:
    """FEMA National Flood Hazard Layer — ArcGIS REST API。
    输入经纬度（从 Zillow/Apify 数据中获取），返回 flood zone。"""
    url = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    features = data.get("features", [])
    if features:
        attrs = features[0]["attributes"]
        return {
            "status": "SUCCESS",
            "flood_zone": attrs.get("FLD_ZONE"),       # "X", "AE", "AH", etc.
            "zone_subtype": attrs.get("ZONE_SUBTY"),
            "in_sfha": attrs.get("SFHA_TF") == "T",    # Special Flood Hazard Area
            "source": "FEMA NFHL ArcGIS REST API",
        }
    return {"status": "FAILED", "error": "No features returned for coordinates"}
```

**Maricopa County Assessor（市场特定）：**

```python
def fetch_maricopa_parcel(lat: float, lon: float) -> dict:
    """Maricopa County Assessor — GIS Parcel Query。
    经纬度 → 业主名、Parcel Number、评估价值。"""
    url = "https://gis.maricopa.gov/arcgis/rest/services/Assessor/AssessorParcels/MapServer/0/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "APN,OWNER,OWNER2,SITUS,LEGAL,ASSESSED_FULL_CASH",
        "returnGeometry": "false",
        "f": "json",
    }
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    features = data.get("features", [])
    if features:
        attrs = features[0]["attributes"]
        return {
            "status": "SUCCESS",
            "parcel_number": attrs.get("APN"),
            "owner": attrs.get("OWNER"),
            "owner2": attrs.get("OWNER2"),
            "situs_address": attrs.get("SITUS"),
            "legal_description": attrs.get("LEGAL"),
            "assessed_value": attrs.get("ASSESSED_FULL_CASH"),
            "source": "Maricopa County Assessor GIS API",
        }
    return {"status": "FAILED", "error": "No parcel found for coordinates"}
```

**Maricopa County Treasurer（市场特定，依赖 Assessor 的 Parcel Number）：**

```python
def fetch_maricopa_tax(parcel_number: str) -> dict:
    """Maricopa County Treasurer — 税务状态查询。
    需要 Assessor 返回的 Parcel Number。"""
    url = f"https://treasurer.maricopa.gov/parcel/{parcel_number}"
    # 注意：这个可能需要 Jina/scraping，视 API 可用性而定
    # 如果有 REST API 则直接调用，否则 fallback 到 jina_read
    # 实现时需要先测试确认
    ...
```

**Maricopa County Recorder（市场特定，依赖 Assessor 的 Owner Name）：**

```python
def fetch_maricopa_recorder(owner_name: str) -> dict:
    """Maricopa County Recorder — Deed/Lien/Lis Pendens 查询。
    需要 Assessor 返回的 Owner Name。
    注意：recorder.maricopa.gov 有 Cloudflare 保护（403），
    可能需要 Jina fallback 或 headless browser。实现时需测试。"""
    ...
```

> **实现优先级：** FEMA（全国通用，API 确认可用）> Assessor（GIS API 大概率可用）
> \> Treasurer/Recorder（可能需要 scraping，复杂度高，可先留接口后续实现）

#### 3.3 数据链（Data Chain）

政府数据源之间有依赖关系，必须按顺序执行：

```
Step 1: FEMA Flood Zone
  输入: lat, lon（来自 Zillow/Apify）
  输出: flood_zone, in_sfha
  依赖: 无（全国通用 API）

Step 2: County Assessor
  输入: lat, lon（来自 Zillow/Apify）
  输出: owner_name, parcel_number, assessed_value
  依赖: 无

Step 3: County Treasurer
  输入: parcel_number（来自 Step 2）
  输出: tax_status, delinquency
  依赖: Step 2 成功

Step 4: County Recorder
  输入: owner_name（来自 Step 2）
  输出: deeds, liens, lis_pendens
  依赖: Step 2 成功
```

如果 Step 2 失败，Step 3/4 自动跳过并标记 `"status": "SKIPPED_DEPENDENCY"`.

#### 3.4 市场匹配与降级逻辑

**匹配方式：州 + County**

```python
def resolve_market(state: str, county: str) -> str | None:
    """从地址解析市场标识。
    county 优先从 Apify 返回数据获取；
    fallback: 城市名 → county lookup table。"""
    key = f"{state}_{county}".lower()
    return key if key in market_sources else None

# 城市 → county fallback mapping（Phoenix metro）
CITY_TO_COUNTY = {
    "phoenix": "maricopa", "mesa": "maricopa", "tempe": "maricopa",
    "scottsdale": "maricopa", "chandler": "maricopa", "gilbert": "maricopa",
    "queen creek": "maricopa", "glendale": "maricopa", "peoria": "maricopa",
    "surprise": "maricopa", "goodyear": "maricopa", "buckeye": "maricopa",
    # Atlanta metro
    "atlanta": "fulton", "sandy springs": "fulton", "roswell": "fulton",
    # ... 后续扩展
}
```

**未知市场降级（A2 方案）：**

匹配不到市场配置时：
1. FEMA Flood Zone **照常查**（全国通用，不依赖市场配置）
2. County-specific 数据源跳过，标记 `"status": "NOT_CONFIGURED"`
3. Layer 1/2 prompt 不注入强制数据源，相当于 v1 行为
4. 打 WARNING log：`"Market not configured for {state}_{county}, running in degraded mode"`
5. 报告正常生成，但 Data Gaps 中注明"该市场尚未配置政府数据源直连"

#### 3.5 新增配置文件：`config/market_sources.json`

market_sources.json 现在的角色变了：**不是告诉 AI 去哪搜，是告诉程序调哪个 API。**

```json
{
  "az_maricopa": {
    "market_name": "Phoenix Metro — Maricopa County, AZ",
    "state": "AZ",
    "county": "Maricopa",
    "gov_fetchers": {
      "assessor": {
        "function": "fetch_maricopa_parcel",
        "api_type": "arcgis_rest",
        "url": "https://gis.maricopa.gov/arcgis/rest/services/Assessor/AssessorParcels/MapServer/0/query",
        "input": "lat_lon",
        "status": "VERIFIED"
      },
      "treasurer": {
        "function": "fetch_maricopa_tax",
        "api_type": "web_scrape",
        "url": "https://treasurer.maricopa.gov/parcel/",
        "input": "parcel_number",
        "status": "NEEDS_TESTING"
      },
      "recorder": {
        "function": "fetch_maricopa_recorder",
        "api_type": "web_scrape",
        "url": "https://recorder.maricopa.gov/recdocdata/",
        "input": "owner_name",
        "status": "NEEDS_TESTING"
      },
      "permits": {
        "function": null,
        "status": "NOT_AVAILABLE",
        "notes": "Queen Creek 无在线 permit 数据库。其他 Maricopa 城市（Mesa/Tempe/Scottsdale）有"
      }
    },
    "city_to_county": ["phoenix","mesa","tempe","scottsdale","chandler","gilbert","queen creek","glendale","peoria","surprise","goodyear","buckeye"]
  }
}
```

> FEMA 不在 market config 里，因为它是全国通用的，直接硬编码在 gov_fetcher.py 中。

#### 3.6 Gov Data → Prompt 注入 + AI 搜索重定向

gov_fetcher 拿到的硬数据注入 prompt 后，**同时告诉 AI 不要重复搜这些，去挖更深的背景信息。**

**注入到 Layer 1 prompt 的示例：**

```
══════════════════════════════════════════════════════════
PRE-FETCHED GOVERNMENT DATA (Track A — verified, do NOT re-search these)
══════════════════════════════════════════════════════════

FEMA FLOOD ZONE (source: FEMA NFHL ArcGIS REST API):
  Flood Zone: X (Minimal Flood Hazard)
  In Special Flood Hazard Area: NO
  → Conclusion: No mandatory flood insurance required.
  → Use this as CONFIRMED data. Do NOT write "needs confirmation".

COUNTY ASSESSOR (source: Maricopa County Assessor GIS API):
  Parcel Number: 50330033
  Owner: SMITH JOHN A
  Owner 2: SMITH JANE B
  Assessed Full Cash Value: $385,000
  Situs Address: 21145 E SADDLE WAY
  → Owner is INDIVIDUAL (not LLC/Trust). Use this as CONFIRMED.

COUNTY TREASURER (source: Maricopa County Treasurer):
  Tax Status: CURRENT (no delinquency)
  → Use as CONFIRMED.

COUNTY RECORDER: NOT AVAILABLE (Cloudflare protection)
  → Use your search tools to find Deed/Lien data as fallback.

══════════════════════════════════════════════════════════
YOUR SEARCH MISSION (Track B — use your search tools for these)
══════════════════════════════════════════════════════════

The hard data above is already confirmed. Do NOT waste search rounds
re-checking FEMA or Assessor data. Instead, focus ALL your search
effort on background intelligence that APIs cannot provide:

PRIORITY SEARCHES:
  1. Owner background: Search "SMITH JOHN A" + lawsuit / judgment /
     bankruptcy / foreclosure — any litigation history
  2. Property-specific news: Search the exact address for any news
     reports, incidents, code enforcement actions
  3. Neighborhood deep dive: Recent crime incidents within 0.5 mile
     (not just aggregate scores — specific incidents)
  4. Environmental: EPA ECHO violations near address, brownfields,
     underground storage tanks
  5. Market intelligence: Recent comparable sales within 0.5 mile,
     any distressed sales or foreclosure clusters

These are the "黑料" — the unexpected findings that make this report
worth paying for. Aggregate scores from Niche/CrimeGrade are table
stakes. Go deeper.
```

**注入到 Layer 2 prompt 的示例：**

```
══════════════════════════════════════════════════════════
PRE-FETCHED GOVERNMENT DATA (Track A — use directly in Phase analysis)
══════════════════════════════════════════════════════════

PHASE 1 (Ownership): Owner = SMITH JOHN A (Individual, not LLC).
  Parcel #50330033. Assessed $385,000. USE AS CONFIRMED.

PHASE 4 (Infrastructure): FEMA Zone X. No mandatory flood insurance.
  USE AS CONFIRMED.

PHASE 6 (Regulatory): Tax status CURRENT, no delinquency.
  USE AS CONFIRMED.

PHASE 2 (Permits): Queen Creek has NO public permit database.
  State this limitation. Do not search for permits.

══════════════════════════════════════════════════════════
YOUR SEARCH MISSION (Track B — dig deeper on these)
══════════════════════════════════════════════════════════

Hard data is confirmed above. Your job is to UNCOVER what APIs miss:

PHASE 1 DEEP DIG — BORROWER PORTFOLIO RISK (HML-CRITICAL):
  This is the most important deep dig. HML's risk is 50% property, 50% borrower.
  Standard underwriting misses cross-lender exposure. Your job is to find it.

  STEP A — Confirm identity and role:
  - Search "[owner name] Arizona realtor" / "investor" / "flipper"
  - Check LinkedIn, Instagram, YouTube for self-described real estate activity
  - Is this person a professional investor or a homeowner? This changes everything.

  STEP B — Map their current portfolio (find ALL properties they hold):
  - Search "[owner name] [city] AZ property" on Zillow agent profile
  - Search "[owner name]" on Redfin as buyer/seller
  - Search Arizona Corporation Commission (azcc.gov) for any LLC registered
    to this person — LLCs often hold real estate
  - If LLC found: search that LLC name on Zillow/Redfin/Realtor for listings
  - If active on Instagram/YouTube/TikTok/BiggerPockets: scrape post content
    for mentions of current projects, addresses, or "just closed / just listed"
    — professional flippers frequently publicize their active deals

  STEP C — Estimate cross-lender HML exposure:
  - If they are an active investor/flipper: how many properties are they
    currently holding? (from Step B)
  - Search "[owner name] hard money" or "[LLC name] deed of trust Arizona"
    for any public mentions of their financing sources
  - Search "[owner name] [lender name]" if any HML lender is mentioned
    in their social media or public profiles
  - ⚠️ NOTE: Maricopa Recorder (recorder.maricopa.gov) is protected by
    Cloudflare Managed Challenge — completely inaccessible via curl, jina_read,
    or any automated HTTP method. Do NOT attempt to scrape it. Do NOT write
    "Recorder search returned X" — it never will. Explicitly state:
    "Maricopa Recorder inaccessible (Cloudflare); cross-lender debt unknown."
    Estimate total HML exposure from social media + MLS signals only.

  STEP D — Litigation and financial stress signals:
  - Search AZCourts.gov Superior Court public access for "[owner name]"
    URL: https://www.superiorcourt.maricopa.gov/publicaccess/
  - Search "[owner name] Arizona bankruptcy" (PACER records sometimes surface
    in news or legal databases)
  - Search "[owner name] judgment lien Arizona"
  - Search "[owner name] foreclosure Arizona"

  OUTPUT REQUIRED: A "borrower_risk_profile" summary answering:
  (1) Professional investor or homeowner?
  (2) Estimated number of properties currently held
  (3) Any LLC structures found?
  (4) Any litigation, bankruptcy, or judgment signals?
  (5) Cross-lender HML exposure — known or estimated?
  (6) Overall borrower risk: LOW / MEDIUM / HIGH

PHASE 2 DEEP DIG:
  - Listing claims "Brand new oven" + "Pool acid washed 4/2023"
  - Cross-check: 22-year-old house, NO renovation permits found.
    What major systems are likely at end-of-life?
    (roof 25yr, HVAC 20yr, water heater 12yr, pool equipment 10-15yr)
  - Search for contractor complaints or BBB filings at this address

PHASE 3 DEEP DIG:
  - SpotCrime / CrimeMapping: specific incidents at or near address
  - Not aggregate scores — find actual incident reports

PHASE 5 DEEP DIG:
  - Find 3-5 ACTIVE rental listings within 1 mile, similar bed/bath
  - Actual asking rents, not Zestimate or HUD FMR
  - Any Craigslist/Facebook Marketplace listings in this ZIP

⚠️ RECORDER DATA IS NOT AVAILABLE:
  recorder.maricopa.gov is protected by Cloudflare Managed Challenge.
  Automated access (curl, jina_read, HTTP) is permanently blocked.
  Do NOT attempt. Do NOT fabricate results. State the limitation and move on.
```

#### 3.7 v1 vs v2 对比：同一个数据点的报告方式

| 数据点 | v1 写法（❌） | v2 写法（✅） |
|--------|-------------|-------------|
| FEMA 洪水区 | "FEMA洪水区未确认 — 需FEMA地块核查" | "FEMA NFHL API 确认：Zone X（Minimal Flood Hazard）。无需强制洪水险。✅ CONFIRMED" |
| 业主身份 | "2023后业主/留置权未确认 — 需产权调查" | "Maricopa Assessor GIS API 确认：业主 SMITH JOHN A，Individual，Parcel #50330033，assessed $385,000。✅ CONFIRMED" |
| 税务状态 | "Trulia/Zillow show 2025 taxes of $1,559" | "Maricopa Treasurer 确认：2025 税务 CURRENT，无欠税。Zillow 数据 $1,559 与官方一致。✅ CONFIRMED" |
| 产权/留置权 | "需Maricopa County Recorder 产权核查" | "Recorder API 未接入（Cloudflare 保护），AI 通过 jina_read fallback 搜索。结果：[搜索结果]。⚠️ PARTIAL" |
| Permit | "装修许可不可搜索，需正式申请" | "Queen Creek 无公开在线 permit 数据库（已确认，致电 480-358-3000）。挂牌无结构性装修声明。⚠️ KNOWN LIMITATION" |

**关键区别：**
- ✅ CONFIRMED = 程序直调 API，硬数据
- ⚠️ PARTIAL = AI 搜索 fallback，可信度中等
- ❌ NOT AVAILABLE = 数据源不可达，明确标注

---

### Layer 1 & Layer 2 其他 Prompt 优化

### Layer 1 改动

在现有 prompt 末尾追加：

```
ADDITIONAL REQUIREMENTS:
- For each domain, also identify "UNKNOWN / NOT FOUND" items explicitly
  (do not silently skip data you couldn't find)
- When PRE-FETCHED GOVERNMENT DATA is provided above, treat it as
  CONFIRMED FACT. Do NOT re-search these data points. Do NOT write
  "needs confirmation" for confirmed data.
- Add a new field "data_confidence" (0-100): how complete is your data
  for this area? Government API confirmed data counts as 100% confidence
  for those specific fields.
```

**新增输出字段：**
```json
{
  "data_confidence": 85,
  "unknowns": ["具体说明没查到什么"],
  "gov_data_used": {
    "fema_flood": "CONFIRMED — Zone X",
    "assessor": "CONFIRMED — Owner: SMITH JOHN A, Parcel: 50330033",
    "treasurer": "CONFIRMED — Tax CURRENT",
    "recorder": "PARTIAL — jina_read fallback used"
  }
}
```

### Layer 2 改动

在每个 Phase 的 prompt 中追加"推理连接"要求：

```
FOR EACH PHASE — after stating findings, you MUST add:
  "cross_reference_note": "How this phase's findings interact with
   other phases or Layer 1 data. What does this COMBINED with [X]
   tell us that neither alone would reveal?"

When using PRE-FETCHED GOVERNMENT DATA, cite it as:
  "[CONFIRMED via Maricopa Assessor GIS API]" or "[CONFIRMED via FEMA NFHL API]"
This distinguishes confirmed facts from AI-searched findings.
```

**目的：** 让 Layer 2 在收集数据时就开始做交叉推理，为 Layer 3 提供线索。

**新增输出字段（每个 phase 内）：**
```json
{
  "findings": "...",
  "red_flags": [],
  "data_source": "CONFIRMED_API" | "AI_SEARCH" | "NOT_AVAILABLE",
  "cross_reference_note": "结合 Phase X 的 Y 数据，这意味着..."
}
```

---

## 四、Pipeline 输出与报告撰写分离

### 核心架构决策

**Pipeline 只负责收集和分析数据，输出标准化素材包（raw.json）。
报告撰写是独立模块，读取素材包，输出面向客户的正式报告。**

```
Pipeline（数据收集 + 分析）:
  Apify → Gov Fetcher → Layer 1 → Layer 2 → Layer 3
  输出: results/{zpid}_{date}_raw.json（素材包）

Report Writer（独立模块，后续迭代）:
  输入: raw.json
  处理: 法律措辞、行业术语、格式排版、disclaimer
  输出: results/{zpid}_{date}_report.md（正式报告）
```

### 为什么分开

| | Pipeline | Report Writer |
|---|---|---|
| 目标 | 准确、完整、结构化 | 专业、有说服力、法律安全 |
| 语气 | 中性、客观 | 面向 HML CIO 的商业语言 |
| 格式 | JSON | 精排版 Markdown / 未来 PDF |
| 迭代频率 | 数据源变了才改 | 每次 pitch 可能微调措辞 |
| 扩展性 | 稳定不动 | 同一素材包 → 不同客户类型出不同报告 |

### 4.1 素材包结构（raw.json）— Pipeline 的唯一正式输出

**设计原则：**
- raw.json 必须是**自包含**的 — 任何报告模块只需读这一个文件
- 每个数字必须有原始来源（raw_quote）— 不能有"有结论无原文"的字段
- 所有动态数据带时间戳 — 报告生成时可显示"as of YYYY-MM-DD"
- CoT 和搜索过程不进 raw.json — 存入独立 debug 文件

```json
{
  "meta": {
    "version": "2.0",
    "address": "21145 E Saddle Way, Queen Creek, AZ 85142",
    "zpid": "55277871",
    "generated_at": "2026-04-01T13:30:00Z",
    "market_key": "az_maricopa",
    "pipeline_duration_seconds": 720,
    "pipeline_log": "logs/run_2026-04-01_153205.log"   // debug log 路径，不嵌入 raw.json
  },

  // ── Track A: 程序直调政府 API ─────────────────────────────────────────
  "gov_data": {
    "fema": {
      "status": "SUCCESS",
      "flood_zone": "X",
      "zone_subtype": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
      "in_sfha": false,
      "source": "FEMA NFHL ArcGIS REST API",
      "queried_at": "2026-04-01T13:31:00Z",
      "query": {"lat": 33.2148, "lon": -111.6340}
    },
    "assessor": {
      "status": "FAILED",
      "error": "GIS endpoint returns JS redirect, not REST API",
      "fallback_note": "Layer 2 Track B will attempt via agentic search"
    },
    "treasurer": { "status": "SKIPPED_DEPENDENCY" },
    "recorder": { "status": "NOT_CONFIGURED" }
  },

  // ── Zillow 原始数据 ────────────────────────────────────────────────────
  "property_data": {
    "zpid": "55277871",
    "address": "21145 E Saddle Way, Queen Creek, AZ 85142",
    "price": 460000,
    "yearBuilt": 2003,
    "bedrooms": 3, "bathrooms": 2,
    "livingArea": 1859, "lotSize": 7347,
    "latitude": 33.2148, "longitude": -111.6340,
    "taxAnnualAmount": 1558,
    "rentZestimate": 2506,
    "hoaFee": 0,
    "priceHistory": [...],
    "description": "..."
    // 完整 Zillow 字段，Apify 原始输出
  },

  // ── Track B Layer 1: 宏观区域分析 ──────────────────────────────────────
  "macro": {
    "risk_level": "LOW",
    "risk_rationale": "...",
    "data_confidence": 84,
    "key_findings": ["...", "..."],
    "crime_summary": "...",
    "market_trend": "...",
    "regulatory_risks": "...",
    "infrastructure_risks": "...",
    "macro_signals": "...",
    "red_flags": ["..."],
    "green_signals": ["..."],
    "unknowns": ["..."],

    // ★ 关键：每个 source 必须是对象，含 raw_quote
    "sources": [
      {
        "url": "https://spotcrime.com/AZ/Queen%20Creek/trends",
        "raw_quote": "19 assaults, 0 shootings, 14 burglaries, 18 thefts",
        "data_type": "crime_monthly",
        "queried_at": "2026-04-01T15:42:00Z",
        "verified": true
      },
      {
        "url": "https://www.zillow.com/homedetails/21120-E-SADDLE-Way-.../",
        "raw_quote": "Sold $425,000 · Dec 2025",
        "data_type": "sale_price",
        "queried_at": "2026-04-01T15:43:00Z",
        "verified": true
      }
      // 每个数字一条 source 记录
    ]
  },

  // ── Track B Layer 2: 微观房产取证 ──────────────────────────────────────
  "micro": {
    "verdict": {
      "action": "CONDITIONAL_PURSUE",
      "confidence": "MEDIUM",
      "kill_switch": false
    },
    "top_risks": ["..."],
    "top_strengths": ["..."],
    "data_gaps": ["..."],

    "phase_results": {
      "phase1_ownership": {
        "owner_type": "private_individual | professional_investor | LLC",
        "hold_duration_months": 31,
        "findings": "...",
        "red_flags": ["..."],
        "cross_reference_note": "...",

        // ★ 新增：借款人组合风险画像（HML 视角最重要的输出）
        "borrower_risk_profile": {
          "is_professional_investor": true,           // true/false
          "evidence": "Instagram @xxx: 'AZ Realtor, Investor, Flipper'",
          "estimated_properties_held": 3,             // 当前持有物业数（估算）
          "properties_found": [                       // 搜索到的其他物业
            {"address": "...", "source": "Zillow agent profile", "status": "listed/sold/holding"}
          ],
          "llc_found": false,                         // 是否找到 LLC 实体
          "llc_names": [],
          "litigation_signals": [],                   // 诉讼/破产/判决
          "cross_lender_exposure": "UNKNOWN",         // KNOWN($X) | ESTIMATED($X) | UNKNOWN
          "cross_lender_note": "Maricopa Recorder inaccessible; estimated based on...",
          "borrower_risk_level": "LOW | MEDIUM | HIGH",
          "borrower_risk_summary": "..."              // 一句话总结
        },

        // ★ 每个 phase 必须有自己的 sources
        "sources": [
          {
            "url": "https://www.homes.com/property/21145-e-saddle-way.../",
            "raw_quote": "Current Owners Jun 2023 - Present. Palladino Nicolas. Owner Type. Private Individual.",
            "data_type": "owner_name",
            "queried_at": "2026-04-01T15:44:00Z",
            "verified": true
          }
        ]
      },
      "phase2_permits": {
        "findings": "...",
        "red_flags": ["..."],
        "cross_reference_note": "...",
        "sources": [...]
      },
      // phase3 ~ phase6 同结构
    },

    // Layer 2 全局 sources（跨 phase 使用的）
    "sources": [...]
  },

  // ── Layer 3: 交叉推理 + 对抗博弈 ────────────────────────────────────────
  "synthesis": {
    "cross_insights": [
      {
        "title": "Palladino's 31-Month No-Renovation Hold Proves Defects Survive",
        "severity": "HIGH",
        "data_points": [
          // 引用上游 phase 的字段路径，不重复存储原文
          "micro.phase1_ownership.findings",
          "micro.phase2_permits.findings"
        ],
        "reasoning": "...",
        "so_what": "...",             // 对 HML 意味着什么
        "estimated_impact": "$20,000-$25,000"
      }
    ],
    "blue_team": {
      "bull_summary": "...",
      "bull_arguments": ["..."],
      "recommended_ltv": 65,
      "exit_strategy": "...",
      "confidence_in_deal": "MEDIUM"
    },
    "red_team": {
      "bear_summary": "...",
      "bear_arguments": ["..."],
      "worst_case_loss": "$73,000-$75,000",  // capex $40K + ARV下行$25K + pool$10K
      "unresolved_risks": ["..."]
    },
    "judge_verdict": {
      "executive_summary": "...",
      "final_action": "CONDITIONAL_PURSUE",
      "confidence": "MEDIUM",
      "winning_side": "SPLIT",
      "adjusted_ltv": 60,
      "conditions_to_pursue": ["..."],
      "unresolved_risks": ["..."]
    }
  }
}
```

**source 对象规范：**

```python
class Source(TypedDict):
    url: str                    # 必须
    raw_quote: str              # 必须，≥10字，AI 实际读到的原文
    data_type: str              # 必须，见下方类型列表
    queried_at: str             # 必须，ISO 8601
    verified: bool              # raw_quote 非空且 len >= 10
    url_alive: bool | None      # report_writer 生成时填入（pipeline 阶段不填）

# data_type 枚举
DATA_TYPES = [
    "sale_price", "rental_price", "loan_amount", "assessed_value",
    "tax_amount", "crime_monthly", "owner_name", "permit_record",
    "flood_zone", "market_stat", "regulatory", "news", "other"
]
```

**没有 raw_quote 的 source 自动标记 `"verified": false`。**

### 4.2 Report Writer — 暂停实现（DEFERRED）

> ⏸️ **Report Writer 模块暂不实现。**
>
> 当前阶段的唯一目标是让 raw.json 成为完备的、可独立对接任意报告模块的数据包。
> Report Writer 是 raw.json 完成后的下一阶段工作。
>
> **原因：**
> 1. 报告的受众（HML、DSCR lender、投资人）不同，报告格式需求差异大
> 2. 先做好"挖黑"（数据收集与分析），再做"写字"（文书）
> 3. 文书的措辞、法律语言需要独立打磨，不能混在 pipeline 里
>
> **计划：** raw.json 稳定后，单独启动 report_writer 子项目，按受众类型分开实现（HML 版、investor 版）

**当前阶段 pipeline 的唯一输出：`results/{zpid}_{date}_raw.json`**

---

## 五、代码改动清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `config/market_sources.json` | 各市场 Gov API 配置（API URL、输入类型、状态） |
| `src/gov_fetcher.py` | 🆕 核心：程序直调政府 REST API（FEMA、Assessor、Treasurer、Recorder） |
| `src/market_config.py` | 读取 market_sources.json，按州+county 匹配市场，生成 gov_data prompt 注入段 |
| `src/synthesizer.py` | Layer 3 — 交叉推理 + 对抗博弈 |
| `prompts/layer3_cross_reference.txt` | 交叉推理 prompt |
| `prompts/layer3_blue_team.txt` | 看多方 prompt |
| `prompts/layer3_red_team.txt` | 看空方 prompt |
| `prompts/layer3_judge.txt` | 裁判 prompt |
| `prompts/gov_data_inject.txt` | Gov API 结果注入 prompt 模板（Layer 1/2 共用） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `prompts/layer1_macro.txt` | 追加 data_confidence + unknowns + gov_data_used 要求 |
| `prompts/layer2_micro.txt` | Phase 1 重写为 Borrower Portfolio Risk Deep Dig（A/B/C/D 四步）；其他 Phase 追加 cross_reference_note + data_source 字段 |
| `src/investigator.py` | 1. 接收 gov_data 参数  2. 将 gov_data 注入 prompt（PRE-FETCHED 段）  3. 适配新 JSON 输出字段 |
| `src/reporter.py` | 重构为 `assemble_raw()` — 组装并保存 raw.json（不生成报告） |
| ~~`src/report_writer.py`~~ | ⏸️ DEFERRED — 暂不实现 |
| `main.py` | 1. 解析市场 → gov_fetcher  2. Layer 1/2/3  3. 组装输出 raw.json |

### main.py 新流程

```bash
# 当前阶段：Pipeline 只输出 raw.json（report_writer 暂停）
python main.py --url <zillow_url>
# → results/{zpid}_{date}_raw.json     ✅ 正式输出
# → logs/run_{date}_{time}.log         ✅ 完整运行日志（含 debug 信息）

# report_writer 相关参数已暂时禁用：
# --collect-only  （现在默认就是 collect-only）
# --report        （deferred）
# --zh            （deferred）
```

```python
# Step 1: Fetch Zillow data（不变）
property_data = fetch_property(url)

# Step 1.5: Gov Sources — 程序直调政府 API
market_key = resolve_market(
    state=property_data.get("state"),
    county=property_data.get("county"),
    city=property_data.get("city"),
)
gov_data = fetch_gov_sources(property_data, market_key)

# Step 2: Layer 1（宏观，注入 gov_data）
macro = investigate_macro(address, gov_data=gov_data)
# macro.sources 里每条必须是 Source 对象（含 raw_quote）

# Step 3: Layer 2（微观，注入 gov_data）
micro = investigate_micro(property_data, macro, gov_data=gov_data)
# micro.phase_results 每个 phase 必须有 sources 字段

# Step 4: Layer 3（交叉推理 + 对抗博弈）
synthesis = synthesize(property_data, macro, micro, gov_data=gov_data)

# Step 5: 组装并保存 raw.json（Pipeline 的唯一输出）
raw = {
    "meta": {
        "version": "2.0",
        "address": address,
        "zpid": zpid,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "market_key": market_key,
        "pipeline_duration_seconds": elapsed,
        "pipeline_log": f"logs/run_{date}_{time}.log",
    },
    "gov_data": gov_data,
    "property_data": property_data,
    "macro": macro,
    "micro": micro,
    "synthesis": synthesis,
}
save_json(raw, f"results/{zpid}_{date}_raw.json")

# ⏸️ Report Writer 暂停 — raw.json 是当前阶段的终点
```

### synthesizer.py 接口设计

```python
def synthesize(property_data: dict, macro: dict, micro: dict) -> dict:
    """
    Layer 3 — 交叉推理 + 对抗博弈。

    Returns:
        {
            "cross_insights": [...],       # 交叉推理洞察
            "blue_team": {...},            # 看多方论证
            "red_team": {...},             # 看空方论证
            "judge_verdict": {             # 裁判最终判决
                "executive_summary": "...",
                "final_action": "KILL|PURSUE|CONDITIONAL_PURSUE",
                "confidence": "HIGH|MEDIUM|LOW",
                "winning_side": "BLUE|RED|SPLIT",
                "unresolved_risks": [...],
                "conditions_to_pursue": [...]
            }
        }
    """
```

---

## 六、性能与成本考量

### API 调用数

| 版本 | 调用明细 | 预估耗时 |
|------|---------|---------|
| v1 | 2× agentic_call（L1 + L2） | ~3-5 min |
| v2 | 2× agentic_call（L1 + L2，但有强制数据源 → 搜索更深 → 可能略慢）+ 4× llm_call（Cross + Blue + Red + Judge，纯推理，无搜索） | ~8-15 min |

> L1/L2 因为强制数据源，agentic_call 的搜索轮数可能从 ~4 轮增加到 ~6-8 轮。
> 可以将 max_rounds 从 6 提高到 10 以确保强制源全部覆盖。

### 成本控制建议

- Layer 3 的 4 次调用中，Blue/Red/Judge **不需要联网搜索**（用已有数据推理即可）
- 建议 Blue/Red/Judge 用 **直接 LLM 调用**（非 agentic_call），省去搜索成本和时间
- 只有 Cross-Reference 可能需要联网（验证推理中的假设）
- 具体实现：Blue/Red/Judge 用 `litellm.completion()` 或类似直接调用

### 模型选择 — 多模型博弈策略

核心思想：**不同模型有不同的"性格"，用不同模型做对抗比同一模型自己辩论效果好得多。**

所有 Layer 3 调用使用 Reflexion 的 `llm_call()` 直接调用（不用 `agentic_call`），
因为 Blue/Red/Judge **不需要联网搜索**，只需要纯推理。省时间、省成本。

```python
from reflexion.providers import llm_call

result = llm_call(
    provider="deepinfra",                    # 或 "moonshot", "openclaw"
    model="Qwen/Qwen3.5-122B-A10B",         # 按角色分配
    messages=[...],
    tools=None,                              # 关键：不传 tools，纯推理
    max_tokens=4096,
)
```

| 步骤 | 调用方式 | 建议模型 | 理由 |
|------|---------|---------|------|
| Layer 1 (macro) | `agentic_call`（联网搜索） | openclaw / reflexion-sonnet | 需要搜索真实数据 + 强制数据源 |
| Layer 2 (micro) | `agentic_call`（联网搜索） | openclaw / reflexion-sonnet | 需要搜索真实数据 + 强制数据源 |
| Cross-Reference | `llm_call`（纯推理） | openclaw / reflexion-sonnet | 需要强逻辑链推理 |
| Blue Team | `llm_call`（纯推理） | moonshot / kimi-k2.5 | Kimi 擅长构建乐观论证，中文表达好 |
| Red Team | `llm_call`（纯推理） | deepinfra / Qwen3.5-122B-A10B | Qwen 擅长挑刺、找矛盾 |
| Judge | `llm_call`（纯推理） | openclaw / reflexion-opus | 需要最强综合判断力，Opus 做最终裁决 |

> 模型分配应可配置（在 `config/market_sources.json` 或单独的 `config/models.json` 中），
> 方便后续 A/B 测试不同模型组合。

---

## 七、测试策略

### 新增测试

| 文件 | 测试内容 |
|------|---------|
| `test_gov_fetcher.py` | 🆕 每个数据源独立 smoke test（见下方详细要求） |
| `test_market_config.py` | 🆕 市场匹配逻辑（已知市场、未知市场降级、城市名 fallback） |
| `test_synthesizer.py` | mock 数据 → 测试 cross_insights 结构、Blue/Red/Judge 输出格式 |
| `test_reporter_v2.py` | 新报告模板渲染测试（含 CONFIRMED/PARTIAL/NOT_AVAILABLE 标注） |

### Gov Fetcher Smoke Tests（每个数据源必须独立验证联通性）

**原则：每个 gov_fetcher 函数必须有对应的 smoke test，用真实 API 调用确认联通。**
标注 `@pytest.mark.smoke`，默认不跑，CI 或手动触发。

测试地址：21145 E Saddle Way, Queen Creek, AZ 85142
坐标：lat=33.2148, lon=-111.6340

```python
# test_gov_fetcher.py

@pytest.mark.smoke
def test_fema_flood_zone_smoke():
    """FEMA NFHL ArcGIS API — 真实调用，确认返回 flood zone"""
    result = fetch_fema_flood_zone(lat=33.2148, lon=-111.6340)
    assert result["status"] == "SUCCESS"
    assert result["flood_zone"] in ("X", "AE", "AH", "VE", "A", "D")
    assert isinstance(result["in_sfha"], bool)
    print(f"✅ FEMA: Zone {result['flood_zone']}, SFHA={result['in_sfha']}")

@pytest.mark.smoke
def test_maricopa_assessor_smoke():
    """Maricopa Assessor GIS API — 真实调用，确认返回业主+Parcel"""
    result = fetch_maricopa_parcel(lat=33.2148, lon=-111.6340)
    assert result["status"] == "SUCCESS"
    assert result["parcel_number"] is not None
    assert result["owner"] is not None
    assert len(result["owner"]) > 0
    print(f"✅ Assessor: Parcel={result['parcel_number']}, Owner={result['owner']}")

@pytest.mark.smoke
def test_maricopa_treasurer_smoke():
    """Maricopa Treasurer — 真实调用，确认返回税务状态。
    依赖 Assessor 返回的 Parcel Number。"""
    assessor = fetch_maricopa_parcel(lat=33.2148, lon=-111.6340)
    assert assessor["status"] == "SUCCESS", "Assessor must work first"
    result = fetch_maricopa_tax(assessor["parcel_number"])
    assert result["status"] in ("SUCCESS", "FAILED")
    # FAILED 可接受（可能需要 scraping），但不应崩溃
    print(f"✅ Treasurer: status={result['status']}")

@pytest.mark.smoke
def test_fetch_gov_sources_integration():
    """完整 fetch_gov_sources 集成测试 — 所有数据源串联"""
    property_data = {
        "latitude": 33.2148, "longitude": -111.6340,
        "state": "AZ", "county": "Maricopa", "city": "Queen Creek",
    }
    result = fetch_gov_sources(property_data, "az_maricopa")
    # FEMA 和 Assessor 必须 SUCCESS
    assert result["fema"]["status"] == "SUCCESS"
    assert result["assessor"]["status"] == "SUCCESS"
    # Treasurer/Recorder 可以 FAILED（实现中）但不崩溃
    assert result["treasurer"]["status"] in ("SUCCESS", "FAILED", "NEEDS_TESTING")
    assert result["recorder"]["status"] in ("SUCCESS", "FAILED", "NOT_CONFIGURED")
    print(f"✅ Integration: FEMA={result['fema']['flood_zone']}, "
          f"Owner={result['assessor']['owner']}")

@pytest.mark.smoke
def test_unknown_market_degraded():
    """未知市场降级运行 — FEMA 照查，county-specific 跳过，不崩溃"""
    property_data = {
        "latitude": 33.45, "longitude": -112.07,
        "state": "AZ", "county": "UnknownCounty", "city": "Somewhere",
    }
    result = fetch_gov_sources(property_data, None)
    # FEMA 全国通用，必须尝试
    assert result["fema"]["status"] in ("SUCCESS", "FAILED")
    # County-specific 应为 NOT_CONFIGURED
    assert result["assessor"]["status"] == "NOT_CONFIGURED"
    print(f"✅ Degraded mode: FEMA attempted, assessor skipped")
```

### 回归测试

- 用 Queen Creek 那份 v1 输出数据作为固定输入，跑 Layer 3 + 新 reporter
- 对比 v1 和 v2 报告，确保信息无丢失

---

## 八、语言与法律

### 8.1 语言规则

**所有 prompt、报告输出、disclaimer 一律英文。不做中英翻译。**

理由：
1. HML 行业纯英文生态，翻译感会降低专业信任
2. 英文 prompt → AI 自然使用 underwriting 行业术语（"no clouds on title"、"DSCR coverage"）
3. agentic_call 用英文 query 搜英文政府网站，搜索效率更高

具体要求：
- Layer 1/2 prompt：已是英文（不变）
- Layer 3 prompt（Cross-Reference、Blue/Red/Judge）：全英文
- Gov Data 注入段：全英文
- reporter.py 输出：全英文
- Disclaimer：全英文
- config 注释：英文

### 8.2 中文速览版（给创始人 review 用）

main.py 增加 `--zh` 可选参数：
```python
# 默认只输出英文报告
python main.py --url <zillow_url>
# → results/{zpid}_{date}.md（英文正式版）

# 加 --zh 同时生成中文速览版
python main.py --url <zillow_url> --zh
# → results/{zpid}_{date}.md（英文正式版）
# → results/{zpid}_{date}_zh.md（中文速览版）
```

中文速览版的实现：
- 英文报告生成完毕后，用一次 `llm_call()` 翻译关键部分
- 翻译范围：Executive Summary + Key Insights + Risk Debate Summary + Verdict
- Supporting Evidence（Layer 1/2 附录）**不翻译**（篇幅大、价值低）
- 顶部标注：`⚠️ 内部速览版 — 仅供创始人 review，不对外发送`

### 8.3 法律保护（Disclaimer）

**报告 disclaimer 从现有的 3 行弱声明升级为完整法律保护声明。**

替换现有的 `_DISCLAIMER`：

```
IMPORTANT LEGAL NOTICE AND DISCLAIMER

This report is generated by automated data aggregation and AI-assisted
analysis. It is provided strictly for preliminary informational purposes
and does NOT constitute:
  - A professional appraisal or property valuation
  - Legal advice or a title opinion
  - An inspection report or engineering assessment
  - A recommendation to lend, invest, or take any financial action

DATA LIMITATIONS:
  - Government data sources (FEMA, County Assessor, County Recorder)
    may contain errors, delays, or omissions. Data freshness is noted
    with query timestamps where available.
  - AI-generated analysis may contain inaccuracies or misinterpretations
  - This report is NOT a substitute for professional due diligence,
    including but not limited to: title search by a licensed title
    company, property inspection by a licensed inspector, appraisal
    by a licensed appraiser, and legal review by qualified counsel

NO WARRANTY: This report is provided "AS IS" without warranty of any
kind, express or implied. The author(s) make no representations
regarding the accuracy, completeness, or reliability of any information
contained herein.

LIMITATION OF LIABILITY: Under no circumstances shall the author(s)
be liable for any direct, indirect, incidental, or consequential
damages arising from the use of or reliance on this report.

By reading this report, the recipient acknowledges and agrees to
these terms.
```

**Gov Data 来源标注：** 报告中每一处使用 Gov API 数据的地方，必须标注数据来源和查询时间：

```
FEMA Flood Zone: X (Minimal Flood Hazard)
  Source: FEMA NFHL ArcGIS REST API | Queried: 2026-04-01T13:30:00Z
  Note: Flood zone designations may change. Verify with current FIRM
  panel before closing.
```

---

## 九、事实性零容忍（Anti-Hallucination）

**核心原则：报告中出现的每一个财务数字、人名、地址、日期，必须有可追溯的原始来源。没有来源的数字不得进入报告。**

---

### 9.1 已确认的幻觉案例（v2 必须修复）

v2 第一次跑（Queen Creek 55277871）发现的实际问题：

| 位置 | 报告内容 | 实际情况 | 性质 |
|------|---------|---------|------|
| Key Insight #1 | 21163 E Saddle Way 成交 $524,500 | keystoyourdreamsrealty.com 显示实际成交 $500,000 (Dec 1, 2025) | ❌ 数字错误 $24,500 差距 |
| Area Analysis | SpotCrime: 15 assaults, 17 burglaries | 验证时为 19 assaults, 14 burglaries | ⚠️ 动态数据无时间戳 |
| Phase 1 | "Palladino CONFIRMED via homes.com" | homes.com URL 返回 403，Tyler 无法验证 | ⚠️ URL 不可访问 |

---

### 9.2 根本原因分析

| 原因 | 说明 |
|------|------|
| AI 记错数字 | agentic_call 搜索到页面，但提取数字时出错（$524,500 vs $500,000）|
| 动态数据无时间戳 | SpotCrime 月度数字每月更新，但 AI 存的是无时间戳的快照 |
| URL 可访问但无原文 | AI 只存了 URL，没存原文 quote；URL 后来 403，无法验证 |

---

### 9.3 解决方案：三层防护

#### 层 1：raw_quote 强制存储（agentic_call 层）

每个 source 必须存三个字段，缺一不可：

```json
{
  "url": "https://www.keystoyourdreamsrealty.com/-/listing/AZ-ARMLS/6931380/...",
  "raw_quote": "Sold for $500,000 on Dec 1, 2025",
  "queried_at": "2026-04-01T15:42:00Z",
  "data_type": "sale_price"
}
```

**规则：**
- `raw_quote` = AI 实际读到的原文片段（≥10字，≤200字）
- 没有 `raw_quote` 的 source 标记 `"verified": false`
- 报告里引用未验证的数字时，自动加 `⚠️ unverified`

**Layer 1/2 prompt 追加要求：**
```
FOR EVERY NUMERICAL CLAIM, you MUST include the exact quote you read:
  ✅ "21163 E Saddle Way sold for $500,000 on Dec 1 2025 [source: keystoyourdreamsrealty.com, 
      raw_quote: 'Sold for $500,000 on Dec 1, 2025']"
  ❌ "21163 E Saddle Way sold for $524,500" (no quote = rejected)

If you cannot find the raw text that supports a number, DO NOT include that number.
Write "NOT FOUND" instead.
```

#### 层 2：动态数据时间戳（所有 AI 搜索数据）

所有动态来源（SpotCrime、Zillow 租金、Realtor.com DOM 等）必须标注：
```json
{
  "url": "https://spotcrime.com/AZ/Queen%20Creek/trends",
  "raw_quote": "19 assaults, 0 shootings, 14 burglaries, 18 thefts",
  "queried_at": "2026-04-01T15:42:00Z",
  "data_type": "crime_monthly",
  "note": "Monthly rolling data — may differ from report generation date"
}
```

报告中所有动态数字后面加 `(as of YYYY-MM-DD)`。

#### 层 3：关键数字二次验证（report_writer 层）

report_writer 生成报告时，对以下类型的数字**自动触发二次验证**：

```python
VERIFY_REQUIRED_TYPES = [
    "sale_price",       # 成交价格
    "rental_price",     # 租金
    "loan_amount",      # 贷款金额
    "arv_estimate",     # ARV 估值
    "tax_amount",       # 税额
    "owner_name",       # 业主姓名
]

def verify_claim(source: dict) -> bool:
    """二次验证：HTTP HEAD 请求确认 URL 仍可访问"""
    if source.get("data_type") not in VERIFY_REQUIRED_TYPES:
        return True
    try:
        resp = requests.head(source["url"], timeout=5, allow_redirects=True)
        source["url_alive"] = resp.status_code == 200
        return source["url_alive"]
    except:
        source["url_alive"] = False
        return False
```

URL 不可访问时，报告中该数字标注：
```
$500,000 ⚠️ (source URL inaccessible as of report generation — raw quote preserved)
```

---

### 9.4 Claim 可信度分级（报告展示）

| 标注 | 含义 | 触发条件 |
|------|------|---------|
| ✅ CONFIRMED | 程序直调 API，硬数据 | Gov Fetcher 成功 |
| ✅ VERIFIED | AI 搜索到，有 raw_quote，URL 可访问 | raw_quote + url_alive = True |
| ⚠️ UNVERIFIED | AI 搜索到，无 raw_quote 或 URL 不可访问 | raw_quote 缺失或 url_alive = False |
| ❌ NOT FOUND | AI 尝试搜索但未找到 | AI 明确写 NOT FOUND |

**UNVERIFIED 数字不得出现在 Executive Summary 和 Key Insights 中。**  
只能出现在 Supporting Evidence 附录里，并加注标记。

---

### 9.5 AI Prompt 硬规则（追加到所有 Layer 1/2/3 prompt）

```
FACTUAL INTEGRITY RULES — NON-NEGOTIABLE:

1. NEVER invent or estimate a number. If you cannot find the exact figure,
   write "NOT FOUND" and explain what you searched.

2. For every dollar amount ($), date, or person's name you include:
   - Quote the exact text you read (raw_quote)
   - Include the URL where you found it

3. If a URL returned an error or the page was empty, say so explicitly:
   "Attempted [URL] — returned 403/empty. Data not verified."

4. Dynamic data (crime stats, rental listings, DOM) must include the date
   you retrieved it: "as of 2026-04-01"

5. When two sources disagree, cite BOTH and flag the discrepancy:
   "Zillow shows $3,797/month; rentZestimate shows $2,506/month — discrepancy noted"

VIOLATION = hallucination. One hallucinated number invalidates the entire section.
```

---

### 9.6 raw.json 结构更新（sources 字段）

每个 source 对象从：
```json
{"url": "...", "note": "..."}
```
升级为：
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

`verified = raw_quote is not None AND len(raw_quote) >= 10`

---

## 十、不做什么（v2 边界）

1. ❌ 不做 Recorder scraping（Cloudflare 保护，复杂度高，留给 v3 或等客户需求确认）
2. ❌ 不做 PDF 输出（Markdown 先跑通）
3. ❌ 不做批量处理（一次跑一个地址）
4. ❌ 不做 Web UI（CLI 优先）
5. ❌ 不改 Apify/Zillow 抓取逻辑
6. ❌ 不接第三方付费数据源（Title search API 等，等客户反馈后再决定）

---

## 十、验收标准

### Pipeline 验收（素材包）

1. `python main.py --url <zillow_url> --collect-only` 跑通全流程，输出 `_raw.json`
2. raw.json 包含完整的 `property_data` / `gov_data` / `macro` / `micro` / `synthesis`
3. `gov_data.fema.status == "SUCCESS"` 且 `flood_zone` 有值
4. `gov_data.assessor.status in ("SUCCESS", "FAILED")`（不崩溃）
5. `layer3_synthesis` 包含 `cross_insights`（≥2个）+ `blue_team` + `red_team` + `judge_verdict`
6. 未知市场（非 az_maricopa）降级运行不崩溃，FEMA 仍可查
7. 每个 Gov Fetcher 数据源有独立 smoke test 通过

### Borrower Profile 验收（HML 核心）

8. `micro.phase_results.phase1_ownership.borrower_risk_profile` 字段存在
9. `is_professional_investor` 有明确 true/false（不允许 null）
10. `estimated_properties_held` 有数值（即使是估算，必须给出，不允许 null）
11. `borrower_risk_level` 有明确 LOW/MEDIUM/HIGH
12. `cross_lender_exposure` 如果是 UNKNOWN，必须在 `cross_lender_note` 里说明尝试了什么方法

### 事实性验收（Anti-Hallucination — 必须全部通过）

8. raw.json 中所有 sources 包含 `raw_quote`、`queried_at`、`data_type` 三个字段
9. `verified = true` 的 source 占全部 sources 的 ≥ 80%
10. Executive Summary 和 Key Insights 中**零个** `⚠️ UNVERIFIED` 标注
11. 所有动态数据（SpotCrime、租金、DOM）带 `(as of YYYY-MM-DD)` 时间戳
12. 报告中每个 dollar amount 在 raw.json 中有对应的 raw_quote 可追溯

### Report Writer 验收

⏸️ **DEFERRED — 当前阶段不验收 report_writer。**
raw.json 完备后单独立项。
