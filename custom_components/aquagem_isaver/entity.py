"""Shared Aquagem entity."""

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class AquagemEntity(CoordinatorEntity):
    """Base entity tied to one gateway."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, entry.title),
            manufacturer="Aquagem",
            model=coordinator.client.model,
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Keep generated entity IDs stable and English in every HA language."""
        if self.platform_data and self.translation_key:
            translation_key = (
                f"component.{self.platform_data.platform_name}.entity."
                f"{self.platform_data.domain}.{self.translation_key}.name"
            )
            if english_name := self.platform_data.default_language_platform_translations.get(
                translation_key
            ):
                return english_name
        return super().suggested_object_id

    @property
    def available(self) -> bool:
        """Keep transient read failures from making every entity unavailable."""
        return super().available and self.coordinator.communication_online is not False
