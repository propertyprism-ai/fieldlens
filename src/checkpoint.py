"""
src/checkpoint.py — Pipeline 检查点保存与恢复

检查点目录：results/checkpoints/{run_id}/
每层完成后保存为 layer1_macro.json / layer2_micro.json / layer3_synthesis.json /
                  property_data.json / gov_data.json
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 基准目录
RESULTS_BASE = Path(__file__).parent.parent / "results"


def save_checkpoint(run_id: str, layer: str, data: dict) -> Path:
    """
    保存检查点。

    Args:
        run_id:  运行标识，如 "{zpid}_{YYYY-MM-DD_HHMMSS}"
        layer:   层名，如 "layer1_macro", "layer2_micro", "layer3_synthesis",
                 "property_data", "gov_data"
        data:    要保存的 dict

    Returns:
        保存的 .json 文件路径
    """
    ckpt_dir = RESULTS_BASE / "checkpoints" / run_id
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    file_path = ckpt_dir / f"{layer}.json"
    file_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug("Checkpoint saved: %s", file_path)
    return file_path


def load_checkpoint(run_id: str, layer: str) -> dict | None:
    """
    加载检查点。

    Args:
        run_id:  运行标识
        layer:   层名

    Returns:
        已保存的 dict；文件不存在返回 None
    """
    file_path = RESULTS_BASE / "checkpoints" / run_id / f"{layer}.json"
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def list_checkpoints(run_id: str) -> list[str]:
    """
    返回已完成的所有层名列表。

    Args:
        run_id:  运行标识

    Returns:
        已存在检查点文件的层名列表（如 ["layer1_macro", "layer2_micro"]）
    """
    ckpt_dir = RESULTS_BASE / "checkpoints" / run_id
    if not ckpt_dir.exists():
        return []
    return [
        p.stem
        for p in ckpt_dir.iterdir()
        if p.is_file() and p.suffix == ".json"
    ]
