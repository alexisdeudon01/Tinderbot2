"""Sensor platform for Tinder MCP — profile information and match statistics."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TinderCoordinator
from .const import (
    ATTR_COORDINATOR,
    DOMAIN,
    ENTITY_MATCH_COUNT,
    ENTITY_PROFILE_AGE,
    ENTITY_PROFILE_BIO,
    ENTITY_PROFILE_NAME,
)


@dataclass
class TinderSensorEntityDescription(SensorEntityDescription):
    """Extend SensorEntityDescription with a value accessor."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda _: None


SENSOR_DESCRIPTIONS: tuple[TinderSensorEntityDescription, ...] = (
    TinderSensorEntityDescription(
        key=ENTITY_PROFILE_NAME,
        name="Tinder Profile Name",
        icon="mdi:account",
        value_fn=lambda data: data.get("current_name"),
    ),
    TinderSensorEntityDescription(
        key=ENTITY_PROFILE_AGE,
        name="Tinder Profile Age",
        icon="mdi:cake-variant",
        native_unit_of_measurement="ans",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current_age"),
    ),
    TinderSensorEntityDescription(
        key=ENTITY_PROFILE_BIO,
        name="Tinder Profile Bio",
        icon="mdi:text",
        value_fn=lambda data: (data.get("current_bio") or "")[:255],
    ),
    TinderSensorEntityDescription(
        key=ENTITY_MATCH_COUNT,
        name="Tinder Match Count",
        icon="mdi:heart-multiple",
        native_unit_of_measurement="matchs",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.get("match_count", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tinder MCP sensors from a config entry."""
    coordinator: TinderCoordinator = hass.data[DOMAIN][entry.entry_id][ATTR_COORDINATOR]
    async_add_entities(
        TinderSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class TinderSensor(CoordinatorEntity[TinderCoordinator], SensorEntity):
    """A single Tinder sensor backed by the DataUpdateCoordinator."""

    entity_description: TinderSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TinderCoordinator,
        entry: ConfigEntry,
        description: TinderSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Tinder MCP",
            "manufacturer": "glassBead-tc",
            "model": "Tinder API MCP Server",
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
