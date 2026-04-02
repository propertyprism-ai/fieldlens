"""
src/market_config.py — 按房产地址匹配市场配置
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "market_sources.json"

# city → market key 查找表（Maricopa County 主要城市）
_CITY_LOOKUP: dict[str, str] = {
    "phoenix": "phoenix_maricopa",
    "mesa": "phoenix_maricopa",
    "queen creek": "phoenix_maricopa",
    "gilbert": "phoenix_maricopa",
    "chandler": "phoenix_maricopa",
    "scottsdale": "phoenix_maricopa",
    "tempe": "phoenix_maricopa",
    "apache junction": "phoenix_maricopa",
    "surprise": "phoenix_maricopa",
    "peoria": "phoenix_maricopa",
    "glendale": "phoenix_maricopa",
    "avondale": "phoenix_maricopa",
    "goodyear": "phoenix_maricopa",
    "buckeye": "phoenix_maricopa",
    "maricopa": "phoenix_maricopa",
}

# county → market key 查找表
_COUNTY_LOOKUP: dict[str, str] = {
    "maricopa county": "phoenix_maricopa",
    "maricopa": "phoenix_maricopa",
}


def _load_sources() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def get_market_config(property_data: dict) -> dict | None:
    """
    按房产数据匹配市场配置。

    优先级：county 字段 → city 字段 → None（降级，不崩溃）

    Args:
        property_data: fetch_property() 返回的房产 dict（或任意含 county/city 的 dict）

    Returns:
        market_sources.json 中对应市场的完整配置 dict，或 None（未知市场）
    """
    if not property_data:
        return None

    sources = _load_sources()

    # 优先：county 匹配
    county = (property_data.get("county") or "").strip().lower()
    if county:
        market_key = _COUNTY_LOOKUP.get(county)
        if market_key and market_key in sources:
            return sources[market_key]

    # Fallback：city 匹配
    city = (property_data.get("city") or "").strip().lower()
    if city:
        market_key = _CITY_LOOKUP.get(city)
        if market_key and market_key in sources:
            return sources[market_key]

    return None
