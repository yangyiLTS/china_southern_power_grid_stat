# -*- coding: utf-8 -*-
"""
Config flow for China Southern Power Grid Statistics integration.
Steps:
1. User input account credentials (username and password), the validity of credential verified
2. Get all electricity accounts linked to the user account, let user select one of them
3. Get the rest of needed parameters and save the config entries
"""
from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed
from requests import RequestException

from .const import (
    ABORT_ALL_ADDED,
    ABORT_NO_ACCOUNT,
    CONF_ACCOUNT_NUMBER,
    CONF_ACTION,
    CONF_API_PROFILE,
    CONF_AUTH_TOKEN,
    CONF_ELE_ACCOUNTS,
    CONF_GENERAL_ERROR,
    CONF_LOGIN_TYPE,
    CONF_SETTINGS,
    CONF_SMS_CODE,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATED_AT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    ERROR_UNKNOWN,
    LOGIN_TYPE_TO_QR_APP_NAME,
    STEP_ADD_ACCOUNT,
    STEP_ALI_QR_LOGIN,
    STEP_CSG_QR_LOGIN,
    STEP_INIT,
    STEP_QR_LOGIN,
    STEP_SETTINGS,
    STEP_SMS_LOGIN,
    STEP_SMS_PWD_LOGIN,
    STEP_USER,
    STEP_VALIDATE_SMS_CODE,
    STEP_WX_QR_LOGIN,
    redact_identifier,
)
from .csg_client import (
    API_PROFILE_WEB,
    CSGClient,
    CSGElectricityAccount,
    InvalidCredentials,
    LoginType,
    QrCodeExpired,
    api_profile_for_login_type,
)
from .csg_client.const import QR_AUTO_REFRESH_SECONDS

QR_POLL_INTERVAL_SECONDS = 2

_LOGGER = logging.getLogger(__name__)


class CSGConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for China Southern Power Grid Statistics."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize per-flow QR login state."""
        self._qr_login_task: asyncio.Task[str | None] | None = None
        self._qr_auth_token: str | None = None
        self._qr_image_link: str | None = None
        self._qr_refresh_count = 0

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return CSGOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle the initial step.
        Let user choose the login method.
        """
        self.context["user_data"] = {}
        return self.async_show_menu(
            step_id=STEP_USER,
            menu_options=[
                STEP_SMS_LOGIN,
                STEP_SMS_PWD_LOGIN,
                STEP_CSG_QR_LOGIN,
                STEP_WX_QR_LOGIN,
                STEP_ALI_QR_LOGIN,
            ],
        )

    async def async_step_sms_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SMS login step."""
        if user_input is None:
            # initial step, need phone number to send SMS code
            return self.async_show_form(
                step_id=STEP_SMS_LOGIN,
                data_schema=vol.Schema(
                    {
                        # TODO hardcoded string, should be a reference to strings.json?
                        vol.Required(CONF_USERNAME): vol.All(
                            str, vol.Length(min=11, max=11), msg="请输入11位手机号"
                        )
                    }
                ),
            )
        self.context["user_data"][CONF_USERNAME] = user_input[CONF_USERNAME]
        self.context["user_data"][CONF_PASSWORD] = ""
        self.context["user_data"][CONF_LOGIN_TYPE] = LoginType.LOGIN_TYPE_SMS
        return await self.async_step_validate_sms_code()

    async def async_step_sms_pwd_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SMS and password login step."""
        if user_input is None:
            return self.async_show_form(
                step_id=STEP_SMS_PWD_LOGIN,
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): vol.All(
                            str, vol.Length(min=11, max=11), msg="请输入11位手机号"
                        ),
                        vol.Required(CONF_PASSWORD): vol.All(
                            str, vol.Length(min=8, max=16), msg="请输入8-16位登陆密码"
                        ),  # as shown on CSG web login page
                    }
                ),
            )
        self.context["user_data"][CONF_USERNAME] = user_input[CONF_USERNAME]
        self.context["user_data"][CONF_PASSWORD] = user_input[CONF_PASSWORD]
        self.context["user_data"][CONF_LOGIN_TYPE] = LoginType.LOGIN_TYPE_PWD_AND_SMS
        return await self.async_step_validate_sms_code()

    async def async_step_validate_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SMS code validation step, for both SMS and SMS+password login."""
        schema = vol.Schema(
            {
                vol.Required(CONF_SMS_CODE): vol.All(
                    str, vol.Length(min=6, max=6), msg="请输入6位短信验证码"
                ),
            }
        )
        client: CSGClient = CSGClient()
        username = self.context["user_data"][CONF_USERNAME]

        if user_input is None:
            await self.check_and_set_unique_id(username)
            errors = {}
            error_detail = ""
            try:
                await self.hass.async_add_executor_job(
                    client.api_send_login_sms, username
                )
            except RequestException:
                errors[CONF_GENERAL_ERROR] = ERROR_CANNOT_CONNECT
            except Exception as ge:
                _LOGGER.exception("Unexpected exception when sending sms code")
                errors[CONF_GENERAL_ERROR] = ERROR_UNKNOWN
                error_detail = str(ge)
            else:
                return self.async_show_form(
                    step_id=STEP_VALIDATE_SMS_CODE,
                    data_schema=schema,
                    description_placeholders={"phone_no": username},
                )
            return self.async_show_form(
                step_id=STEP_VALIDATE_SMS_CODE,
                data_schema=schema,
                errors=errors,
                description_placeholders={"error_detail": error_detail},
            )

        # sms code is present, validate with api
        password = self.context["user_data"][CONF_PASSWORD]
        login_type: LoginType = self.context["user_data"][CONF_LOGIN_TYPE]
        sms_code = user_input[CONF_SMS_CODE]

        errors = {}
        error_detail = ""
        try:
            if login_type == LoginType.LOGIN_TYPE_SMS:
                auth_token = await self.hass.async_add_executor_job(
                    client.api_login_with_sms_code,
                    username,
                    sms_code,
                )
            elif login_type == LoginType.LOGIN_TYPE_PWD_AND_SMS:
                auth_token = await self.hass.async_add_executor_job(
                    client.api_login_with_password_and_sms_code,
                    username,
                    password,
                    sms_code,
                )
            else:
                raise ValueError(
                    f"Invalid login type for step {STEP_VALIDATE_SMS_CODE}: {login_type}"
                )
        except RequestException:
            errors[CONF_GENERAL_ERROR] = ERROR_CANNOT_CONNECT
        except InvalidCredentials as ice:
            errors[CONF_GENERAL_ERROR] = ERROR_INVALID_AUTH
            error_detail = str(ice)
        except Exception as ge:
            _LOGGER.exception("Unexpected exception during login validation")
            errors[CONF_GENERAL_ERROR] = ERROR_UNKNOWN
            error_detail = str(ge)
        else:
            return await self.create_or_update_config_entry(
                auth_token, login_type, password, username
            )
        return self.async_show_form(
            step_id=STEP_VALIDATE_SMS_CODE,
            data_schema=schema,
            errors=errors,
            description_placeholders={"error_detail": error_detail},
        )

    async def async_step_csg_qr_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """CSG APP QR Login"""
        self.context["user_data"][CONF_LOGIN_TYPE] = LoginType.LOGIN_TYPE_CSG_QR
        return await self.async_step_qr_login()

    async def async_step_wx_qr_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """WeChat QR Login"""
        self.context["user_data"][CONF_LOGIN_TYPE] = LoginType.LOGIN_TYPE_WX_QR
        return await self.async_step_qr_login()

    async def async_step_ali_qr_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """AliPay QR Login"""
        self.context["user_data"][CONF_LOGIN_TYPE] = LoginType.LOGIN_TYPE_ALI_QR
        return await self.async_step_qr_login()

    async def async_step_qr_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show a QR code and automatically wait for login confirmation."""
        login_type = self.context["user_data"][CONF_LOGIN_TYPE]

        if self._qr_login_task is None:
            client = CSGClient()
            try:
                login_id, self._qr_image_link = (
                    await self.hass.async_add_executor_job(
                        client.api_create_login_qr_code, login_type
                    )
                )
            except RequestException:
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:
                _LOGGER.exception("Unexpected exception when creating login QR code")
                return self.async_abort(reason=ERROR_UNKNOWN)

            self._qr_login_task = self.hass.async_create_task(
                self._async_wait_for_qr_login(login_id, login_type),
                "csg_qr_login_poll",
            )

        if not self._qr_login_task.done():
            refresh_notice = (
                "<p><strong>上一张二维码已过期，已自动更换。</strong></p>"
                if self._qr_refresh_count
                else ""
            )
            safe_image_link = html.escape(self._qr_image_link or "", quote=True)
            description = (
                f"{refresh_notice}<p>使用{LOGIN_TYPE_TO_QR_APP_NAME[login_type]}"
                "扫码并在手机上确认。此页面会自动检查登录状态，无需点击下一步。"
                "如一直未扫码，页面会每 5 分钟主动换一张新码。</p>"
                f'<img src="{safe_image_link}" alt="登录二维码" '
                'style="width: min(240px, 70vw); height: auto;"/>'
            )
            return self.async_show_progress(
                step_id=STEP_QR_LOGIN,
                progress_action="wait_for_qr_login",
                progress_task=self._qr_login_task,
                description_placeholders={"description": description},
            )

        try:
            auth_token = self._qr_login_task.result()
        except RequestException:
            self._qr_login_task = None
            return self.async_show_progress_done(
                next_step_id="qr_login_connection_error"
            )
        except Exception:
            _LOGGER.exception("Unexpected exception while polling login QR code")
            self._qr_login_task = None
            return self.async_show_progress_done(next_step_id="qr_login_unknown_error")

        self._qr_login_task = None
        if auth_token is None:
            self._qr_refresh_count += 1
            return self.async_show_progress_done(next_step_id="qr_login_refresh")

        self._qr_auth_token = auth_token
        return self.async_show_progress_done(next_step_id="qr_login_finish")

    async def _async_wait_for_qr_login(
        self, login_id: str, login_type: LoginType
    ) -> str | None:
        """Poll the QR login status until success or expiration."""
        client = CSGClient(api_profile=API_PROFILE_WEB)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + QR_AUTO_REFRESH_SECONDS

        while True:
            try:
                ok, auth_token = await self.hass.async_add_executor_job(
                    client.api_get_qr_login_status, login_id, login_type
                )
            except QrCodeExpired:
                return None

            if ok:
                return auth_token

            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            await asyncio.sleep(min(QR_POLL_INTERVAL_SECONDS, remaining))

    async def async_step_qr_login_refresh(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Automatically replace an expired QR code."""
        return await self.async_step_qr_login()

    async def async_step_qr_login_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish a successful QR login without another user action."""
        assert self._qr_auth_token is not None
        login_type = self.context["user_data"][CONF_LOGIN_TYPE]
        client = CSGClient(api_profile=API_PROFILE_WEB)
        client.set_authentication_params(self._qr_auth_token)
        try:
            user_info = await self.hass.async_add_executor_job(client.api_get_user_info)
        except RequestException:
            return self.async_abort(reason=ERROR_CANNOT_CONNECT)
        except Exception:
            _LOGGER.exception("Unexpected exception while completing QR login")
            return self.async_abort(reason=ERROR_UNKNOWN)

        username = user_info["mobile"]
        await self.check_and_set_unique_id(username)
        return await self.create_or_update_config_entry(
            self._qr_auth_token, login_type, "", username
        )

    async def async_step_qr_login_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Abort a QR flow when the service cannot be reached."""
        return self.async_abort(reason=ERROR_CANNOT_CONNECT)

    async def async_step_qr_login_unknown_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Abort a QR flow after an unexpected polling failure."""
        return self.async_abort(reason=ERROR_UNKNOWN)

    async def check_and_set_unique_id(self, username: str):
        """set unique id for the config entry, abort if already configured"""
        # TODO: username (mobile) may not be the best unique id
        unique_id = f"CSG-{username}"
        await self.async_set_unique_id(unique_id)
        if not self._reauth_entry:
            self._abort_if_unique_id_configured()

    async def create_or_update_config_entry(
        self, auth_token, login_type, _password, username
    ) -> FlowResult:
        """Create or update config entry
        If the account is newly added, create a new entry
        If the account is already added (reauth), update the existing entry"""
        linked_accounts: dict[str, dict[str, str]] = {}
        if not self._reauth_entry:
            client = CSGClient.load(
                {
                    CONF_AUTH_TOKEN: auth_token,
                    CONF_API_PROFILE: api_profile_for_login_type(login_type),
                }
            )
            try:
                await self.hass.async_add_executor_job(client.initialize)
                accounts = await self.hass.async_add_executor_job(
                    client.get_all_electricity_accounts
                )
            except RequestException:
                return self.async_abort(reason=ERROR_CANNOT_CONNECT)
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while discovering linked electricity accounts"
                )
                return self.async_abort(reason=ERROR_UNKNOWN)
            linked_accounts = {
                account.account_number: account.dump() for account in accounts
            }

        data = {
            CONF_USERNAME: username,
            # Password login is interactive and the password is not required
            # after an auth token has been issued. Never persist it in HA.
            CONF_PASSWORD: "",
            CONF_LOGIN_TYPE: login_type,
            CONF_AUTH_TOKEN: auth_token,
            CONF_API_PROFILE: api_profile_for_login_type(login_type),
            CONF_ELE_ACCOUNTS: linked_accounts,
            CONF_SETTINGS: {
                CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            },
            CONF_UPDATED_AT: str(int(time.time() * 1000)),
        }
        # handle normal creation and reauth
        if self._reauth_entry:
            # reauth
            # save the old config and only update the auth related data
            old_config = dict(self._reauth_entry.data)
            data[CONF_ELE_ACCOUNTS] = dict(old_config[CONF_ELE_ACCOUNTS])
            data[CONF_SETTINGS] = dict(old_config[CONF_SETTINGS])
            self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            self._reauth_entry = None
            return self.async_abort(reason="reauth_successful")
        # normal creation
        # check if account already exists

        return self.async_create_entry(
            title=f"CSG-{username}",
            data=data,
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()


class CSGOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for China Southern Power Grid Statistics."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.all_electricity_accounts: list[CSGElectricityAccount] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        schema = vol.Schema(
            {
                vol.Required(CONF_ACTION, default=STEP_ADD_ACCOUNT): vol.In(
                    {
                        STEP_ADD_ACCOUNT: "添加已绑定的缴费号",
                        STEP_SETTINGS: "参数设置",
                    }
                ),
            }
        )
        if user_input:
            if user_input[CONF_ACTION] == STEP_ADD_ACCOUNT:
                return await self.async_step_add_account()
            if user_input[CONF_ACTION] == STEP_SETTINGS:
                return await self.async_step_settings()
        return self.async_show_form(step_id=STEP_INIT, data_schema=schema)

    async def async_step_add_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select one of the electricity accounts from current account"""
        # account_no: f'{account_no} ({name} {addr})'

        all_csg_config_entries = self.hass.config_entries.async_entries(DOMAIN)
        # get a list of all account numbers from all config entries
        all_account_numbers = []
        for config_entry in all_csg_config_entries:
            all_account_numbers.extend(config_entry.data[CONF_ELE_ACCOUNTS].keys())
        if user_input:
            account_num_to_add = user_input[CONF_ACCOUNT_NUMBER]
            for account in self.all_electricity_accounts:
                if account.account_number == account_num_to_add:
                    # store the account config in main entry instead of creating new entries
                    new_data = dict(self.config_entry.data)
                    new_accounts = dict(new_data[CONF_ELE_ACCOUNTS])
                    new_accounts[account_num_to_add] = account.dump()
                    new_data[CONF_ELE_ACCOUNTS] = new_accounts
                    # this must be set or update won't be detected
                    new_data[CONF_UPDATED_AT] = str(int(time.time() * 1000))
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=new_data,
                    )
                    _LOGGER.info(
                        "Added ele account to %s: %s",
                        redact_identifier(self.config_entry.data[CONF_USERNAME]),
                        redact_identifier(account_num_to_add),
                    )
                    _LOGGER.info("Reloading entry because of new added account")
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                    return self.async_create_entry(
                        title="",
                        data={},
                    )
        # end of handling add account

        # start of getting all unbound accounts
        client = CSGClient.load(
            {
                CONF_AUTH_TOKEN: self.config_entry.data[CONF_AUTH_TOKEN],
                CONF_API_PROFILE: self.config_entry.data.get(
                    CONF_API_PROFILE,
                    api_profile_for_login_type(
                        self.config_entry.data[CONF_LOGIN_TYPE]
                    ),
                ),
            }
        )
        logged_in = await self.hass.async_add_executor_job(client.verify_login)
        if not logged_in:
            # token expired
            raise ConfigEntryAuthFailed("Login expired")
        await self.hass.async_add_executor_job(client.initialize)

        accounts = await self.hass.async_add_executor_job(
            client.get_all_electricity_accounts
        )
        self.all_electricity_accounts = accounts
        if not accounts:
            _LOGGER.warning(
                "No linked ele accounts found in csg account %s",
                redact_identifier(self.config_entry.data[CONF_USERNAME]),
            )
            return self.async_abort(reason=ABORT_NO_ACCOUNT)
        selections = {}
        for account in accounts:
            if account.account_number not in all_account_numbers:
                # avoid adding one ele account twice
                selections[account.account_number] = (
                    f"{account.account_number} ({account.user_name} {account.address})"
                )
        if not selections:
            _LOGGER.info(
                "Account %s: no ele account to add (all already added), abort",
                redact_identifier(self.config_entry.data[CONF_USERNAME]),
            )
            return self.async_abort(reason=ABORT_ALL_ADDED)

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NUMBER): vol.In(selections),
            }
        )
        return self.async_show_form(
            step_id=STEP_ADD_ACCOUNT,
            data_schema=schema,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Settings of parameters"""
        update_interval = self.config_entry.data[CONF_SETTINGS][CONF_UPDATE_INTERVAL]
        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL, default=update_interval): vol.All(
                    int, vol.Range(min=60), msg="刷新间隔不能低于60秒"
                ),
            }
        )
        if user_input is None:
            return self.async_show_form(step_id=STEP_SETTINGS, data_schema=schema)

        new_data = dict(self.config_entry.data)
        new_settings = dict(new_data[CONF_SETTINGS])
        new_settings[CONF_UPDATE_INTERVAL] = user_input[CONF_UPDATE_INTERVAL]
        new_data[CONF_SETTINGS] = new_settings
        new_data[CONF_UPDATED_AT] = str(int(time.time() * 1000))
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
        )
        return self.async_create_entry(
            title="",
            data={},
        )
