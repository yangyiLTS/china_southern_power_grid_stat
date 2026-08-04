# -*- coding: utf-8 -*-
"""The China Southern Power Grid Statistics integration."""
from __future__ import annotations

import logging
import time

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_API_PROFILE,
    CONF_AUTH_TOKEN,
    CONF_ELE_ACCOUNTS,
    CONF_LOGIN_TYPE,
    CONF_UPDATED_AT,
    DOMAIN,
    auth_notification_id,
    redact_identifier,
)
from .csg_client import (
    CSGClient,
    api_profile_for_login_type,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up China Southern Power Grid Statistics from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # validate session, re-authenticate if needed
    client = CSGClient.load(
        {
            CONF_AUTH_TOKEN: entry.data[CONF_AUTH_TOKEN],
            CONF_API_PROFILE: entry.data.get(
                CONF_API_PROFILE,
                api_profile_for_login_type(entry.data[CONF_LOGIN_TYPE]),
            ),
        }
    )
    if not await hass.async_add_executor_job(client.verify_login):
        persistent_notification.async_create(
            hass,
            (
                "南网在线登录已过期，电费数据已停止更新。请前往“设置 → "
                "设备与服务 → 南方电网电费统计”，选择“重新配置”后再次扫码。"
            ),
            title="南方电网需要重新登录",
            notification_id=auth_notification_id(entry.entry_id),
        )
        raise ConfigEntryAuthFailed("Login expired")

    persistent_notification.async_dismiss(
        hass, auth_notification_id(entry.entry_id)
    )

    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading CSG entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("Unload platforms for CSG entry, success: %s", unload_ok)
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove device"""
    _LOGGER.info("Removing a CSG electricity-account device")
    account_num = list(device_entry.identifiers)[0][1]

    # remove entities
    entity_reg = entity_registry.async_get(hass)
    entities = {
        ent.unique_id: ent.entity_id
        for ent in entity_registry.async_entries_for_config_entry(
            entity_reg, config_entry.entry_id
        )
        if account_num in ent.unique_id
    }
    for entity_id in entities.values():
        entity_reg.async_remove(entity_id)

    # update config entry
    new_data = dict(config_entry.data)
    new_accounts = dict(new_data[CONF_ELE_ACCOUNTS])
    new_accounts.pop(account_num)
    new_data[CONF_ELE_ACCOUNTS] = new_accounts
    new_data[CONF_UPDATED_AT] = str(int(time.time() * 1000))
    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
    )
    _LOGGER.info(
        "Removed ele account from %s: %s",
        redact_identifier(config_entry.data[CONF_USERNAME]),
        redact_identifier(account_num),
    )
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.info(
        "Removing CSG entry for account %s",
        redact_identifier(entry.data[CONF_USERNAME]),
    )

    # logout
    def client_logout():
        client = CSGClient.load(
            {
                CONF_AUTH_TOKEN: entry.data[CONF_AUTH_TOKEN],
                CONF_API_PROFILE: entry.data.get(
                    CONF_API_PROFILE,
                    api_profile_for_login_type(entry.data[CONF_LOGIN_TYPE]),
                ),
            }
        )
        if client.verify_login():
            client.logout(entry.data[CONF_LOGIN_TYPE])
            _LOGGER.info(
                "CSG account %s logged out",
                redact_identifier(entry.data[CONF_USERNAME]),
            )

    await hass.async_add_executor_job(client_logout)
