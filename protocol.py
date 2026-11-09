#!/usr/bin/env python3
"""
Chronos Distributed Logging Protocol Specification
Defines the wire format, severity levels, RFC 2474 / RFC 3246 DiffServ mappings,
and serialization/deserialization helpers for network log datagrams.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

# Standard Syslog / Application Severity Levels in order of increasing importance
SEVERITIES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Numeric priority ranking used for severity comparison and default fallback validation
SEVERITY_RANK: Dict[str, int] = {
    "DEBUG": 0,      # Informational traces with lowest priority
    "INFO": 1,       # Standard operational events
    "WARNING": 2,    # Non-critical anomalies or elevated thresholds
    "ERROR": 3,      # Failure events impacting a transaction
    "CRITICAL": 4,   # Fatal system-wide failure or data loss
}

# Differentiated Services Code Point (DSCP) mapping per RFC 2474 / RFC 3246
# DSCP values occupy the upper 6 bits of the IPv4 Type of Service (TOS) octet.
SEVERITY_DSCP: Dict[str, int] = {
    "DEBUG": 0,      # Best Effort (CS0) - lowest transmission priority
    "INFO": 10,      # Assured Forwarding 11 (AF11) - regular telemetry
    "WARNING": 26,   # Assured Forwarding 31 (AF31) - elevated monitoring
    "ERROR": 34,     # Assured Forwarding 41 (AF41) - high-priority alert
    "CRITICAL": 46,  # Expedited Forwarding (EF) - VIP queue, lowest latency
}

# Default UDP port for centralized log aggregation server
DEFAULT_SERVER_PORT = 5514

# Default UDP port for background congestion traffic (avoids polluting port 5514)
DEFAULT_CONGESTION_PORT = 9999

# Maximum UDP packet buffer size (64 KB maximum IP packet ceiling)
BUFFER_SIZE = 65535


def dscp_to_tos(dscp: int) -> int:
    """
    Converts a 6-bit DSCP value (0-63) into an 8-bit IPv4 Type of Service (TOS) byte.
    RFC 2474 defines DSCP in bits 7-2 of the TOS octet; bits 1-0 are reserved for ECN.
    Shifting left by 2 bits aligns the 6-bit DSCP into the upper 6 bits of the byte.
    """
    # Verify DSCP fits within 6-bit unsigned range (2^6 = 64 possible values)
    if not (0 <= dscp <= 63):
        raise ValueError(f"DSCP must be between 0 and 63, got {dscp}")
    # Shift left by 2 to align with bits 7..2 of the IPv4 TOS header byte
    return dscp << 2


def tos_to_dscp(tos: int) -> int:
    """
    Extracts the 6-bit DSCP value from an 8-bit IPv4 TOS byte.
    Masks out the lowest 2 bits (ECN) using 0xFC (binary 11111100), then right-shifts by 2.
    """
    # Bitwise AND with 0xFC clears bits 0 and 1 (ECN field), then shift right by 2
    return (tos & 0xFC) >> 2


def get_tos_for_severity(severity: str) -> int:
    """
    Retrieves the exact 8-bit IPv4 TOS byte for a given severity string.
    Defaults to DSCP 0 (0x00) if the severity name is not recognized.
    """
    # Normalize input string to uppercase
    sev_upper = severity.upper()
    # Lookup DSCP number from mapping, fallback to Best Effort (0)
    dscp = SEVERITY_DSCP.get(sev_upper, 0)
    # Convert DSCP to TOS byte
    return dscp_to_tos(dscp)


def get_severity_for_dscp(dscp: int) -> str:
    """
    Reverse lookup: finds the severity level corresponding to a 6-bit DSCP value.
    Defaults to DEBUG if no match is found.
    """
    # Iterate through mapped DSCP pairs to match incoming code point
    for sev, val in SEVERITY_DSCP.items():
        if val == dscp:
            return sev
    # Fallback to DEBUG if unmapped
    return "DEBUG"


# Pre-calculated lookup table mapping severity names directly to their IPv4 TOS integer byte
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
    Constructs a JSON-formatted log message payload and serializes it to UTF-8 bytes.
    Includes monotonic sequence number, high-resolution sender timestamp, and origin hostname.
    """
    # Ensure severity name is uppercase and valid; fallback to INFO if invalid
    sev_upper = severity.upper()
    if sev_upper not in SEVERITY_RANK:
        sev_upper = "INFO"

    # Capture current Unix epoch timestamp if not explicitly supplied
    now_time = time.time()
    if send_time is None:
        send_time = now_time

    # Generate ISO-8601 human-readable timestamp from sender epoch time
    if timestamp is None:
        timestamp = datetime.fromtimestamp(send_time).isoformat()

    # Build canonical payload dictionary
    entry: Dict[str, Any] = {
        "seq": int(seq),                       # Monotonic sequence counter for packet loss detection
        "severity": sev_upper,                 # Severity category string (DEBUG..CRITICAL)
        "timestamp": timestamp,                # Human-readable ISO-8601 timestamp string
        "host": str(host),                     # Hostname or IP of producing microservice
        "message": str(message),               # Log event description text
        "send_time": float(send_time),         # High-precision sender float epoch for latency calculation
    }

    # Compact JSON encoding without extra whitespace to minimize UDP datagram size
    return json.dumps(entry, separators=(",", ":")).encode("utf-8")


def parse_log_payload(data: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parses and validates incoming raw bytes from a UDP datagram.
    Returns (entry_dict, None) on success, or (None, error_message) on malformed input.
    Ensures server resiliency against malformed packets.
    """
    try:
        # Decode raw UDP bytes into UTF-8 text
        decoded = data.decode("utf-8")
        # Parse JSON document into dictionary
        entry = json.loads(decoded)

        # Enforce presence of all mandatory protocol fields
        required_keys = {"seq", "severity", "timestamp", "host", "message", "send_time"}
        missing = required_keys - entry.keys()
        if missing:
            return None, f"Missing required fields: {missing}"

        # Standardize severity casing and validate against recognized severities
        entry["severity"] = str(entry["severity"]).upper()
        if entry["severity"] not in SEVERITY_RANK:
            entry["severity"] = "INFO"

        return entry, None

    except UnicodeDecodeError as err:
        # Gracefully handle corrupt non-UTF-8 bytes
        return None, f"UTF-8 decode error: {err}"
    except json.JSONDecodeError as err:
        # Gracefully handle corrupted or truncated JSON payloads
        return None, f"JSON parse error: {err}"
    except Exception as err:
        # Catch-all for unexpected parsing failures
        return None, f"Unexpected parsing error: {err}"
