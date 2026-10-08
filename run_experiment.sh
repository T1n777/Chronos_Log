#!/usr/bin/env bash
#
# run_experiment.sh - Chronos Distributed Log Aggregation Experiment Runner
#
# Automates execution of tests across standalone and Mininet environments.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    cat << EOF
Chronos Experiment Orchestrator

Usage:
  ./run_experiment.sh demo         Run interactive terminal showcase for evaluation & viva
  ./run_experiment.sh standalone   Run local end-to-end socket verification test
  ./run_experiment.sh analyze      Analyze existing experiment output or run benchmark
  ./run_experiment.sh clean        Clean up background processes, sockets, and results
  ./run_experiment.sh help         Display this guide

For Mininet + Ryu full SDN deployment:
  Follow the sequential step-by-step instructions documented in README.md.
EOF
}

cleanup() {
    # Terminate any lingering background python processes started by this script
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[CLEANUP] Stopping log server (PID $SERVER_PID)..."
        kill -INT "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

case "${1:-help}" in
    demo)
        python3 demo.py "${@:2}"
        ;;

    standalone)
        echo "=========================================================="
        echo " Chronos Standalone End-to-End Verification Test"
        echo "=========================================================="
        echo "Verifying low-level UDP sockets, IP TOS marking, concurrency,"
        echo "log categorization, and latency calculation on localhost."
        echo "=========================================================="

        RESULTS_DIR="results/standalone"
        mkdir -p "$RESULTS_DIR"

        echo "[1/4] Starting Centralized Log Server on 127.0.0.1:5514..."
        python3 log_server.py \
            --bind-ip 127.0.0.1 \
            --port 5514 \
            --stats-interval 2 \
            --output-dir "$RESULTS_DIR" \
            --quiet &
        SERVER_PID=$!
        sleep 1

        echo "[2/4] Starting 3 Parallel Log Clients (h1, h2, h3)..."
        python3 log_client.py --server-ip 127.0.0.1 --server-port 5514 --hostname h1 --rate 0.05 --count 100 --quiet &
        PID1=$!
        python3 log_client.py --server-ip 127.0.0.1 --server-port 5514 --hostname h2 --rate 0.05 --count 100 --quiet &
        PID2=$!
        python3 log_client.py --server-ip 127.0.0.1 --server-port 5514 --hostname h3 --rate 0.05 --count 100 --quiet &
        PID3=$!

        echo "[3/4] Waiting for log transmissions to complete..."
        wait "$PID1" "$PID2" "$PID3"

        echo "[4/4] Stopping Log Server to trigger report generation..."
        kill -INT "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        unset SERVER_PID

        echo ""
        echo "[SUCCESS] Standalone test completed! Output logs in $RESULTS_DIR:"
        ls -lh "$RESULTS_DIR"
        ;;

    analyze)
        echo "=========================================================="
        echo " Running Performance & QoS Comparative Evaluation"
        echo "=========================================================="
        python3 analyze_results.py
        ;;

    clean)
        echo "[INFO] Cleaning up test results and lingering processes..."
        pkill -f "log_server.py" || true
        pkill -f "log_client.py" || true
        pkill -f "flood.py" || true
        echo "[SUCCESS] Environment cleaned."
        ;;

    help|*)
        show_help
        ;;
esac
