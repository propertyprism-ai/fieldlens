"""
test_fetcher.py — L1 单元测试，mock 所有外部调用
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_LISTING = {
    "zpid": "12345678",
    "address": {
        "streetAddress": "19533 E Timberline Rd",
        "city": "Queen Creek",
        "state": "AZ",
        "zipcode": "85142"
    },
    "hdpUrl": "https://www.zillow.com/homedetails/19533-E-Timberline-Rd/12345678_zpid/",
    "price": 550000,
    "yearBuilt": 2018,
    "bedrooms": 4,
    "bathrooms": 3,
    "livingArea": 2800,
    "lotSize": 8500,
    "homeType": "SINGLE_FAMILY",
    "daysOnZillow": 12,
    "homeStatus": "FOR_SALE",
    "rentZestimate": 2800,
    "restimateLowPercent": 5,
    "restimateHighPercent": 8,
    "description": "Beautiful home with new roof and updated kitchen.",
    "taxHistory": [
        {"taxPaid": 4200, "year": 2023},
        {"taxPaid": None, "year": 2022},
    ],
    "priceHistory": [
        {"date": "2024-01-15", "price": 550000, "event": "Listed for sale"},
        {"date": "2022-05-20", "price": 480000, "event": "Sold"},
    ],
    "schools": [
        {"name": "Queen Creek Elementary", "rating": 7},
        {"name": "Queen Creek High School", "rating": 6},
    ],
    "resoFacts": {
        "hoaFee": 150,
        "livingArea": 2800,
        "taxAnnualAmount": None,
    }
}


# ── Tests: extract_core_fields ────────────────────────────────────────────────

def test_extract_core_fields_basic():
    """extract_core_fields 提取所有核心字段"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)

    assert result is not None
    assert result["zpid"] == "12345678"
    assert result["address"] == "19533 E Timberline Rd, Queen Creek, AZ, 85142"
    assert result["price"] == 550000
    assert result["bedrooms"] == 4
    assert result["bathrooms"] == 3
    assert result["yearBuilt"] == 2018
    assert result["homeType"] == "SINGLE_FAMILY"


def test_extract_core_fields_tax_from_history():
    """税务从 taxHistory 提取第一个非 null 值"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)
    assert result["taxAnnualAmount"] == 4200.0


def test_extract_core_fields_rent_range():
    """租金范围基于 rentZestimate 和置信区间计算"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)
    assert result["rentZestimate"] == 2800
    assert result["rentMin"] is not None
    assert result["rentMax"] is not None
    assert result["rentMin"] < 2800 < result["rentMax"]


def test_extract_core_fields_hoa():
    """HOA 费用正确提取"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)
    assert result["hoaFee"] == 150.0


def test_extract_core_fields_hoa_default_zero():
    """缺失 HOA 时默认为 0"""
    from src.fetcher import extract_core_fields
    listing = dict(SAMPLE_LISTING)
    listing["resoFacts"] = {}
    result = extract_core_fields(listing)
    assert result["hoaFee"] == 0


def test_extract_core_fields_schools():
    """学校评分正确提取"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)
    assert len(result["schoolRating"]) == 2
    assert "Queen Creek Elementary: 7.0/10" in result["schoolRating"]


def test_extract_core_fields_price_history():
    """价格历史只保留 date/price/event"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields(SAMPLE_LISTING)
    assert len(result["priceHistory"]) == 2
    for entry in result["priceHistory"]:
        assert set(entry.keys()) == {"date", "price", "event"}


def test_extract_core_fields_none_input():
    """输入 None 返回 None"""
    from src.fetcher import extract_core_fields
    assert extract_core_fields(None) is None


def test_extract_core_fields_empty_dict():
    """空 dict 不抛异常"""
    from src.fetcher import extract_core_fields
    result = extract_core_fields({})
    assert result is not None
    assert result["zpid"] is None


# ── Tests: fetch_property ─────────────────────────────────────────────────────

def test_fetch_property_success():
    """fetch_property 成功时返回清洗后的 dict"""
    from src.fetcher import fetch_property

    mock_client = MagicMock()
    mock_run = {"id": "run123", "defaultDatasetId": "dataset123"}
    mock_client.actor.return_value.call.return_value = mock_run
    mock_client.dataset.return_value.iterate_items.return_value = iter([SAMPLE_LISTING])

    with patch("src.fetcher.ApifyClient", return_value=mock_client):
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token-abc"}):
            result = fetch_property("https://www.zillow.com/homedetails/test/12345678_zpid/")

    assert result is not None
    assert result["zpid"] == "12345678"
    assert result["price"] == 550000


def test_fetch_property_empty_results():
    """Apify 返回空结果时抛 FetchError"""
    from src.fetcher import fetch_property, FetchError

    mock_client = MagicMock()
    mock_run = {"id": "run123", "defaultDatasetId": "dataset123"}
    mock_client.actor.return_value.call.return_value = mock_run
    mock_client.dataset.return_value.iterate_items.return_value = iter([])

    with patch("src.fetcher.ApifyClient", return_value=mock_client):
        with pytest.raises(FetchError):
            fetch_property("https://www.zillow.com/homedetails/test/12345678_zpid/")


def test_fetch_property_apify_exception():
    """Apify 调用抛异常时包装为 FetchError"""
    from src.fetcher import fetch_property, FetchError

    mock_client = MagicMock()
    mock_client.actor.return_value.call.side_effect = RuntimeError("API error")

    with patch("src.fetcher.ApifyClient", return_value=mock_client):
        with pytest.raises(FetchError):
            fetch_property("https://www.zillow.com/homedetails/test/12345678_zpid/")


def test_fetch_property_uses_api_token_from_env():
    """fetch_property 从环境变量读取 APIFY_API_TOKEN"""
    from src.fetcher import fetch_property

    mock_client = MagicMock()
    mock_run = {"id": "run123", "defaultDatasetId": "dataset123"}
    mock_client.actor.return_value.call.return_value = mock_run
    mock_client.dataset.return_value.iterate_items.return_value = iter([SAMPLE_LISTING])

    with patch("src.fetcher.ApifyClient", return_value=mock_client) as mock_apify_cls:
        with patch.dict("os.environ", {"APIFY_API_TOKEN": "test-token-123"}):
            fetch_property("https://www.zillow.com/homedetails/test/12345678_zpid/")
        mock_apify_cls.assert_called_once_with("test-token-123")
