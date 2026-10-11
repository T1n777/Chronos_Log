#!/usr/bin/env python3

import json
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

SEVERITIES = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

SEVERITY_RANK: Dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

SEVERITY_DSCP: Dict[str, int] = {
    "DEBUG": 0,
    "INFO": 10,
    "WARNING": 26,
    "ERROR": 34,
    "CRITICAL": 46,
}

DEFAULT_SERVER_PORT = 5514
DEFAULT_CONGESTION_PORT = 9999
BUFFER_SIZE = 65535

def dscp_to_tos(dscp: int) -> int:

    if not (0 <= dscp <= 63):
        raise ValueError(f"DSCP must be between 0 and 63, got {dscp}")
    return dscp << 2

def tos_to_dscp(tos: int) -> int:

    return (tos & 0xFC) >> 2

def get_tos_for_severity(severity: str) -> int:

    sev_upper = severity.upper()
    dscp = SEVERITY_DSCP.get(sev_upper, 0)
    return dscp_to_tos(dscp)

def get_severity_for_dscp(dscp: int) -> str:

    for sev, val in SEVERITY_DSCP.items():
        if val == dscp:
            return sev
    return "DEBUG"

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

    try:
        decoded = data.decode("utf-8")
        entry = json.loads(decoded)

        required_keys = {"seq", "severity", "timestamp", "host", "message", "send_time"}
        missing = required_keys - entry.keys()
        if missing:
            return None, f"Missing required fields: {missing}"

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
