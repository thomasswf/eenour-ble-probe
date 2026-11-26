from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    probe = hass.data[DOMAIN][entry.entry_id]["probe"]
    async_add_entities([EenourProbeSensor(entry, probe)])


class EenourProbeSensor(SensorEntity):
    _attr_should_poll = True

    def __init__(self, entry: ConfigEntry, probe) -> None:
        self._probe = probe
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "EENOUR Probe Status"

    @property
    def native_value(self):
        return "connected" if self._probe.connected else "disconnected"

    @property
    def extra_state_attributes(self):
        return {
            "address": self._probe.address,
            "packet_count": self._probe.packet_count,
            "last_packets": {k: v[0] for k, v in self._probe.last_packets.items()},
            "services": self._probe.services_dump,
            "last_error": self._probe.last_error,
        }
