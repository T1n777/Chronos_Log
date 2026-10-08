#!/usr/bin/env python3
"""
test_suite.py - Comprehensive Automated Verification Test Suite for Chronos Log

Tests:
1. Protocol unit tests (DSCP/TOS bitwise operations, schemas, payload parsing).
2. End-to-end socket communication (multithreaded server + client).
3. Packet loss gap detection via sequence numbers.
4. Severity categorization into distinct data structures and JSON exports.
5. Latency calculation accuracy.
6. UDP traffic flooder throughput and rate limiting.
7. Results analysis and CSV/report generation.
"""

import os
import sys
import time
import json
import socket
import shutil
import unittest
import threading
from typing import Dict, Any, List

# Ensure Chronos_Log directory is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from protocol import (
    SEVERITIES,
    SEVERITY_DSCP,
    SEVERITY_TOS,
    dscp_to_tos,
    tos_to_dscp,
    get_tos_for_severity,
    get_severity_for_dscp,
    create_log_payload,
    parse_log_payload,
)
from log_server import LogServer
from log_client import pick_severity_and_message
from flood import run_flood
from analyze_results import (
    load_run_data,
    generate_synthetic_benchmark,
    print_comparison_table,
)


class TestProtocol(unittest.TestCase):
    """
    Unit tests for protocol constants, RFC DSCP mappings, and serialization.
    """

    def test_dscp_tos_conversions(self):
        """Verify DSCP to TOS bitwise shift operations align with RFC standards."""
        # CRITICAL -> EF (Expedited Forwarding) -> DSCP 46 -> TOS 0xB8 (184)
        self.assertEqual(dscp_to_tos(46), 0xB8)
        self.assertEqual(tos_to_dscp(0xB8), 46)
        self.assertEqual(get_tos_for_severity("CRITICAL"), 0xB8)

        # ERROR -> AF41 -> DSCP 34 -> TOS 0x88 (136)
        self.assertEqual(dscp_to_tos(34), 0x88)
        self.assertEqual(tos_to_dscp(0x88), 34)
        self.assertEqual(get_tos_for_severity("ERROR"), 0x88)

        # WARNING -> AF31 -> DSCP 26 -> TOS 0x68 (104)
        self.assertEqual(dscp_to_tos(26), 0x68)
        self.assertEqual(tos_to_dscp(0x68), 26)
        self.assertEqual(get_tos_for_severity("WARNING"), 0x68)

        # INFO -> AF11 -> DSCP 10 -> TOS 0x28 (40)
        self.assertEqual(dscp_to_tos(10), 0x28)
        self.assertEqual(tos_to_dscp(0x28), 10)
        self.assertEqual(get_tos_for_severity("INFO"), 0x28)

        # DEBUG -> BE -> DSCP 0 -> TOS 0x00 (0)
        self.assertEqual(dscp_to_tos(0), 0x00)
        self.assertEqual(tos_to_dscp(0x00), 0)
        self.assertEqual(get_tos_for_severity("DEBUG"), 0x00)

    def test_invalid_dscp_raises_value_error(self):
        """Verify invalid DSCP outside 0-63 range raises ValueError."""
        with self.assertRaises(ValueError):
            dscp_to_tos(64)
        with self.assertRaises(ValueError):
            dscp_to_tos(-1)

    def test_payload_creation_and_parsing(self):
        """Verify payload serialization, schema compliance, and deserialization."""
        test_msg = "Database replication latency high"
        now = time.time()
        raw = create_log_payload(
            seq=42,
            severity="critical",
            host="h1",
            message=test_msg,
            send_time=now,
        )
        self.assertIsInstance(raw, bytes)

        parsed, err = parse_log_payload(raw)
        self.assertIsNone(err)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["seq"], 42)
        self.assertEqual(parsed["severity"], "CRITICAL")
        self.assertEqual(parsed["host"], "h1")
        self.assertEqual(parsed["message"], test_msg)
        self.assertAlmostEqual(parsed["send_time"], now, places=3)

    def test_malformed_payload_handling(self):
        """Verify server reject malformed or incomplete datagrams."""
        # Non-JSON bytes
        entry, err = parse_log_payload(b"Not valid JSON")
        self.assertIsNone(entry)
        self.assertIn("JSON parse error", err)

        # Incomplete JSON (missing required keys)
        incomplete = json.dumps({"seq": 1, "host": "h1"}).encode("utf-8")
        entry, err = parse_log_payload(incomplete)
        self.assertIsNone(entry)
        self.assertIn("Missing required fields", err)


