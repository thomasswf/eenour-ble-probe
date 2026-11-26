import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS
from .const import DOMAIN

class EenourProbeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="EENOUR Probe", data={CONF_ADDRESS: address})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS, default="7C:E7:12:FB:F4:E3"): str}),
        )
