"""conftest.py — pytest 配置，注册自定义 mark"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="Run smoke tests (real API calls)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test requiring real API access"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-smoke"):
        return
    skip_smoke = pytest.mark.skip(reason="smoke tests skipped by default (use --run-smoke)")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip_smoke)
