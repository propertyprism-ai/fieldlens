#!/usr/bin/env python3.12
"""
main.py — fieldlens CLI 入口

Usage:
  python main.py --url <zillow_url>                       # 全流程 pipeline + 报告
  python main.py --url <zillow_url> --collect-only         # 只 pipeline，输出 raw.json
  python main.py --report results/xxx_raw.json              # 只生成报告
  python main.py --url <zillow_url> --zh                   # 同时生成中文速览版
  python main.py --resume <zpid>_<YYYY-MM-DD_HHMMSS>       # 从检查点恢复，跳过已完成层
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path


def _elapsed(t0: float) -> str:
    s = int(time.time() - t0)
    return f"{s//60}m{s%60:02d}s" if s >= 60 else f"{s}s"


def _notify(msg: str) -> None:
    """Send Telegram notification via openclaw (fail silently)."""
    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "telegram",
             "--account", "dev",
             "--target", "7534802214",
             "--message", msg],
            timeout=15,
            capture_output=True,
        )
    except Exception:
        pass


def _run_pipeline(args, log, run_id: str | None = None):
    """
    Run full data pipeline, return (property_data, gov_data, macro, micro, synthesis, zpid).

    If run_id is provided, checkpoints are saved after each layer completes.
    """
    from src.fetcher import fetch_property, FetchError
    from src.gov_fetcher import fetch_gov_sources
    from src.investigator import investigate_macro, investigate_micro
    from src.market_config import get_market_config
    from src.synthesizer import synthesize
    from src.checkpoint import save_checkpoint, load_checkpoint, list_checkpoints

    total_start = time.time()

    # Determine which layers are already complete (resume mode)
    completed = set(list_checkpoints(run_id)) if run_id else set()

    # ── Step 1: Fetch ──────────────────────────────────────────
    t = time.time()
    if "property_data" in completed:
        log.info("[1/5] Fetching property data ... SKIPPED (checkpoint found)")
        property_data = load_checkpoint(run_id, "property_data")
    else:
        log.info("[1/5] Fetching property data from Zillow (Apify)...")
        try:
            property_data = fetch_property(args.url)
        except FetchError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        if run_id:
            save_checkpoint(run_id, "property_data", property_data)

    address = property_data.get("address", "Unknown")
    price = property_data.get("price")
    beds = property_data.get("bedrooms")
    baths = property_data.get("bathrooms")
    price_str = f"${price:,}" if price else "N/A"
    log.info("  ✓ %s", address)
    log.info("  ✓ %s | %sbd/%sba | built %s [%s]",
             price_str, beds, baths, property_data.get('yearBuilt', 'N/A'), _elapsed(t))
    _notify(
        f"[1/5] ✅ Apify 数据获取完成（{_elapsed(t)}）\n"
        f"  地址：{address}\n"
        f"  价格：{price_str} | {beds}bd/{baths}ba | 建于{property_data.get('yearBuilt', 'N/A')}"
    )

    # ── Step 1.5: Gov Fetcher (Track A) ────────────────────────
    t = time.time()
    market_config = get_market_config(property_data)
    market_key = None
    if market_config:
        # Resolve market_key from config filename lookup
        if "Maricopa" in market_config.get("market_name", ""):
            market_key = "phoenix_maricopa"
        log.info("  ✓ Market: %s → key=%s", market_config.get('market_name', 'Unknown'), market_key)
    else:
        log.warning("  ⚠ Market config not found — gov sources degraded")

    log.info("[1.5/5] Fetching government data (Track A)...")
    gov_data = fetch_gov_sources(property_data, market_key=market_key)
    if run_id:
        save_checkpoint(run_id, "gov_data", gov_data)
    fema_status = gov_data.get("fema", {}).get("status", "N/A")
    assessor_status = gov_data.get("assessor", {}).get("status", "N/A")
    log.info("  ✓ FEMA=%s | Assessor=%s [%s]", fema_status, assessor_status, _elapsed(t))
    if gov_data.get("assessor", {}).get("status") == "SUCCESS":
        owner = gov_data["assessor"].get("owner", "N/A")
        parcel = gov_data["assessor"].get("parcel_number", "N/A")
        log.info("  ✓ Owner=%s | Parcel=%s", owner, parcel)
    _notify(
        f"[1.5/5] ✅ Gov 数据获取完成（{_elapsed(t)}）\n"
        f"  FEMA: {fema_status}\n"
        f"  Assessor: {assessor_status}"
    )

    # ── Step 2: Layer 1 ────────────────────────────────────────
    t = time.time()
    if "layer1_macro" in completed:
        log.info("[2/5] Layer 1 — Macro area investigation ... SKIPPED (checkpoint found)")
        macro = load_checkpoint(run_id, "layer1_macro")
    else:
        log.info("[2/5] Layer 1 — Macro area investigation (Reflexion agentic search)...")
        macro = investigate_macro(address, gov_data=gov_data)
        if run_id:
            save_checkpoint(run_id, "layer1_macro", macro)
    risk = macro.get('risk_level', 'UNKNOWN')
    confidence = macro.get('data_confidence', 'N/A')
    findings_count = len(macro.get('key_findings', []))
    log.info("  ✓ Risk Level: %s | Data confidence: %s/100 | Findings: %d [%s]",
             risk, confidence, findings_count, _elapsed(t))
    findings = macro.get('key_findings', [])
    finding1 = findings[0] if len(findings) > 0 else 'N/A'
    finding2 = findings[1] if len(findings) > 1 else 'N/A'
    _notify(
        f"[2/5] ✅ Layer 1 宏观区域完成（{_elapsed(t)}）\n"
        f"  风险等级：{risk}\n"
        f"  数据置信度：{confidence}/100\n"
        f"  关键发现（前2条）：\n"
        f"  • {finding1}\n"
        f"  • {finding2}"
    )

    # ── Step 3: Layer 2 ────────────────────────────────────────
    t = time.time()
    if "layer2_micro" in completed:
        log.info("[3/5] Layer 2 — Micro property forensics ... SKIPPED (checkpoint found)")
        micro = load_checkpoint(run_id, "layer2_micro")
    else:
        log.info("[3/5] Layer 2 — Micro property forensics (Reflexion agentic search)...")
        micro = investigate_micro(property_data, macro, gov_data=gov_data)
        if run_id:
            save_checkpoint(run_id, "layer2_micro", micro)
    verdict = micro.get("verdict", {})
    action = verdict.get('recommended_action', 'UNKNOWN')
    kill = verdict.get('kill_switch', 'N/A')
    log.info("  ✓ Verdict: %s | Kill switch: %s [%s]", action, kill, _elapsed(t))
    summary = verdict.get('one_line_summary', '')
    if summary:
        log.info("  ✓ %s", summary[:100])
    _notify(
        f"[3/5] ✅ Layer 2 微观法证完成（{_elapsed(t)}）\n"
        f"  判决：{action} | Kill switch：{kill}\n"
        f"  摘要：{summary[:100] if summary else 'N/A'}"
    )

    # ── Step 4: Layer 3 ────────────────────────────────────────
    t = time.time()
    if "layer3_synthesis" in completed:
        log.info("[4/5] Layer 3 — Cross-reference + Red/Blue/Judge debate ... SKIPPED (checkpoint found)")
        synthesis = load_checkpoint(run_id, "layer3_synthesis")
    else:
        log.info("[4/5] Layer 3 — Cross-reference + Red/Blue/Judge debate...")
        synthesis = synthesize(property_data, macro, micro, gov_data=gov_data)
        if run_id:
            save_checkpoint(run_id, "layer3_synthesis", synthesis)
    judge_verdict = synthesis.get("judge_verdict", {})
    final_action = judge_verdict.get('final_action', 'UNKNOWN')
    winning_side = judge_verdict.get('winning_side', 'N/A')
    insights_count = len(synthesis.get('cross_insights', []))
    log.info("  ✓ Final: %s | Winner: %s | Insights: %d [%s]",
             final_action, winning_side, insights_count, _elapsed(t))
    exec_summary = judge_verdict.get('executive_summary', '')
    _notify(
        f"[4/5] ✅ Layer 3 综合分析完成（{_elapsed(t)}）\n"
        f"  最终结论：{final_action} | 胜方：{winning_side}\n"
        f"  交叉洞察数：{insights_count}\n"
        f"  执行摘要：{exec_summary[:100] if exec_summary else 'N/A'}..."
    )

    return property_data, gov_data, macro, micro, synthesis, total_start


def main():
    parser = argparse.ArgumentParser(
        description="fieldlens — PropertyPrism Risk Intelligence Report Generator"
    )
    parser.add_argument("--url", help="Zillow property URL")
    parser.add_argument("--collect-only", action="store_true",
                        help="Run pipeline only, output raw.json (no report)")
    parser.add_argument("--report", metavar="RAW_JSON",
                        help="Generate report from existing raw.json file")
    parser.add_argument("--zh", action="store_true",
                        help="Also generate Chinese summary version")
    parser.add_argument("--resume", metavar="RUN_ID",
                        help="Resume from checkpoint: zpid_YYYY-MM-DD_HHMMSS")
    args = parser.parse_args()

    # ── Mode: --report only ────────────────────────────────────
    if args.report and not args.url:
        from src.report_writer import write_report_from_file, write_report_zh
        import json as _json

        raw_path = Path(args.report)
        if not raw_path.exists():
            print(f"ERROR: {raw_path} not found", file=sys.stderr)
            sys.exit(1)

        t = time.time()
        print(f"[report] Generating report from {raw_path}...")
        report = write_report_from_file(str(raw_path))

        report_path = raw_path.parent / raw_path.name.replace("_raw.json", ".md")
        report_path.write_text(report, encoding="utf-8")
        print(f"✅ Report saved: {report_path} [{_elapsed(t)}]")

        if args.zh:
            bundle = _json.loads(raw_path.read_text(encoding="utf-8"))
            zh_report = write_report_zh(bundle)
            zh_path = raw_path.parent / raw_path.name.replace("_raw.json", "_zh.md")
            zh_path.write_text(zh_report, encoding="utf-8")
            print(f"✅ Chinese summary saved: {zh_path}")

        print(report_path)
        return

    # ── Mode: --url required for pipeline ─────────────────────
    if not args.url and not args.resume:
        parser.print_help()
        sys.exit(1)

    from src.logger import init_logger
    from src.reporter import build_raw_bundle
    from src.report_writer import write_report, write_report_zh
    from src.checkpoint import list_checkpoints

    # Resume mode: load run_id from --resume
    if args.resume:
        run_id = args.resume
        completed = set(list_checkpoints(run_id))
        # Extract zpid from run_id (first part before _)
        zpid = run_id.split("_")[0] if "_" in run_id else run_id
        log = init_logger(zpid, run_id.split("_", 1)[1] if "_" in run_id else "")
        log.info("Resume mode: run_id=%s, completed layers=%s", run_id, completed)
        # URL still required if property_data not cached
        if "property_data" not in completed and not args.url:
            print("ERROR: --url required when property_data checkpoint is missing", file=sys.stderr)
            sys.exit(1)
        # Update args.url if missing (needed for fetch_property if not cached)
        if not args.url:
            args.url = None  # will only be used if property_data not cached
    else:
        run_id = None
        # Temporary logger (zpid unknown until fetch completes)
        today_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        log = init_logger("pending", today_str)

    property_data, gov_data, macro, micro, synthesis, total_start = _run_pipeline(args, log, run_id=run_id)

    zpid = property_data.get("zpid", "unknown")

    # In resume mode, use the original run_id's timestamp for output path consistency
    if args.resume and "_" in args.resume:
        today_str = args.resume.split("_", 1)[1]
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    # ── Step 5a: Save raw.json ──────────────────────────────────
    bundle = build_raw_bundle(property_data, macro, micro, synthesis, gov_data)
    raw_path = results_dir / f"{zpid}_{today_str}_raw.json"
    raw_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("  ✓ Raw bundle saved: %s", raw_path)

    if args.collect_only:
        print(f"\n{'='*60}")
        print(f"✅ Raw bundle saved: {raw_path}")
        print(f"   Total time: {_elapsed(total_start)}")
        print(f"{'='*60}")
        print(raw_path)
        _notify(
            f"[5/5] ✅ 数据收集完成（总耗时：{_elapsed(total_start)}）\n"
            f"  raw.json 路径：{raw_path}"
        )
        return

    # ── Step 5b: Generate report ────────────────────────────────
    t = time.time()
    log.info("[5/5] Generating report...")
    report = write_report(bundle)

    report_path = results_dir / f"{zpid}_{today_str}.md"
    report_path.write_text(report, encoding="utf-8")

    log.info("  ✓ %d chars [%s]", len(report), _elapsed(t))

    if args.zh:
        zh_report = write_report_zh(bundle)
        zh_path = results_dir / f"{zpid}_{today_str}_zh.md"
        zh_path.write_text(zh_report, encoding="utf-8")
        log.info("  ✓ Chinese summary saved: %s", zh_path)

    print(f"\n{'='*60}")
    print(f"✅ Report saved: {report_path}")
    print(f"   Total time: {_elapsed(total_start)}")
    print(f"{'='*60}")
    print(report_path)

    _notify(
        f"[5/5] ✅ 报告生成完成（总耗时：{_elapsed(total_start)}）\n"
        f"  报告路径：{report_path}\n"
        f"  报告大小：{len(report):,}字符"
    )


if __name__ == "__main__":
    main()
