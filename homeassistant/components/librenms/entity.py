"""Base entity for the LibreNMS integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LibrenmsDataUpdateCoordinator


class LibrenmsEntity(CoordinatorEntity[LibrenmsDataUpdateCoordinator]):
    """Define LibreNMS base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="LibreNMS",
            sw_version=coordinator.data.system.local_ver,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.configuration_url,
            name="LibreNMS",
        )
