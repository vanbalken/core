"""Support for zeversolor inverters."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (  # , CONF_SCAN_INTERVAL
    CONF_HOST,
    CONF_PORT,
    CONF_RESOURCES,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

BASE_URL = "http://{0}:{1}{2}"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

SENSOR_PREFIX = "PV "

SENSOR_TYPES = {
    "power": ["Solar Power", "Watt", "mdi:weather-sunny"],
    "energy_today": ["Solar Energy Today", "KWh", "mdi:weather-sunny"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.positive_int,
        vol.Required(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform."""
    # scan_interval = config.get(CONF_SCAN_INTERVAL)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    try:
        data = ZeversolarData(host, port)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [sensor_type.title(), "", "mdi:flash"]

        entities.append(ZeversolarSensor(data, sensor_type))

    add_entities(entities)


# pylint: disable=abstract-method
class ZeversolarData:
    """The zeversolor data object."""

    def __init__(self, host, port):
        """Initialize the inverter."""
        self._host = host
        self._port = port
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the data from the inverter."""
        try:
            r = requests.get(
                BASE_URL.format(self._host, self._port, "/home.cgi"), timeout=5
            )
            self.data = r.text
            temp = r.text.splitlines()
            _LOGGER.info("Data = %s", temp[10])
            _LOGGER.info("Data = %s", temp[11])
        except requests.exceptions.RequestException:
            # Inverter is unavailable when there is no sun
            self.data = None


class ZeversolarSensor(Entity):
    """Implementation of a zeversolor sensor."""

    def __init__(self, data, sensor_type):
        """Initialize the sensor."""
        self.data = data
        self.type = sensor_type
        self._name = SENSOR_PREFIX + SENSOR_TYPES[self.type][0]
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    def update(self):
        """Get the latest data and use it to update our sensor state."""
        self.data.update()

        # Set value to None if there is no data
        if self.data.data is None:
            self._state = None
            return

        energy = str(self.data.data).splitlines()

        """Go to http://inverter.ip:port/home.cgi"""
        if self.type == "power":
            self._state = int(energy[10])

        elif self.type == "energy_today":
            """fix bug where the 0 after the decimal point is missing ('0.9' actually means 0.09, '0.90' is just that)"""
            kwh = energy[11]
            parts = kwh.split(".")
            if len(parts[1]) == 1:
                kwh = "{}.0{}".format(parts[0], parts[1])
            self._state = float(kwh)
