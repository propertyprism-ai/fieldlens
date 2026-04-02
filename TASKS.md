# TASKS.md — fieldlens 执行清单

## Sprint 1 — MVP 流水线 ✅ 完成 (2026-04-01)

- [x] 创建 `src/__init__.py`
- [x] 实现 `src/fetcher.py` — extract_core_fields() + fetch_property() + FetchError
- [x] 实现 `src/investigator.py` — investigate_macro() + investigate_micro() + _parse_json_response()
- [x] 实现 `src/reporter.py` — generate_report()
- [x] 实现 `main.py` — CLI 入口 `python main.py --url <zillow_url>`
- [x] 创建 `requirements.txt`
- [x] L1 单元测试全绿（36/36）
- [x] Smoke 测试：investigate_macro 真实调用通过

## Sprint 2 — v2 Layer 3 升级 ✅ 完成 (2026-04-01)

- [x] `src/synthesizer.py` — synthesize() 串联 4 次 llm_call（cross/blue/red/judge）
- [x] `prompts/layer3_cross_reference.txt` / `layer3_blue_team.txt` / `layer3_red_team.txt` / `layer3_judge.txt`
- [x] `prompts/layer1_macro.txt` — 追加 data_confidence + unknowns
- [x] `prompts/layer2_micro.txt` — 每个 Phase 追加 cross_reference_note
- [x] `src/investigator.py` — 向后兼容新字段
- [x] `src/reporter.py` — 完全重写（Executive Summary 前置，洞察驱动）
- [x] `main.py` — 5 步 CLI 流水线（含 Layer 3）
- [x] `test_synthesizer.py` — 7 个 L1 单元测试全绿
- [x] `test_reporter_v2.py` — 6 个 v2 报告模板测试全绿
- [x] 全量回归：55/55 通过

## Sprint 3 — 待定

- [ ] 集成测试：APIFY_API_TOKEN 可用时跑完整 5 步 smoke pipeline
- [ ] `config/market_config.tsv` — 各市场参数配置
- [ ] 错误重试逻辑（llm_call 超时处理）
- [ ] Smoke 测试：Layer 3 真实调用验证

