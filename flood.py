#!/usr/bin/env python3
"""
flood.py - Controlled UDP Traffic and Congestion Generator

Generates high-rate UDP background traffic at a target bandwidth (Mbps)
to deliberately saturate network links (e.g. Mininet bottleneck link s2-s4),
triggering controlled queue backlog, bufferbloat, and packet drops for QoS evaluation.
"""

import sys
import time
import socket
import argparse
from typing import Optional


def run_flood(
    target_ip: str,
    target_port: int,
    rate_mbps: float,
    duration: int,
    packet_size: int = 1400,
    report_interval: float = 2.0,
) -> None:
    """
    Generate controlled UDP traffic to saturate the network.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest_addr = (target_ip, target_port)

    # Pre-generate dummy byte payload
    payload = b"X" * max(packet_size, 64)
    actual_pkt_len = len(payload)

    # Calculate transmission intervals
    # Total bits per second = rate_mbps * 1,000,000
    # Bits per packet (Ethernet payload) = actual_pkt_len * 8
    bits_per_sec = rate_mbps * 1_000_000.0
    bits_per_pkt = actual_pkt_len * 8.0
    pkts_per_sec = bits_per_sec / bits_per_pkt
    interval = 1.0 / pkts_per_sec if pkts_per_sec > 0 else 0.001

    print("=" * 65)
    print(" Chronos Controlled UDP Traffic Generator")
    print("=" * 65)
    print(f" Target           : {target_ip}:{target_port}")
    print(f" Target Bandwidth : {rate_mbps:.2f} Mbps ({pkts_per_sec:.1f} pkts/s)")
    print(f" Packet Size      : {actual_pkt_len} bytes")
    print(f" Duration         : {duration} seconds")
    print("=" * 65)

    start_time = time.time()
    end_time = start_time + duration
    next_report = start_time + report_interval

    packets_sent = 0
    bytes_sent = 0

    try:
        while True:
            now = time.time()
            if now >= end_time:
                break

            sock.sendto(payload, dest_addr)
            packets_sent += 1
            bytes_sent += actual_pkt_len

            if now >= next_report:
                elapsed = now - start_time
                current_mbps = (bytes_sent * 8.0) / (elapsed * 1_000_000.0)
                print(
                    f" [FLOOD] Elapsed: {elapsed:5.1f}s | Sent: {packets_sent:<8} pkts "
                    f"| Achieved Throughput: {current_mbps:5.2f} Mbps"
                )
                next_report = now + report_interval

            # Precise timing control with burst compensation
            expected_time = start_time + (packets_sent * interval)
            sleep_time = expected_time - time.time()
            if sleep_time > 0.0005:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[INFO] Flood traffic stopped early by user.")
    finally:
        total_elapsed = max(time.time() - start_time, 0.001)
        actual_mbps = (bytes_sent * 8.0) / (total_elapsed * 1_000_000.0)
        sock.close()

        print("\n" + "=" * 65)
        print(" Flood Generation Summary")
        print("=" * 65)
        print(f" Total Duration         : {total_elapsed:.2f} seconds")
        print(f" Total Packets Sent     : {packets_sent}")
        print(f" Total Data Sent        : {bytes_sent / (1024 * 1024):.2f} MB")
        print(f" Average Bandwidth Rate : {actual_mbps:.2f} Mbps")
        print("=" * 65)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Controlled UDP packet flooder to generate network congestion."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Destination IP address (e.g., 10.0.0.4 or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9999,
        help="Destination UDP port (default: 9999, avoids interfering with port 5514)",
    )
    parser.add_argument(
        "--rate-mbps",
        type=float,
        default=5.0,
        help="Target transmission bandwidth in Mbps (default: 5.0)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration of flood transmission in seconds (default: 60)",
    )
    parser.add_argument(
        "--packet-size",
        type=int,
        default=1400,
        help="UDP payload size in bytes (default: 1400)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_flood(
        target_ip=args.target,
        target_port=args.port,
        rate_mbps=args.rate_mbps,
        duration=args.duration,
        packet_size=args.packet_size,
    )
