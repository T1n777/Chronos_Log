#!/usr/bin/env python3
"""
Chronos Centralized Log Aggregation Server
Listens for asynchronous UDP datagrams on port 5514, computes one-way network transit latency,
detects packet loss via monotonic sequence gap analysis, categorizes logs by severity,
and periodically prints and exports performance reports.
"""

import os
import sys
import time
import json
import socket
import signal
import threading
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

from protocol import (
    SEVERITIES,
    DEFAULT_SERVER_PORT,
    BUFFER_SIZE,
    parse_log_payload,
)


class LogServer:
    """
    Multi-threaded UDP log ingestion server with real-time telemetry and loss accounting.
    """

    def __init__(
        self,
        bind_ip: str = "0.0.0.0",
        port: int = DEFAULT_SERVER_PORT,
        stats_interval: float = 5.0,
        output_dir: str = "results",
        quiet: bool = False,
    ):
        # Server network binding configuration
        self.bind_ip = bind_ip
        self.port = port
        self.stats_interval = stats_interval  # Interval between terminal performance tables
        self.output_dir = output_dir          # Directory where categorized JSON reports will be written
        self.quiet = quiet                    # If True, suppresses individual per-packet logs

        # Step 1: Create an IPv4 UDP datagram socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Step 2: Enable SO_REUSEADDR so the port can be rebound immediately upon restart
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Step 3: Bind socket to network interface and listening port
        self.sock.bind((self.bind_ip, self.port))

        # Categorized log storage partitioned into 5 independent lists by severity
        self.categorized_logs: Dict[str, List[Dict[str, Any]]] = {
            sev: [] for sev in SEVERITIES
        }

        # Delivery latency measurements in milliseconds grouped by severity
        self.latencies: Dict[str, List[float]] = {sev: [] for sev in SEVERITIES}

        # Per-host sequence tracking table for detecting dropped datagrams
        self.host_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "expected_seq": 0,                    # Next expected sequence counter
                "received": 0,                        # Total packets delivered successfully
                "lost": 0,                            # Total packets dropped in transit
                "out_of_order": 0,                    # Out-of-order packet count
                "first_seen": None,                   # Timestamp of first packet received
                "last_seen": None,                    # Timestamp of most recent packet received
                "severities": {sev: 0 for sev in SEVERITIES},  # Per-severity count for this host
            }
        )

        # Thread synchronization lock protecting shared data structures
        self.lock = threading.Lock()

        # Operational state flags and timing counters
        self.is_running = True
        self.start_time = time.time()
        self.total_received = 0
        self.total_lost = 0

    def start(self) -> None:
        """
        Starts the log server:
        1. Spawns background periodic statistics reporting thread.
        2. Enters main blocking socket recvfrom() loop.
        3. Cleans up and exports reports upon termination.
        """
        # Print initialization banner
        print("=" * 70)
        print(" Chronos Centralized Log Aggregation Server")
        print("=" * 70)
        print(f" Binding Address  : {self.bind_ip}:{self.port} (UDP)")
        print(f" Output Directory : {os.path.abspath(self.output_dir)}")
        print(f" Stats Interval   : {self.stats_interval:.1f} seconds")
        print(" Status           : Ready to receive datagrams. Press Ctrl+C to exit.")
        print("=" * 70)

        # Ensure output directory exists on disk
        os.makedirs(self.output_dir, exist_ok=True)

        # Spawn background daemon thread for periodic metric reporting
        reporter_thread = threading.Thread(target=self._stats_reporter_loop, daemon=True)
        reporter_thread.start()

        try:
            # Main UDP datagram reception loop
            while self.is_running:
                # Blocks until an incoming UDP datagram arrives
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                # Ingest and process packet contents
                self._process_datagram(data, addr)
        except OSError:
            # Socket closed during shutdown; exit loop cleanly
            pass
        except KeyboardInterrupt:
            # Keyboard interrupt signal caught
            print("\n[INFO] Shutdown signal received.")
        finally:
            # Ensure cleanup and file export occurs
            self.stop()

    def stop(self) -> None:
        """
        Stops the server gracefully:
        Closes socket, prints final performance table, and writes JSON files.
        """
        if not self.is_running:
            return
        self.is_running = False

        # Close listening socket to release port
        try:
            self.sock.close()
        except Exception:
            pass

        # Print final console summary and export JSON reports to disk
        self._print_final_summary()
        self._export_json_reports()

    def _process_datagram(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Parses datagram, calculates transit latency, updates sequence loss metrics,
        and categorizes log into severity queues under a thread lock.
        """
        # Record receipt timestamp immediately to maximize latency measurement accuracy
        receive_time = time.time()

        # Parse and validate protocol wire format
        entry, err = parse_log_payload(data)

        # Check for malformed packets or decoding failures
        if err or entry is None:
            if not self.quiet:
                print(f"[MALFORMED] From {addr[0]}:{addr[1]}: {err}", file=sys.stderr)
            return

        # Extract message fields
        severity = entry["severity"]
        host = entry["host"]
        seq = entry["seq"]
        send_time = entry["send_time"]

        # Calculate transit delay (one-way latency) in milliseconds
        latency_ms = max((receive_time - send_time) * 1000.0, 0.0)
        entry["receive_time"] = receive_time
        entry["delivery_latency_ms"] = round(latency_ms, 3)

        # Acquire lock to safely update aggregate shared structures
        with self.lock:
            # Step A: Append entry to appropriate categorized severity list
            self.categorized_logs[severity].append(entry)
            self.latencies[severity].append(latency_ms)
            self.total_received += 1

            # Step B: Update host tracking record
            h_stat = self.host_stats[host]
            if h_stat["first_seen"] is None:
                h_stat["first_seen"] = receive_time
            h_stat["last_seen"] = receive_time
            h_stat["severities"][severity] += 1
            h_stat["received"] += 1

            # Step C: Detect dropped UDP packets via sequence gap analysis
            expected = h_stat["expected_seq"]
            if seq > expected:
                # Gap detected: packets were dropped in transit (e.g., bottleneck queue drop)
                gap = seq - expected
                h_stat["lost"] += gap
                self.total_lost += gap
                h_stat["expected_seq"] = seq + 1
            elif seq == expected:
                # Normal in-order arrival
                h_stat["expected_seq"] = seq + 1
            else:
                # Packet arrived out of order (sequence was lower than expected)
                h_stat["out_of_order"] += 1

        # Print per-packet log message if quiet mode is disabled
        if not self.quiet:
            ts_str = entry.get("timestamp", datetime.now().isoformat())
            print(
                f"[{severity:<8}] from {host:<4} (seq={seq:<5} lat={latency_ms:6.2f}ms) : {entry['message']}"
            )

    def _stats_reporter_loop(self) -> None:
        """
        Background loop: wakes up every stats_interval seconds to print telemetry metrics.
        """
        while self.is_running:
            time.sleep(self.stats_interval)
            if self.is_running:
                self._print_stats_table()

    def _print_stats_table(self) -> None:
        """
        Renders a structured terminal table displaying throughput, packet loss,
        per-severity latency statistics, and per-host breakdown.
        """
        with self.lock:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elapsed = max(time.time() - self.start_time, 0.001)
            total_pkts = self.total_received + self.total_lost
            overall_loss_pct = (self.total_lost / total_pkts * 100.0) if total_pkts > 0 else 0.0

            # Header section
            print("\n" + "=" * 76)
            print(f" Chronos Log Aggregator Metrics [{now_str}] (Uptime: {elapsed:.1f}s)")
            print("=" * 76)
            print(
                f" Received: {self.total_received:<6} | Estimated Lost: {self.total_lost:<6} "
                f"| Loss Rate: {overall_loss_pct:5.2f}% | Throughput: {self.total_received/elapsed:5.1f} pkts/s"
            )
            print("-" * 76)
            print(
                f" {'Severity':<10} {'Received':<10} {'Share':<9} {'Avg Lat (ms)':<15} "
                f"{'Min Lat':<12} {'Max Lat':<12}"
            )
            print("-" * 76)

            # Per-severity metrics display
            for sev in SEVERITIES:
                cnt = len(self.categorized_logs[sev])
                share = (cnt / self.total_received * 100.0) if self.total_received > 0 else 0.0
                lats = self.latencies[sev]
                if lats:
                    avg_lat = sum(lats) / len(lats)
                    min_lat = min(lats)
                    max_lat = max(lats)
                    print(
                        f" {sev:<10} {cnt:<10} {share:>6.1f}%  {avg_lat:>12.2f}ms "
                        f"{min_lat:>9.2f}ms  {max_lat:>9.2f}ms"
                    )
                else:
                    print(f" {sev:<10} {cnt:<10} {share:>6.1f}%          N/A          N/A          N/A")

            # Per-host breakdown
            if self.host_stats:
                print("-" * 76)
                print(f" Per-Host Overview:")
                for h_name, h_data in sorted(self.host_stats.items()):
                    h_total = h_data["received"] + h_data["lost"]
                    h_loss = (h_data["lost"] / h_total * 100.0) if h_total > 0 else 0.0
                    print(
                        f"   * {h_name:<6} -> Received: {h_data['received']:<5} | Lost: {h_data['lost']:<5} "
                        f"| Loss Rate: {h_loss:5.1f}% | Out-of-Order: {h_data['out_of_order']}"
                    )
            print("=" * 76 + "\n")

    def _print_final_summary(self) -> None:
        """
        Prints the conclusive performance table upon server termination.
        """
        print("\n" + "=" * 76)
        print(" FINAL SYSTEM PERFORMANCE REPORT")
        print("=" * 76)
        self._print_stats_table()

    def _export_json_reports(self) -> None:
        """
        Serializes categorized logs and aggregate experiment statistics to JSON files on disk.
        Produces:
          - logs_debug.json, logs_info.json, logs_warning.json, logs_error.json, logs_critical.json
          - server_summary.json (comprehensive run metrics)
        """
        with self.lock:
            # Export individual partitioned severity log files
            for sev in SEVERITIES:
                filepath = os.path.join(self.output_dir, f"logs_{sev.lower()}.json")
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(self.categorized_logs[sev], f, indent=2)
                    print(f" [REPORT] Saved {len(self.categorized_logs[sev])} {sev} logs to: {filepath}")
                except IOError as err:
                    print(f"[ERROR] Failed writing {filepath}: {err}", file=sys.stderr)

            # Compute summary statistics
            elapsed = max(time.time() - self.start_time, 0.001)
            total_pkts = self.total_received + self.total_lost
            overall_loss = (self.total_lost / total_pkts * 100.0) if total_pkts > 0 else 0.0

            summary_data: Dict[str, Any] = {
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": round(elapsed, 2),
                "total_packets_received": self.total_received,
                "total_packets_lost": self.total_lost,
                "total_packets_transmitted": total_pkts,
                "overall_loss_rate_percent": round(overall_loss, 2),
                "throughput_pkts_per_sec": round(self.total_received / elapsed, 2),
                "severity_metrics": {},
                "host_metrics": {},
            }

            # Populate per-severity summary statistics
            for sev in SEVERITIES:
                lats = self.latencies[sev]
                cnt = len(self.categorized_logs[sev])
                summary_data["severity_metrics"][sev] = {
                    "count": cnt,
                    "avg_latency_ms": round(sum(lats) / len(lats), 3) if lats else 0.0,
                    "min_latency_ms": round(min(lats), 3) if lats else 0.0,
                    "max_latency_ms": round(max(lats), 3) if lats else 0.0,
                }

            # Populate per-host metrics
            for h_name, h_data in self.host_stats.items():
                h_total = h_data["received"] + h_data["lost"]
                summary_data["host_metrics"][h_name] = {
                    "received": h_data["received"],
                    "lost": h_data["lost"],
                    "loss_rate_percent": round((h_data["lost"] / h_total * 100.0), 2) if h_total > 0 else 0.0,
                    "out_of_order": h_data["out_of_order"],
                    "severities": h_data["severities"],
                }

            # Write master summary JSON report
            summary_filepath = os.path.join(self.output_dir, "server_summary.json")
            try:
                with open(summary_filepath, "w", encoding="utf-8") as f:
                    json.dump(summary_data, f, indent=2)
                print(f" [REPORT] Aggregate summary saved to: {summary_filepath}")
            except IOError as err:
                print(f"[ERROR] Failed writing summary report: {err}", file=sys.stderr)


def parse_args():
    """
    Parses command-line arguments for server configuration.
    """
    parser = argparse.ArgumentParser(
        description="Centralized UDP Log Server with Categorization and Metrics."
    )
    # Listening network interface
    parser.add_argument(
        "--bind-ip",
        default="0.0.0.0",
        help="Network interface IP address to bind (default: 0.0.0.0)",
    )
    # Listening UDP port
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"UDP port to listen on (default: {DEFAULT_SERVER_PORT})",
    )
    # Reporting interval in seconds
    parser.add_argument(
        "--stats-interval",
        type=float,
        default=5.0,
        help="Interval in seconds between periodic console stats reports (default: 5.0)",
    )
    # Directory path for output JSON reports
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory to save output JSON logs and summary (default: results)",
    )
    # Quiet flag
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-datagram console logging and display only periodic tables",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Parse CLI flags and initialize LogServer instance
    args = parse_args()
    server = LogServer(
        bind_ip=args.bind_ip,
        port=args.port,
        stats_interval=args.stats_interval,
        output_dir=args.output_dir,
        quiet=args.quiet,
    )

    # Register OS signal handlers for graceful shutdown on SIGINT (Ctrl+C) and SIGTERM
    def _sig_handler(sig, frame):
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # Begin server listening loop
    server.start()
