import asyncio
import logging
import time

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components import bluetooth
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


class Probe:
    def __init__(self, address):
        self.address = address
        self.client = None
        self.connected = False
        self.services_dump = []
        self.last_packets = {}
        self.packet_count = 0
        self.last_error = None


async def probe_loop(hass: HomeAssistant, probe: Probe):
    from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

    while True:
        try:
            device = bluetooth.async_ble_device_from_address(hass, probe.address, connectable=True)
            if device is None:
                _LOGGER.info("EENOUR_PROBE device not seen by scanner yet, retrying in 10s")
                await asyncio.sleep(10)
                continue

            def _disconnected(client):
                _LOGGER.info("EENOUR_PROBE disconnected")
                probe.connected = False
                probe.client = None

            client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                probe.address,
                disconnected_callback=_disconnected,
                max_attempts=3,
            )
            probe.client = client
            probe.connected = True
            _LOGGER.info("EENOUR_PROBE connected to %s", probe.address)

            dump = []
            for service in client.services:
                s_entry = {"service": service.uuid, "chars": []}
                for char in service.characteristics:
                    s_entry["chars"].append(
                        {
                            "uuid": char.uuid,
                            "properties": list(char.properties),
                            "descriptors": [d.uuid for d in char.descriptors],
                        }
                    )
                    _LOGGER.info(
                        "EENOUR_PROBE svc %s char %s props %s",
                        service.uuid,
                        char.uuid,
                        char.properties,
                    )
                    if "read" in char.properties:
                        try:
                            val = await client.read_gatt_char(char.uuid)
                            _LOGGER.info(
                                "EENOUR_PROBE read %s = %s | %r",
                                char.uuid,
                                bytes(val).hex(),
                                bytes(val),
                            )
                        except Exception as err:
                            _LOGGER.info("EENOUR_PROBE read %s failed: %s", char.uuid, err)
                dump.append(s_entry)
            probe.services_dump = dump

            last_log = {}

            def make_cb(uuid):
                def _cb(sender, data):
                    probe.packet_count += 1
                    hx = bytes(data).hex()
                    probe.last_packets[uuid] = (hx, time.time())
                    now = time.time()
                    if now - last_log.get(uuid, 0) >= 1.0:
                        last_log[uuid] = now
                        _LOGGER.info("EENOUR_PROBE notify %s: %s", uuid, hx)

                return _cb

            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties or "indicate" in char.properties:
                        try:
                            await client.start_notify(char.uuid, make_cb(char.uuid))
                            _LOGGER.info("EENOUR_PROBE subscribed %s", char.uuid)
                        except Exception as err:
                            _LOGGER.info("EENOUR_PROBE subscribe %s failed: %s", char.uuid, err)

            while client.is_connected:
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            probe.last_error = repr(err)
            _LOGGER.info("EENOUR_PROBE loop error: %r - retry in 15s", err)
            probe.connected = False
            probe.client = None
            await asyncio.sleep(15)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS].upper()
    probe = Probe(address)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"probe": probe}
    task = entry.async_create_background_task(hass, probe_loop(hass, probe), "eenour_probe_loop")
    hass.data[DOMAIN][entry.entry_id]["task"] = task

    if not hass.services.has_service(DOMAIN, "write"):

        async def _write(call: ServiceCall) -> None:
            uuid = call.data["uuid"]
            raw = bytes.fromhex(call.data["data"].replace(" ", ""))
            for data in hass.data.get(DOMAIN, {}).values():
                p = data["probe"]
                if p.client is not None and p.connected:
                    await p.client.write_gatt_char(uuid, raw, response=call.data.get("response", True))
                    _LOGGER.info("EENOUR_PROBE wrote %s to %s", raw.hex(), uuid)
                    return
            _LOGGER.warning("EENOUR_PROBE write failed: no connected client")

        hass.services.async_register(
            DOMAIN,
            "write",
            _write,
            schema=vol.Schema(
                {
                    vol.Required("uuid"): cv.string,
                    vol.Required("data"): cv.string,
                    vol.Optional("response", default=True): cv.boolean,
                }
            ),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        task = data.get("task")
        if task:
            task.cancel()
        probe = data["probe"]
        if probe.client is not None:
            try:
                await probe.client.disconnect()
            except Exception:
                pass
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
