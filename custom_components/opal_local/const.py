"""Constants for the first-generation Opal BLE protocol."""
DOMAIN = "opal_local"
SERVICE = "3e6763c5-9429-40cc-909e-bebf8c7487be"
CHARACTERISTICS = {
    "enabled": "79994230-4b04-40cd-85c9-02dd1a8d4dd0",
    "status": "097a2751-ca0d-432f-87b5-7d2f31e45551",
    "bin": "5bcbf6b1-de80-94b6-0f4b-99fb984707b6",
    "night": "37988f00-ea39-4a2d-9983-afad6535c02e",
    "cleaning": "efe4bd77-0600-47d7-b3f6-dc81af0d9aaf",
}
STATUS = {0: "off", 1: "making_ice", 2: "needs_water", 3: "bin_full", 4: "cleaning"}
CONF_PAIR = "pair"
CONF_INTERVAL = "poll_interval"
CONF_SOURCE = "bluetooth_source"
DEFAULT_INTERVAL = 10