class TestSocketIntegration(unittest.TestCase):
    """
    End-to-end integration tests using live UDP sockets on localhost.
    """

    TEST_PORT = 15514
    TEST_DIR = os.path.join(SCRIPT_DIR, "test_output")

    def setUp(self):
        if os.path.exists(self.TEST_DIR):
            shutil.rmtree(self.TEST_DIR)
        os.makedirs(self.TEST_DIR, exist_ok=True)

        self.server = LogServer(
            bind_ip="127.0.0.1",
            port=self.TEST_PORT,
            stats_interval=1.0,
            output_dir=self.TEST_DIR,
            quiet=True,
        )
        self.server_thread = threading.Thread(target=self.server.start, daemon=True)
        self.server_thread.start()
        time.sleep(0.3)  # Allow socket bind to complete

    def tearDown(self):
        self.server.stop()
        time.sleep(0.2)
        if os.path.exists(self.TEST_DIR):
            shutil.rmtree(self.TEST_DIR)

    def test_all_severities_categorization(self):
        """Transmit logs of each severity and verify accurate server categorization."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dest = ("127.0.0.1", self.TEST_PORT)

        # Transmit 2 messages of each severity
        seq = 0
        expected_counts = {}
        for sev in SEVERITIES:
            expected_counts[sev] = 2
            for i in range(2):
                msg = f"Test message {i} for {sev}"
                payload = create_log_payload(
                    seq=seq,
                    severity=sev,
                    host="h1",
                    message=msg,
                )
                tos = SEVERITY_TOS[sev]
                try:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
                except OSError:
                    pass
                sock.sendto(payload, dest)
                seq += 1
                time.sleep(0.01)

        sock.close()
        time.sleep(0.5)

        # Verify server in-memory tracking
        with self.server.lock:
            self.assertEqual(self.server.total_received, 10)
            self.assertEqual(self.server.total_lost, 0)
            for sev in SEVERITIES:
                actual_cnt = len(self.server.categorized_logs[sev])
                self.assertEqual(
                    actual_cnt,
                    2,
                    f"Expected 2 logs for {sev}, got {actual_cnt}",
                )

        # Stop server to flush JSON export files
        self.server.stop()
        time.sleep(0.3)

        # Verify JSON export files exist and contain records
        for sev in SEVERITIES:
            json_file = os.path.join(self.TEST_DIR, f"logs_{sev.lower()}.json")
            self.assertTrue(os.path.isfile(json_file), f"Missing {json_file}")
            with open(json_file, "r") as f:
                logs = json.load(f)
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[0]["severity"], sev)

        # Verify aggregate summary file
        summary_file = os.path.join(self.TEST_DIR, "server_summary.json")
        self.assertTrue(os.path.isfile(summary_file))
        with open(summary_file, "r") as f:
            summary = json.load(f)
        self.assertEqual(summary["total_packets_received"], 10)
        self.assertEqual(summary["total_packets_lost"], 0)

    def test_packet_loss_detection(self):
        """Simulate sequence number gaps and verify server detects dropped packets."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dest = ("127.0.0.1", self.TEST_PORT)

        # Send sequence: 0, 1 (no drop)
        # Skip 2, 3 -> Send 4 (gap = 2 lost)
        # Skip 5 -> Send 6 (gap = 1 lost)
        # Total sent: 4 datagrams. Total lost detected: 3 datagrams.
        seqs_to_send = [0, 1, 4, 6]

        for s in seqs_to_send:
            payload = create_log_payload(
                seq=s,
                severity="WARNING",
                host="h2",
                message=f"Sequence test {s}",
            )
            sock.sendto(payload, dest)
            time.sleep(0.02)

        sock.close()
        time.sleep(0.5)

        with self.server.lock:
            h2_stats = self.server.host_stats["h2"]
            self.assertEqual(h2_stats["received"], 4)
            self.assertEqual(h2_stats["lost"], 3)
            self.assertEqual(self.server.total_lost, 3)

    def test_latency_measurement(self):
        """Verify delivery latency is computed and is non-negative."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dest = ("127.0.0.1", self.TEST_PORT)

        send_ts = time.time()
        payload = create_log_payload(
            seq=0,
            severity="CRITICAL",
            host="h3",
            message="Latency test message",
            send_time=send_ts,
        )
        sock.sendto(payload, dest)
        sock.close()
        time.sleep(0.3)

        with self.server.lock:
            crit_logs = self.server.categorized_logs["CRITICAL"]
            self.assertEqual(len(crit_logs), 1)
            entry = crit_logs[0]
            self.assertIn("delivery_latency_ms", entry)
            self.assertGreaterEqual(entry["delivery_latency_ms"], 0.0)
            self.assertLess(entry["delivery_latency_ms"], 1000.0)  # Localhost is sub-second


class TestTrafficFlooder(unittest.TestCase):
    """
    Test controlled UDP congestion generation script.
    """

    def test_flood_rate_and_packet_transmission(self):
        """Verify flooder transmits UDP packets at specified bandwidth."""
        target_port = 19999
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(("127.0.0.1", target_port))
        recv_sock.settimeout(0.5)

        pkts_received = []

        def receiver():
            while True:
                try:
                    data, _ = recv_sock.recvfrom(2048)
                    pkts_received.append(len(data))
                except socket.timeout:
                    break
                except OSError:
                    break

        t = threading.Thread(target=receiver, daemon=True)
        t.start()

        # Run flooder at 1.0 Mbps for 1 second
        run_flood(
            target_ip="127.0.0.1",
            target_port=target_port,
            rate_mbps=1.0,
            duration=1,
            packet_size=1000,
            report_interval=0.5,
        )

        time.sleep(0.6)
        recv_sock.close()
        t.join(timeout=1.0)

        # At 1.0 Mbps with 1000-byte packets, ~125 packets are expected in 1 second
        self.assertGreater(len(pkts_received), 10)
        self.assertEqual(pkts_received[0], 1000)


class TestAnalysisModule(unittest.TestCase):
    """
    Test comparative evaluation and reporting module.
    """

    def test_benchmark_generation_and_reporting(self):
        """Verify report generation with comparison table and CSV export."""
        baseline, qos = generate_synthetic_benchmark()
        self.assertIn("CRITICAL", baseline["severity_metrics"])
        self.assertIn("CRITICAL", qos["severity_metrics"])

        # CRITICAL loss in QoS must be lower than baseline
        self.assertLess(
            qos["severity_metrics"]["CRITICAL"]["loss_rate"],
            baseline["severity_metrics"]["CRITICAL"]["loss_rate"],
        )

        report_file = os.path.join(SCRIPT_DIR, "test_comparison_report.txt")
        try:
            print_comparison_table(baseline, qos, output_report_file=report_file)
            self.assertTrue(os.path.isfile(report_file))

            with open(report_file, "r") as f:
                content = f.read()
            self.assertIn("CHRONOS DISTRIBUTED LOGGING", content)
            self.assertIn("CRITICAL", content)
            self.assertIn("Protected", content)

            csv_file = os.path.join(SCRIPT_DIR, "comparison_report.csv")
            self.assertTrue(os.path.isfile(csv_file))
        finally:
            if os.path.isfile(report_file):
                os.remove(report_file)
            if os.path.isfile(os.path.join(SCRIPT_DIR, "comparison_report.csv")):
                os.remove(os.path.join(SCRIPT_DIR, "comparison_report.csv"))


if __name__ == "__main__":
    print("==================================================================")
    print(" Running Chronos Log Automated Verification Test Suite")
    print("==================================================================")
    unittest.main(verbosity=2)
