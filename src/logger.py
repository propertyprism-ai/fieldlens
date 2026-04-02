"""
src/logger.py — 统一日志模块
"""
import logging
from datetime import datetime
from pathlib import Path

_LOGS_DIR = Path(__file__).parent.parent / "logs"


def init_logger(zpid: str, date_str: str) -> logging.Logger:
    """
    初始化并返回带双输出的 logger。

    Args:
        zpid:     房源 ZPID（用于日志文件命名）
        date_str: 日期字符串 YYYY-MM-DD（用于日志文件命名）

    Returns:
        logging.Logger，同时输出到文件（DEBUG）和控制台（INFO）
    """
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    time_str = datetime.now().strftime("%H%M%S")
    log_filename = f"run_{zpid}_{date_str}_{time_str}.log"
    log_path = _LOGS_DIR / log_filename

    logger_name = f"fieldlens.{zpid}.{time_str}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（多次调用时）
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # FileHandler — DEBUG 级，完整详细
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # StreamHandler — INFO 级，简洁
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)

    return logger
