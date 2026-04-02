"""
src/fetcher.py — Apify Zillow 数据拉取 + 清洗

Public API:
    fetch_property(url: str) -> dict
    FetchError (exception)
    extract_core_fields(listing: dict) -> dict | None  (复用逻辑，也可直接调用)
"""
import os
from apify_client import ApifyClient


class FetchError(Exception):
    """Apify 调用失败或数据为空"""


# ─── 数据清洗辅助函数（移植自 property-finder/1_pull_details.py）────────────


def _extract_address(address_obj: dict) -> str | None:
    if not address_obj:
        return None
    parts = []
    if address_obj.get("streetAddress"):
        parts.append(address_obj["streetAddress"])
    if address_obj.get("city"):
        parts.append(address_obj["city"])
    if address_obj.get("state"):
        parts.append(address_obj["state"])
    if address_obj.get("zipcode"):
        parts.append(str(address_obj["zipcode"]))
    return ", ".join(parts) if parts else None


def _clean_price_history(price_history: list) -> list:
    if not price_history:
        return []
    return [
        {"date": e.get("date"), "price": e.get("price"), "event": e.get("event")}
        for e in price_history
    ]


def _extract_tax_from_history(tax_history: list) -> float | None:
    if not tax_history or not isinstance(tax_history, list):
        return None
    for entry in tax_history:
        if not isinstance(entry, dict):
            continue
        tax_paid = entry.get("taxPaid")
        if tax_paid is None or tax_paid == "":
            continue
        try:
            value = float(tax_paid)
            if value > 0:
                return value
        except (ValueError, TypeError):
            continue
    return None


def _extract_school_ratings(schools: list) -> list:
    if not schools or not isinstance(schools, list):
        return []
    result = []
    for s in schools:
        if not isinstance(s, dict):
            continue
        name = s.get("name", "Unknown School")
        rating = s.get("rating")
        if rating is not None and str(rating).strip() != "":
            try:
                result.append(f"{name}: {float(rating)}/10")
            except (ValueError, TypeError):
                result.append(f"{name}: N/A")
        else:
            result.append(f"{name}: N/A")
    return result


def _calculate_rent_range(rent_zestimate, low_pct, high_pct):
    if not rent_zestimate:
        return None, None
    try:
        rv = float(rent_zestimate)
        lo = float(low_pct) if low_pct not in (None, "") else 0
        hi = float(high_pct) if high_pct not in (None, "") else 0
        return round(rv * (1 - lo / 100), 2), round(rv * (1 + hi / 100), 2)
    except (ValueError, TypeError):
        return None, None


def extract_core_fields(listing: dict) -> dict | None:
    """从单个 Zillow listing 提取核心字段（清洗后）"""
    if not isinstance(listing, dict):
        return None

    reso = listing.get("resoFacts") or {}

    tax_annual = _extract_tax_from_history(listing.get("taxHistory"))
    if tax_annual is None:
        fallback = reso.get("taxAnnualAmount")
        if fallback:
            try:
                tax_annual = float(fallback)
            except (ValueError, TypeError):
                tax_annual = None

    rent_min, rent_max = _calculate_rent_range(
        listing.get("rentZestimate"),
        listing.get("restimateLowPercent"),
        listing.get("restimateHighPercent"),
    )

    hoa_fee = reso.get("hoaFee")
    if hoa_fee is None or hoa_fee == "":
        hoa_fee = 0
    else:
        try:
            hoa_fee = float(hoa_fee)
        except (ValueError, TypeError):
            hoa_fee = 0

    address_obj = listing.get("address") or {}
    city = address_obj.get("city") if isinstance(address_obj, dict) else None
    state = address_obj.get("state") if isinstance(address_obj, dict) else None

    return {
        "zpid": listing.get("zpid"),
        "address": _extract_address(listing.get("address")),
        "url": listing.get("hdpUrl"),
        "price": listing.get("price"),
        "taxAnnualAmount": tax_annual,
        "rentZestimate": listing.get("rentZestimate"),
        "rentMin": rent_min,
        "rentMax": rent_max,
        "hoaFee": hoa_fee,
        "yearBuilt": listing.get("yearBuilt"),
        "bedrooms": listing.get("bedrooms"),
        "bathrooms": listing.get("bathrooms"),
        "livingArea": listing.get("livingArea") or reso.get("livingArea"),
        "lotSize": listing.get("lotSize") or reso.get("lotAreaValue"),
        "homeType": listing.get("homeType"),
        "schoolRating": _extract_school_ratings(listing.get("schools")),
        "daysOnZillow": listing.get("daysOnZillow"),
        "homeStatus": listing.get("homeStatus"),
        "priceHistory": _clean_price_history(listing.get("priceHistory")),
        "description": listing.get("description"),
        "latitude": listing.get("latitude"),
        "longitude": listing.get("longitude"),
        "city": city,
        "state": state,
        "county": listing.get("county"),
    }


# ─── 主函数 ───────────────────────────────────────────────────────────────────


def fetch_property(url: str) -> dict:
    """
    通过 Apify maxcopell/zillow-detail-scraper 拉取 Zillow 房源数据。

    Args:
        url: Zillow 房源 URL

    Returns:
        清洗后的房源 dict（extract_core_fields 输出）

    Raises:
        FetchError: Apify 调用失败或返回空数据
    """
    api_token = os.environ.get("APIFY_API_TOKEN", "")
    client = ApifyClient(api_token)
    actor_id = "maxcopell/zillow-detail-scraper"

    try:
        run = client.actor(actor_id).call(run_input={"startUrls": [{"url": url}]})
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as exc:
        raise FetchError(f"Apify call failed: {exc}") from exc

    if not items:
        raise FetchError(f"Apify returned no results for URL: {url}")

    cleaned = extract_core_fields(items[0])
    if cleaned is None:
        raise FetchError("extract_core_fields returned None for the listing")

    return cleaned
