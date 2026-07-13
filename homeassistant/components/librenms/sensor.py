"""Sensor platform for the LibreNMS integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    LibrenmsConfigEntry,
    LibrenmsData,
    LibrenmsDataUpdateCoordinator,
)
from .entity import LibrenmsEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LibrenmsSensorEntityDescription(SensorEntityDescription):
    """Librenms sensor entity description."""

    value: Callable[[LibrenmsData], StateType]
    is_suitable: Callable[[LibrenmsData], bool] = lambda _: True


SENSOR_TYPES: tuple[LibrenmsSensorEntityDescription, ...] = (
    LibrenmsSensorEntityDescription(
        key="device_count",
        translation_key="device_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: len(data.devices),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LibrenmsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add LibreNMS server state sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        LibrenmsSensorEntity(coordinator, description)
        for description in SENSOR_TYPES
        if description.is_suitable(coordinator.data)
    )


class LibrenmsSensorEntity(LibrenmsEntity, SensorEntity):
    """Define Librenms sensor entity."""

    entity_description: LibrenmsSensorEntityDescription

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
        description: LibrenmsSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self.coordinator.data)
