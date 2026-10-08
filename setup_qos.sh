#!/usr/bin/env bash
#
# setup_qos.sh - Open vSwitch QoS Queue Configuration for Chronos
#
# Configures Hierarchical Token Bucket (HTB) rate shaping and dual-queue
# prioritization on the Mininet bottleneck switch port (s2-eth3).
#
# Queue Architecture on 1 Mbps Link:
#   Queue 0 (Best Effort)   : Min 100 Kbps, Max 200 Kbps (DEBUG, INFO, WARNING, flood)
#   Queue 1 (High Priority) : Min 800 Kbps, Max 1 Mbps   (CRITICAL, ERROR logs)
#

set -e

PORT_NAME="s2-eth3"
ACTION="apply"

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  -p, --port <name>   Target OVS switch port (default: s2-eth3)
  -c, --clean         Remove all QoS and Queue records from OVS
  -s, --status        Display current OVS QoS and Queue configurations
  -h, --help          Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            PORT_NAME="$2"
            shift 2
            ;;
        -c|--clean)
            ACTION="clean"
            shift
            ;;
        -s|--status)
            ACTION="status"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            show_help
            exit 1
            ;;
    esac
done

check_ovs() {
    if ! command -v ovs-vsctl >/dev/null 2>&1; then
        echo "[ERROR] 'ovs-vsctl' command not found. Run this inside the Mininet host or VM." >&2
        exit 1
    fi
}

case "$ACTION" in
    clean)
        check_ovs
        echo "[INFO] Clearing OVS QoS and Queue configurations on port $PORT_NAME..."
        sudo ovs-vsctl --if-exists clear port "$PORT_NAME" qos || true
        sudo ovs-vsctl -- --all destroy qos -- --all destroy queue || true
        echo "[SUCCESS] QoS and queues removed."
        exit 0
        ;;

    status)
        check_ovs
        echo "=================================================="
        echo " OVS QoS & Queue Status"
        echo "=================================================="
        echo "--- Port QoS Mapping ---"
        sudo ovs-vsctl list port "$PORT_NAME" | grep -E "name|qos" || true
        echo ""
        echo "--- QoS Records ---"
        sudo ovs-vsctl list qos || true
        echo ""
        echo "--- Queue Records ---"
        sudo ovs-vsctl list queue || true
        echo "=================================================="
        exit 0
        ;;

    apply)
        check_ovs
        echo "=================================================="
        echo " Configuring OVS QoS on Bottleneck Port: $PORT_NAME"
        echo "=================================================="

        # Ensure port exists
        if ! sudo ovs-vsctl list port "$PORT_NAME" >/dev/null 2>&1; then
            echo "[WARNING] Port '$PORT_NAME' not currently detected in OVS."
            echo "          Make sure Mininet topology is currently active!"
            echo "          Attempting configuration anyway..."
        fi

        # Clear existing QoS on target port
        sudo ovs-vsctl --if-exists clear port "$PORT_NAME" qos || true

        # Create Linux-HTB QoS with 2 priority queues
        # Total Bandwidth: 1,000,000 bps (1 Mbps)
        # Queue 0 (Best Effort)   : Max 200 Kbps (Rate capped under congestion)
        # Queue 1 (High Priority) : Guaranteed min 800 Kbps, max 1,000,000 bps
        sudo ovs-vsctl set port "$PORT_NAME" qos=@newqos -- \
            --id=@newqos create qos type=linux-htb \
                other-config:max-rate=1000000 \
                queues:0=@q0 queues:1=@q1 -- \
            --id=@q0 create queue \
                other-config:min-rate=100000 \
                other-config:max-rate=200000 -- \
            --id=@q1 create queue \
                other-config:min-rate=800000 \
                other-config:max-rate=1000000

        echo "[SUCCESS] QoS Queues Configured on $PORT_NAME:"
        echo "  - Max Link Bandwidth : 1.0 Mbps"
        echo "  - Queue 0 (Best Effort)   : 100 Kbps min / 200 Kbps max"
        echo "  - Queue 1 (High Priority) : 800 Kbps min / 1.0 Mbps max (Protected)"
        echo "=================================================="
        ;;
esac
