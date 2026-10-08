#!/usr/bin/env python3
"""
log_client.py - UDP Log Client with IP TOS / DSCP Prioritization Marking

Generates and transmits structured application logs over UDP to a centralized
log server. Each datagram has its IPv4 Type of Service (TOS) header marked
according to its severity level (CRITICAL, ERROR, WARNING, INFO, DEBUG) to enable
network-layer QoS prioritization.
"""

import socket
import sys
import time
import random
import argparse
from typing import Dict, List, Tuple
from protocol import (
    SEVERITIES,
    SEVERITY_TOS,
    DEFAULT_SERVER_PORT,
    create_log_payload,
)

# Realistic message pools reflecting distributed application workloads
SAMPLE_LOG_MESSAGES: Dict[str, List[str]] = {
    "DEBUG": [
        "Memory cache hit ratio: 0.942 on key user_session_4920",
        "TCP connection pool active: 18 idle: 32 total: 50",
        "Garbage collection cycle completed in 14.2ms, reclaimed 48MB",
        "DNS lookup for db-replica-02.internal resolved in 2.1ms",
        "HTTP request headers parsed: length=412 content_type=application/json",
        "Thread pool worker thread #4 entered idle state",
    ],
    "INFO": [
        "User 10842 authenticated successfully from 192.168.1.45",
        "Order #94827 completed successfully, payment processed in 184ms",
        "Scheduled snapshot backup initiated for volume vol-08472",
        "HTTP 200 GET /api/v1/metrics handled in 32ms",
        "Microservice worker successfully registered with service registry",
        "SSL/TLS certificate renewal verified valid for 89 days",
    ],
    "WARNING": [
        "Disk utilization on /var/log exceeded warning threshold: 84.6%",
        "Upstream database latency spike detected: query took 840ms (>500ms)",
        "API rate limit reached 85% capacity for client api-key-prod-9",
        "Worker thread queue depth elevated: 142 items pending",
        "Retrying transient connection to payment-gateway (attempt 2 of 5)",
        "Memory consumption reached 78% of container cgroup allocation",
    ],
    "ERROR": [
        "Failed to write snapshot to remote storage: Network timeout after 5000ms",
        "OAuth2 token validation failed: Signature verification rejected",
        "Database transaction rolled back due to serialization deadlock",
        "Connection refused by cache cluster node redis-node-03:6379",
        "Failed to process image upload: Decoded payload corrupt",
        "RPC request to inventory-service failed with code 503 SERVICE_UNAVAILABLE",
    ],
    "CRITICAL": [
        "Primary database connection lost: No reachable replica in cluster",
        "Fatal: Memory allocation failed, out of memory (OOM) killer invoked",
        "Raft consensus quorum lost: Cluster state entered read-only degraded mode",
        "Filesystem corruption detected on primary data partition /data",
        "Security alert: Multiple invalid administrative access attempts detected",
        "Core payment pipeline halted: Gateway endpoint completely unreachable",
    ],
}

# Default probability distribution: common DEBUG/INFO, rare CRITICAL
SEVERITY_WEIGHTS: Dict[str, int] = {
    "DEBUG": 35,
    "INFO": 35,
    "WARNING": 15,
    "ERROR": 10,
    "CRITICAL": 5,
}


def pick_severity_and_message(selected_severity: str) -> Tuple[str, str]:
    """
    Select severity and a corresponding realistic log message.
    """
    if selected_severity != "mixed":
        sev = selected_severity.upper()
        if sev not in SAMPLE_LOG_MESSAGES:
            sev = "INFO"
    else:
        severities = list(SEVERITY_WEIGHTS.keys())
        weights = list(SEVERITY_WEIGHTS.values())
        sev = random.choices(severities, weights=weights, k=1)[0]

    msg = random.choice(SAMPLE_LOG_MESSAGES[sev])
    return sev, msg


def run_client(
    server_ip: str,
    server_port: int,
    hostname: str,
    rate: float,
    count: int,
    severity_mode: str,
    quiet: bool = False,
) -> None:
    """
    Main client transmission loop.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest_addr = (server_ip, server_port)

    # Transmission counters
    sent_counts: Dict[str, int] = {sev: 0 for sev in SEVERITIES}
    total_sent = 0
    seq = 0

    print("=" * 65)
    print(" Chronos UDP Log Client")
    print("=" * 65)
    print(f" Target Server : {server_ip}:{server_port}")
    print(f" Source Host   : {hostname}")
    print(f" Mode          : {severity_mode}")
    print(f" Rate          : {rate:.3f}s interval ({1.0/rate:.1f} logs/s)")
    print(f" Count         : {'Infinite (Ctrl+C to stop)' if count <= 0 else count}")
    print("=" * 65)

    start_time = time.time()

    try:
        while True:
            sev, msg = pick_severity_and_message(severity_mode)
            payload = create_log_payload(
                seq=seq,
                severity=sev,
                host=hostname,
                message=msg,
            )

            # Retrieve TOS byte for this severity
            tos_val = SEVERITY_TOS.get(sev, 0)

            # Apply IP_TOS socket option before sending datagram
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_val)
            except OSError as err:
                # Some environments might restrict raw TOS manipulation
                if seq == 0:
                    print(f"[WARN] Failed to set IP_TOS ({err}). Proceeding with default TOS.", file=sys.stderr)

            # Transmit datagram over UDP
            sock.sendto(payload, dest_addr)

            sent_counts[sev] += 1
            total_sent += 1

            if not quiet:
                print(f"[{sev:<8}] seq={seq:<5} TOS=0x{tos_val:02X} -> {msg}")

            seq += 1
            if count > 0 and total_sent >= count:
                break

            if rate > 0:
                time.sleep(rate)

    except KeyboardInterrupt:
        print("\n[INFO] Transmission stopped by user (Ctrl+C).")
    finally:
        elapsed = max(time.time() - start_time, 0.001)
        sock.close()

        print("\n" + "=" * 65)
        print(" Transmission Summary")
        print("=" * 65)
        print(f" Total Logs Transmitted : {total_sent}")
        print(f" Elapsed Time           : {elapsed:.2f} seconds")
        print(f" Average Output Rate    : {total_sent / elapsed:.2f} logs/sec")
        print("-" * 65)
        print(f" {'Severity':<12} {'Count':<10} {'Percentage':<10}")
        print("-" * 65)
        for s in SEVERITIES:
            c = sent_counts[s]
            pct = (c / total_sent * 100.0) if total_sent > 0 else 0.0
            print(f" {s:<12} {c:<10} {pct:>6.1f}%")
        print("=" * 65)


def parse_args():
    parser = argparse.ArgumentParser(
        description="UDP Log Client with DSCP/TOS priority tagging for SDN."
    )
    parser.add_argument(
        "--server-ip",
        required=True,
        help="IP address of the centralized log server (e.g., 10.0.0.4 or 127.0.0.1)",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"UDP port of the log server (default: {DEFAULT_SERVER_PORT})",
    )
    parser.add_argument(
        "--hostname",
        default=socket.gethostname(),
        help="Identifier of this client host (default: system hostname)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=0.1,
        help="Delay between outgoing log messages in seconds (default: 0.1s)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of messages to transmit. 0 means continuous (default: 0)",
    )
    parser.add_argument(
        "--severity",
        choices=["mixed", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="mixed",
        help="Severity generation mode (default: mixed)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-packet console logs and display only summary",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_client(
        server_ip=args.server_ip,
        server_port=args.server_port,
        hostname=args.hostname,
        rate=args.rate,
        count=args.count,
        severity_mode=args.severity,
        quiet=args.quiet,
    )
