"""Regression tests for CSG authentication and API channel routing."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

INTEGRATION_ROOT = (
    Path(__file__).parents[1]
    / "custom_components"
    / "china_southern_power_grid_stat"
)
sys.path.insert(0, str(INTEGRATION_ROOT))

from csg_client import (  # noqa: E402
    HEADER_X_AUTH_TOKEN,
    CSGAPIError,
    CSGClient,
    CSGElectricityAccount,
    LoginType,
    api_profile_for_login_type,
    decrypt_params,
    encrypt_params,
)
from csg_client.const import (  # noqa: E402
    API_PROFILE_APP,
    API_PROFILE_WEB,
    BASE_PATH_APP,
    BASE_PATH_QR_NEW,
    BASE_PATH_WEB,
    PARAM_IV_WEB,
    PARAM_KEY_WEB,
)


class FakeResponse:
    """Small requests.Response stand-in."""

    def __init__(self, payload: dict, headers: dict | None = None) -> None:
        self.status_code = 200
        self.content = json.dumps(payload).encode()
        self.headers = headers or {}


class RecordingSession:
    """Record request metadata and return queued responses."""

    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, *, json, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def _success(data=None, headers=None) -> FakeResponse:
    return FakeResponse({"sta": "00", "data": data}, headers)


@pytest.mark.parametrize(
    ("login_type", "expected_profile"),
    [
        (LoginType.LOGIN_TYPE_SMS, API_PROFILE_APP),
        (LoginType.LOGIN_TYPE_PWD_AND_SMS, API_PROFILE_APP),
        (LoginType.LOGIN_TYPE_CSG_QR, API_PROFILE_WEB),
        (LoginType.LOGIN_TYPE_WX_QR, API_PROFILE_WEB),
        (LoginType.LOGIN_TYPE_ALI_QR, API_PROFILE_WEB),
    ],
)
def test_login_type_selects_a_fixed_api_profile(login_type, expected_profile):
    assert api_profile_for_login_type(login_type) == expected_profile


def test_authenticated_calls_use_the_selected_profile():
    app_client = CSGClient(auth_token="secret", api_profile=API_PROFILE_APP)
    app_client._session = RecordingSession(_success([]))
    app_client.api_get_all_linked_electricity_accounts()
    assert app_client._session.calls[0]["url"] == (
        BASE_PATH_APP + "eleCustNumber/queryBindEleUsers"
    )

    web_client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    web_client._session = RecordingSession(_success([]))
    web_client.api_get_all_linked_electricity_accounts()
    assert web_client._session.calls[0]["url"] == (
        BASE_PATH_WEB + "eleCustNumber/queryBindEleUsers"
    )


def test_wechat_keeps_the_legacy_qr_endpoint():
    client = CSGClient(api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(_success("https://example.invalid/qr"))

    login_id, _ = client.api_create_login_qr_code(
        LoginType.LOGIN_TYPE_WX_QR, login_id="wechat-id"
    )

    call = client._session.calls[0]
    assert login_id == "wechat-id"
    assert call["url"] == BASE_PATH_WEB + "center/createLoginQrcode"
    assert call["json"]["lgoinId"] == "wechat-id"
    assert call["json"]["channel"] == "wechat"
    assert call["json"]["channelCode"] == "4"


@pytest.mark.parametrize(
    ("login_type", "channel"),
    [
        (LoginType.LOGIN_TYPE_CSG_QR, "app"),
        (LoginType.LOGIN_TYPE_ALI_QR, "alipay"),
    ],
)
def test_app_and_alipay_use_the_current_qr_service(login_type, channel):
    client = CSGClient(api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(_success("https://example.invalid/qr"))

    client.api_create_login_qr_code(login_type, login_id="new-id")

    call = client._session.calls[0]
    assert call["url"] == BASE_PATH_QR_NEW + "user/manage/createLoginQrcode"
    assert call["json"] == {
        "channel": channel,
        "channelCode": "4",
        "loginId": "new-id",
    }
    assert call["headers"]["channelCode"] == "3"


def test_qr_status_returns_only_the_response_header_token():
    client = CSGClient(api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(
        _success("ignored", {HEADER_X_AUTH_TOKEN: "issued-token"})
    )

    ok, token = client.api_get_qr_login_status(
        "new-id", LoginType.LOGIN_TYPE_CSG_QR
    )

    assert ok is True
    assert token == "issued-token"
    assert client._session.calls[0]["url"] == (
        BASE_PATH_QR_NEW + "user/manage/getLoginInfo"
    )


def test_qr_status_rejects_success_without_a_token():
    client = CSGClient(api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(_success("not-a-token"))

    with pytest.raises(CSGAPIError, match="missing_auth_token"):
        client.api_get_qr_login_status("id", LoginType.LOGIN_TYPE_CSG_QR)


def test_profile_is_serialized_but_arbitrary_destinations_are_rejected():
    dumped = CSGClient(
        auth_token="secret", api_profile=API_PROFILE_WEB
    ).dump()
    restored = CSGClient.load(dumped)
    assert restored.api_profile == API_PROFILE_WEB

    with pytest.raises(ValueError, match="Unsupported API profile"):
        CSGClient(auth_token="secret", api_profile="https://attacker.invalid/")


def _account() -> CSGElectricityAccount:
    return CSGElectricityAccount(
        account_number="masked-test-account",
        area_code="030000",
        ele_customer_id="binding-id",
        metering_point_id="meter-id",
        metering_point_number="meter-number",
        address="masked",
        user_name="masked",
    )


def _shenzhen_account() -> CSGElectricityAccount:
    return CSGElectricityAccount(
        account_number="masked-shenzhen-account",
        area_code="090000",
        ele_customer_id="shenzhen-binding-id",
        metering_point_id="shenzhen-meter-id",
        metering_point_number="shenzhen-meter-number",
        address="masked",
        user_name="masked",
    )


def test_web_month_call_uses_current_crypto_and_decrypts_response():
    response_data = {
        "totalPower": "12.3",
        "totalElectricity": "6.4",
        "result": [{"date": "2026-08-01", "power": "12.3"}],
    }
    encrypted_response = encrypt_params(
        response_data,
        PARAM_KEY_WEB,
        PARAM_IV_WEB,
    )
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(
        _success(encrypted_response, {"need-decrypto": "true"})
    )

    result = client.api_query_day_electric_by_m_point(
        2026, 8, "030000", "binding-id", "meter-id"
    )

    call = client._session.calls[0]
    assert call["headers"]["need-crypto"] == "true"
    assert decrypt_params(
        call["json"]["param"], PARAM_KEY_WEB, PARAM_IV_WEB
    ) == {
        "areaCode": "030000",
        "eleCustId": "binding-id",
        "yearMonth": "202608",
        "meteringPointId": "meter-id",
    }
    assert result == response_data


def test_combined_month_detail_replaces_removed_daily_charge_api():
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(
        _success(
            {
                "totalPower": "47.16",
                "totalElectricity": "23.58",
                "result": [
                    {"date": "2026-08-01", "power": "15.80"},
                    {
                        "date": "2026-08-02",
                        "power": "15.59",
                        "charge": "7.80",
                    },
                ],
            }
        )
    )

    total_cost, total_kwh, ladder, by_day = client.get_month_daily_detail(
        _account(), (2026, 8)
    )

    assert total_cost == 23.58
    assert total_kwh == 47.16
    assert ladder["ladder"] is None
    assert by_day[0] == {"date": "2026-08-01", "kwh": 15.8}
    assert by_day[1]["charge"] == 7.8


def test_shenzhen_month_uses_calendar_endpoint_and_meter_number():
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_APP)
    client._session = RecordingSession(
        _success(
            {
                "result": [
                    {"date": "2026-09-02", "power": "15.59"},
                    {"date": "2026-09-01", "power": "15.80"},
                ]
            }
        )
    )

    total_cost, total_kwh, _, by_day = client.get_month_daily_detail(
        _shenzhen_account(), (2026, 9)
    )

    call = client._session.calls[0]
    assert call["url"] == BASE_PATH_APP + "charge/queryElectricityCalendar"
    assert call["json"] == {
        "areaCode": "090000",
        "eleCustId": "shenzhen-binding-id",
        "yearMonth": "202609",
        "meteringPointId": "shenzhen-meter-id",
        "deviceIdentif": "shenzhen-meter-number",
    }
    assert "need-crypto" not in call["headers"]
    assert total_cost is None
    assert total_kwh == pytest.approx(31.39)
    assert [item["date"] for item in by_day] == ["2026-09-01", "2026-09-02"]


def test_shenzhen_yesterday_uses_the_same_calendar_route():
    yesterday = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    yesterday -= timedelta(days=1)
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_APP)
    client._session = RecordingSession(
        _success(
            {
                "result": [
                    {"date": yesterday.isoformat(), "power": "9.75"},
                ]
            }
        )
    )

    assert client.get_yesterday_kwh(_shenzhen_account()) == 9.75
    assert client._session.calls[0]["url"] == (
        BASE_PATH_APP + "charge/queryElectricityCalendar"
    )


def test_yesterday_is_derived_from_month_detail():
    yesterday = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    yesterday -= timedelta(days=1)
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(
        _success(
            {
                "result": [
                    {"date": yesterday.isoformat(), "power": "9.75"},
                ]
            }
        )
    )

    assert client.get_yesterday_kwh(_account()) == 9.75


@pytest.mark.parametrize(
    "api_data",
    [
        {"balance": "10.5", "arrears": "0"},
        [{"balance": "10.5", "arrears": "0"}],
    ],
)
def test_balance_accepts_current_and_legacy_response_shapes(api_data):
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(_success(api_data))
    assert client.get_balance_and_arrears(_account()) == (10.5, 0.0)


def test_year_analysis_sends_current_metering_point_number():
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    client._session = RecordingSession(
        _success(
            {
                "totalBillingElectricity": "1",
                "totalActualAmount": "2",
                "electricAndChargeList": [],
            }
        )
    )

    client.get_year_month_stats(_account(), 2026)

    request_data = decrypt_params(
        client._session.calls[0]["json"]["param"],
        PARAM_KEY_WEB,
        PARAM_IV_WEB,
    )
    assert request_data["meteringPointId"] == "meter-number"


def test_removed_data_api_paths_do_not_return():
    source = (INTEGRATION_ROOT / "csg_client" / "__init__.py").read_text()
    assert "queryDayElectricChargeByMPoint" not in source
    assert "queryDayElectricByMPointYesterday" not in source


def test_multi_year_history_keeps_official_monthly_usage_and_cost(monkeypatch):
    client = CSGClient(auth_token="secret", api_profile=API_PROFILE_WEB)
    calls = []

    def fake_year_stats(_account, year):
        calls.append(year)
        return (
            float(year),
            float(year * 2),
            [
                {
                    "month": f"{year}-01",
                    "charge": float(year),
                    "kwh": float(year * 2),
                }
            ],
        )

    monkeypatch.setattr(client, "get_year_month_stats", fake_year_stats)

    rows = client.get_years_month_stats(_account(), [2023, 2024])

    assert calls == [2023, 2024]
    assert rows == [
        {"month": "2023-01", "charge": 2023.0, "kwh": 4046.0},
        {"month": "2024-01", "charge": 2024.0, "kwh": 4048.0},
    ]
