"""
src/gov_fetcher.py — Track A: 政府 REST API 直调，获取硬数据
"""
import logging

import requests

logger = logging.getLogger(__name__)

# ─── FEMA (全国通用) ──────────────────────────────────────────────────────────


def fetch_fema_flood_zone(lat: float, lon: float) -> dict:
    """FEMA National Flood Hazard Layer — ArcGIS REST API。
    坐标注意：geometry 格式是 lon,lat（先经度后纬度）。
    """
    url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        features = data.get("features", [])
        if features:
            attrs = features[0]["attributes"]
            return {
                "status": "SUCCESS",
                "flood_zone": attrs.get("FLD_ZONE"),
                "zone_subtype": attrs.get("ZONE_SUBTY"),
                "in_sfha": attrs.get("SFHA_TF") == "T",
                "source": "FEMA NFHL ArcGIS REST API",
                "query": {"lat": lat, "lon": lon},
            }
        return {"status": "FAILED", "error": "No features returned for coordinates"}
    except Exception as exc:
        logger.warning("FEMA fetch failed: %s", exc)
        return {"status": "FAILED", "error": str(exc)}


# ─── Maricopa County Assessor ─────────────────────────────────────────────────


def fetch_maricopa_parcel(lat: float, lon: float) -> dict:
    """Maricopa County Assessor — GIS Parcel Query。
    坐标注意：geometry 格式是 lon,lat（先经度后纬度）。
    """
    url = "https://gis.maricopa.gov/arcgis/rest/services/Assessor/AssessorParcels/MapServer/0/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "APN,OWNER,OWNER2,SITUS,LEGAL,ASSESSED_FULL_CASH",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
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
    except Exception as exc:
        logger.warning("Maricopa Assessor fetch failed: %s", exc)
        return {"status": "FAILED", "error": str(exc)}


def fetch_maricopa_tax(parcel_number: str) -> dict:
    """Maricopa County Treasurer — 税务状态查询。
    status=NEEDS_TESTING: 接口待验证，先返回占位结果。
    """
    return {
        "status": "NEEDS_TESTING",
        "source": "Maricopa County Treasurer",
        "parcel_number": parcel_number,
    }


# ─── 统一入口 ──────────────────────────────────────────────────────────────────


def fetch_gov_sources(property_data: dict, market_key: str | None) -> dict:
    """
    程序直调政府 REST API，获取强制数据源。

    Args:
        property_data: Apify 返回的 Zillow 数据（含 latitude/longitude）
        market_key: 市场标识（如 "phoenix_maricopa"），None 时只查全国通用源

    Returns:
        dict with fema, assessor, treasurer, recorder results
        每项含 status: SUCCESS|FAILED|NOT_CONFIGURED|SKIPPED_DEPENDENCY
    """
    lat = property_data.get("latitude")
    lon = property_data.get("longitude")

    result: dict = {}

    # Track A1: FEMA（全国通用，无论 market_key）
    if lat is not None and lon is not None:
        logger.info("Fetching FEMA flood zone for (%s, %s)", lat, lon)
        result["fema"] = fetch_fema_flood_zone(lat, lon)
    else:
        result["fema"] = {"status": "FAILED", "error": "Missing latitude/longitude in property_data"}

    # Track A2: County-specific（只有匹配到 phoenix_maricopa 时才运行）
    if market_key != "phoenix_maricopa":
        result["assessor"] = {"status": "NOT_CONFIGURED"}
        result["treasurer"] = {"status": "NOT_CONFIGURED"}
        result["recorder"] = {"status": "NOT_CONFIGURED"}
        return result

    # Maricopa County Assessor
    if lat is not None and lon is not None:
        logger.info("Fetching Maricopa Assessor for (%s, %s)", lat, lon)
        assessor_result = fetch_maricopa_parcel(lat, lon)
    else:
        assessor_result = {"status": "FAILED", "error": "Missing latitude/longitude"}

    result["assessor"] = assessor_result

    # Treasurer depends on Assessor (needs parcel_number)
    if assessor_result.get("status") == "SUCCESS":
        parcel_number = assessor_result.get("parcel_number")
        if parcel_number:
            result["treasurer"] = fetch_maricopa_tax(parcel_number)
        else:
            result["treasurer"] = {"status": "FAILED", "error": "No parcel number from Assessor"}
    else:
        result["treasurer"] = {"status": "SKIPPED_DEPENDENCY"}

    # Recorder: NOT_CONFIGURED (Cloudflare protection, no direct API)
    result["recorder"] = {"status": "NOT_CONFIGURED"}

    return result
