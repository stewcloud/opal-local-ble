"""Protocol decoding, independent of Home Assistant."""
from .const import STATUS


def decode_byte(value: bytes | bytearray) -> int:
    """Reject empty replies; first-generation values are one byte."""
    if len(value) != 1:
        raise ValueError(f"Expected one byte, received {len(value)}")
    return value[0]


def status_name(value: int | None) -> str:
    return STATUS.get(value, "unknown")


def enabled_state(data: dict) -> bool | None:
    """Do not mistake a full bin or no water for the power being off."""
    if data.get("enabled") in (0, 1):
        return bool(data["enabled"])
    if data.get("status") in (0, 1):
        return data["status"] == 1
    return None
