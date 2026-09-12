"""Aquagem configuration switches."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .entity import AquagemEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Aquagem configuration switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AquagemLocalControlAssistSwitch(coordinator, entry)])


class AquagemLocalControlAssistSwitch(AquagemEntity, SwitchEntity, RestoreEntity):
    """Allow adaptive polling that leaves silent windows for local control."""

    _attr_translation_key = "local_control_assist"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_local_control_assist"

    @property
    def available(self) -> bool:
        """Keep the configuration switch available even if the pump is offline."""
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.local_control_assist

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self.coordinator.set_local_control_assist(last_state.state == STATE_ON)

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.set_local_control_assist(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.set_local_control_assist(False)
        self.async_write_ha_state()
