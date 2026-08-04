"""Constants for csg_client"""

from enum import Enum

# Request timeout in seconds for all HTTP calls to the CSG API.
# Prevents the HA thread pool from being exhausted by hung connections.
REQUEST_TIMEOUT = 30

BASE_PATH_WEB = "https://95598.csg.cn/ucs/ma/wt/"
BASE_PATH_APP = "https://95598.csg.cn/ucs/ma/zt/"
BASE_PATH_QR_NEW = "https://95598.csg.cn/mp/w2/wx/userauth/"

API_PROFILE_APP = "app"
API_PROFILE_WEB = "web"
API_PROFILE_TO_BASE_PATH = {
    API_PROFILE_APP: BASE_PATH_APP,
    API_PROFILE_WEB: BASE_PATH_WEB,
}
ALLOWED_BASE_PATHS = frozenset(
    {
        BASE_PATH_APP,
        BASE_PATH_WEB,
        BASE_PATH_QR_NEW,
    }
)

# Legacy mobile API crypto material retained for SMS-login sessions.
# Source: https://95598.csg.cn/js/app.1.6.177.1667607288138.js
PARAM_KEY_APP = "cOdHFNHUNkZrjNaN".encode("utf8")
PARAM_IV_APP = "oMChoRLZnTivcQyR".encode("utf8")

# Current online-hall API crypto material. The web bundle stores obfuscated
# values and derives these 16-byte strings by reversing the underscore-delimited
# segments, dropping the marker, then taking the first character of each part.
# Source: https://95598.csg.cn/js/app.1.6.230.1785775124453.js
PARAM_KEY_WEB = "zFujxJSrfmClqtKO".encode("utf8")
PARAM_IV_WEB = "oMShoRXZnAivcCyR".encode("utf8")
LOGON_CHANNEL_ONLINE_HALL = "3"  # web
LOGON_CHANNEL_HANDHELD_HALL = "4"  # app
RESP_STA_SUCCESS = "00"
RESP_STA_EMPTY_PARAMETER = "01"
RESP_STA_SYSTEM_ERROR = "02"
RESP_STA_NO_LOGIN = "04"
RESP_STA_QR_NOT_SCANNED = "09"
SESSION_KEY_LOGIN_TYPE = "10"


class LoginType(str, Enum):
    """Login type from JS"""

    LOGIN_TYPE_SMS = "11"
    LOGIN_TYPE_PWD_AND_SMS = "1011"
    LOGIN_TYPE_WX_QR = "20"
    LOGIN_TYPE_ALI_QR = "21"
    LOGIN_TYPE_CSG_QR = "30"


class QRCodeType(str, Enum):
    """QR code type used in creation API"""

    QR_CSG = "app"
    QR_WECHAT = "wechat"
    QR_ALIPAY = "alipay"


LOGIN_TYPE_TO_QR_CODE_TYPE = {
    LoginType.LOGIN_TYPE_CSG_QR: QRCodeType.QR_CSG,
    LoginType.LOGIN_TYPE_WX_QR: QRCodeType.QR_WECHAT,
    LoginType.LOGIN_TYPE_ALI_QR: QRCodeType.QR_ALIPAY,
}


def api_profile_for_login_type(login_type: LoginType | str) -> str:
    """Return the API channel that owns the authenticated session."""
    parsed_login_type = LoginType(login_type)
    if parsed_login_type in {
        LoginType.LOGIN_TYPE_WX_QR,
        LoginType.LOGIN_TYPE_ALI_QR,
        LoginType.LOGIN_TYPE_CSG_QR,
    }:
        return API_PROFILE_WEB
    return API_PROFILE_APP

AREACODE_FALLBACK = AREACODE_GUANGDONG = "030000"

# https://95598.csg.cn/js/chunk-31aec193.1.6.177.1667607288138.js
CREDENTIAL_PUBKEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQD1RJE6GBKJlFQvTU6g0ws9R"
    "+qXFccKl4i1Rf4KVR8Rh3XtlBtvBxEyTxnVT294RVvYz6THzHGQwREnlgdkjZyGBf7tmV2CgwaHF+ttvupuzOmRVQ"
    "/difIJtXKM+SM0aCOqBk0fFaLiHrZlZS4qI2/rBQN8VBoVKfGinVMM+USswwIDAQAB"
)

# the value of these login types are the same as the enum above
# however they're not programmatically linked in the source code
# use them as seperated parameters for now
LOGIN_TYPE_PHONE_CODE = "11"
LOGIN_TYPE_PHONE_PWD_CODE = "1011"
SEND_MSG_TYPE_VERIFICATION_CODE = "1"
VERIFICATION_CODE_TYPE_LOGIN = "1"

# https://95598.csg.cn/js/chunk-49c87982.1.6.177.1667607288138.js
RESP_STA_QR_TIMEOUT = "00010001"

# from packet capture
RESP_STA_LOGIN_WRONG_CREDENTIAL = "00010002"

# The current status endpoint can keep returning "not scanned" beyond five
# minutes. Rotate a stale QR locally so the user is never left with an old code;
# this is a UI safety guard, not a claimed server-side expiry duration.
QR_AUTO_REFRESH_SECONDS = 300

# account object serialisation and deserialisation
ATTR_ACCOUNT_NUMBER = "account_number"
ATTR_AREA_CODE = "area_code"
ATTR_ELE_CUSTOMER_ID = "ele_customer_id"
ATTR_METERING_POINT_ID = "metering_point_id"
ATTR_METERING_POINT_NUMBER = "metering_point_number"
ATTR_ADDRESS = "address"
ATTR_USER_NAME = "user_name"
ATTR_AUTH_TOKEN = "auth_token"
ATTR_LOGIN_TYPE = "login_type"
ATTR_API_PROFILE = "api_profile"

# JSON/Headers used in raw APIs
HEADER_X_AUTH_TOKEN = "x-auth-token"
HEADER_CUST_NUMBER = "custNumber"
JSON_KEY_STA = "sta"
JSON_KEY_MESSAGE = "message"
JSON_KEY_CUST_NUMBER = "custNumber"
JSON_KEY_DATA = "data"
JSON_KEY_LOGON_CHAN = "logonChan"
JSON_KEY_SMS_CODE = "code"
JSON_KEY_CRED_TYPE = "credType"
JSON_KEY_AREA_CODE = "areaCode"
JSON_KEY_PARAM = "param"
JSON_KEY_ACCT_ID = "acctId"
JSON_KEY_ELE_CUST_ID = "eleCustId"
JSON_KEY_METERING_POINT_ID = "meteringPointId"
JSON_KEY_METERING_POINT_NUMBER = "meteringPointNumber"
JSON_KEY_YEAR_MONTH = "yearMonth"

# for wrapper functions
WF_ATTR_LADDER = "ladder"
WF_ATTR_LADDER_START_DATE = "start_date"
WF_ATTR_LADDER_REMAINING_KWH = "remaining_kwh"
WF_ATTR_LADDER_TARIFF = "tariff"

WF_ATTR_DATE = "date"
WF_ATTR_MONTH = "month"
WF_ATTR_CHARGE = "charge"
WF_ATTR_KWH = "kwh"
