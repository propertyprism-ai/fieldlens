"""
test_logger.py — L1 单元测试，logger.py
"""
import re
import logging


def test_logger_creates_file(tmp_path, monkeypatch):
    """init_logger 后验证 log 文件在 logs/ 目录创建"""
    import src.logger as logger_module
    monkeypatch.setattr(logger_module, "_LOGS_DIR", tmp_path)

    logger = logger_module.init_logger("12345", "2026-04-01")

    # Close handlers to release file handles
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)

    log_files = list(tmp_path.glob("run_12345_*.log"))
    assert len(log_files) == 1


def test_logger_writes_to_file(tmp_path, monkeypatch):
    """写一条 INFO log → 验证文件有内容"""
    import src.logger as logger_module
    monkeypatch.setattr(logger_module, "_LOGS_DIR", tmp_path)

    logger = logger_module.init_logger("99999", "2026-04-01")
    logger.info("Test log entry from test_logger_writes_to_file")

    for h in logger.handlers[:]:
        h.flush()

    log_files = list(tmp_path.glob("run_99999_*.log"))
    assert log_files
    content = log_files[0].read_text(encoding="utf-8")

    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)

    assert "Test log entry" in content


def test_logger_path_format(tmp_path, monkeypatch):
    """验证文件名格式 run_{zpid}_{date}_{time}.log"""
    import src.logger as logger_module
    monkeypatch.setattr(logger_module, "_LOGS_DIR", tmp_path)

    logger = logger_module.init_logger("55555", "2026-04-01")

    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)

    log_files = list(tmp_path.glob("*.log"))
    assert log_files
    filename = log_files[0].name
    # Pattern: run_55555_2026-04-01_HHMMSS.log
    assert re.match(r"run_55555_2026-04-01_\d{6}\.log", filename), \
        f"Unexpected filename: {filename}"
