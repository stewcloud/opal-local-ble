"""Diagnostics without device addresses, names or config-entry identifiers."""
async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "integration_version": "0.2.1",
        "last_update_success": coordinator.last_update_success,
        "poll_interval": coordinator.update_interval.total_seconds(),
        "pair_on_connect": entry.options.get("pair", True),
        "source_mode": "automatic" if entry.options.get("bluetooth_source", "auto") == "auto" else "selected",
        "raw_status": coordinator.data,
        "note": "Controls validated on a first-generation GE Opal. Proxy failover requires live validation.",
    }
