#!/usr/bin/env python3
"""
protocol.py - Chronos Log Protocol (CLP) Definitions and Constants

This module provides common definitions, severity levels, DiffServ (DSCP)
and IP Type-of-Service (TOS) mappings, default network parameters,
and message serialization helpers used by both clients and the log server.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# Standard severity levels ordered from lowest to highest
SEVERITIES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Numerical rank for severity comparison
SEVERITY_RANK: Dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

# Differentiated Services Code Point (DSCP) values (6-bit values: 0-63)
# Mapping aligns with IETF RFC 2474, RFC 2597, and RFC 3246
SEVERITY_DSCP: Dict[str, int] = {
    "DEBUG": 0,       # Best Effort (BE) - DSCP 0
    "INFO": 10,       # Assured Forwarding 11 (AF11) - DSCP 10
    "WARNING": 26,    # Assured Forwarding 31 (AF31) - DSCP 26
    "ERROR": 34,      # Assured Forwarding 41 (AF41) - DSCP 34
    "CRITICAL": 46,   # Expedited Forwarding (EF) - DSCP 46
}

# Default network configuration
DEFAULT_SERVER_PORT = 5514
DEFAULT_CONGESTION_PORT = 9999
BUFFER_SIZE = 65535


def dscp_to_tos(dscp: int) -> int:
    """
    Convert a 6-bit DSCP value to an 8-bit IPv4 TOS byte.
    In the IPv4 header, DSCP occupies the upper 6 bits, while ECN occupies
    the lower 2 bits. Hence, TOS = (DSCP << 2).
    """
    if not (0 <= dscp <= 63):
        raise ValueError(f"DSCP must be between 0 and 63, got {dscp}")
    return dscp << 2


def tos_to_dscp(tos: int) -> int:
    """
    Extract the 6-bit DSCP value from an 8-bit IPv4 TOS byte.
    """
    return (tos & 0xFC) >> 2


def get_tos_for_severity(severity: str) -> int:
    """
    Return the 8-bit TOS byte for a given severity string.
    """
    sev_upper = severity.upper()
    dscp = SEVERITY_DSCP.get(sev_upper, 0)
    return dscp_to_tos(dscp)


def get_severity_for_dscp(dscp: int) -> str:
    """
    Return the corresponding severity string for a given DSCP value.
    Defaults to 'DEBUG' if no direct match is found.
    """
    for sev, val in SEVERITY_DSCP.items():
        if val == dscp:
            return sev
    return "DEBUG"


# Precomputed TOS values for quick lookup
SEVERITY_TOS: Dict[str, int] = {
    sev: dscp_to_tos(dscp) for sev, dscp in SEVERITY_DSCP.items()
}


def create_log_payload(
    seq: int,
    severity: str,
    host: str,
    message: str,
    timestamp: Optional[str] = None,
    send_time: Optional[float] = None,
) -> bytes:
    """
    Construct a JSON-encoded byte payload for transmission over UDP.
    """
    sev_upper = severity.upper()
    if sev_upper not in SEVERITY_RANK:
        sev_upper = "INFO"

    now_time = time.time()
    if send_time is None:
        send_time = now_time

    if timestamp is None:
        timestamp = datetime.fromtimestamp(send_time).isoformat()

    entry: Dict[str, Any] = {
        "seq": int(seq),
        "severity": sev_upper,
        "timestamp": timestamp,
        "host": str(host),
        "message": str(message),
        "send_time": float(send_time),
    }

    return json.dumps(entry, separators=(",", ":")).encode("utf-8")


def parse_log_payload(data: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse a received raw UDP datagram into a Python dictionary.
    Returns (dict, None) on success, or (None, error_message) on failure.
    """
    try:
        decoded = data.decode("utf-8")
        entry = json.loads(decoded)

        # Validate mandatory fields
        required_keys = {"seq", "severity", "timestamp", "host", "message", "send_time"}
        missing = required_keys - entry.keys()
        if missing:
            return None, f"Missing required fields: {missing}"

        # Normalize severity
        entry["severity"] = str(entry["severity"]).upper()
        if entry["severity"] not in SEVERITY_RANK:
            entry["severity"] = "INFO"

        return entry, None
    except UnicodeDecodeError as err:
        return None, f"UTF-8 decode error: {err}"
    except json.JSONDecodeError as err:
        return None, f"JSON parse error: {err}"
    except Exception as err:
        return None, f"Unexpected parsing error: {err}"
