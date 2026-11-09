#!/usr/bin/env bash
# ==============================================================================
# Chronos Open vSwitch (OVS) QoS & Queue Provisioning Script
# Configures Linux Hierarchical Token Bucket (HTB) rate-limiting queues
# on the bottleneck switch port (s2-eth3) to enforce strict bandwidth isolation:
#   - Queue 0 (Best-Effort): 100k - 200k bps (DEBUG, INFO, WARNING)
#   - Queue 1 (VIP Priority): 800k - 1000k bps (CRITICAL, ERROR)
# ==============================================================================

# Exit immediately if any command returns a non-zero exit code
set -e

# Default bottleneck interface: switch s2 port 3 connecting towards switch s4
PORT_NAME="s2-eth3"
ACTION="apply"

# Display usage instructions
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

# Parse command-line flags
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

# Ensure ovs-vsctl command-line utility exists on host system
check_ovs() {
    if ! command -v ovs-vsctl >/dev/null 2>&1; then
        echo "[ERROR] 'ovs-vsctl' command not found. Run this inside the Mininet host or VM." >&2
        exit 1
    fi
}

case "$ACTION" in
    # --------------------------------------------------------------------------
    # Clean Action: Destroys any existing QoS and Queue records in OVS database
    # --------------------------------------------------------------------------
    clean)
        check_ovs
        echo "[INFO] Clearing OVS QoS and Queue configurations on port $PORT_NAME..."
        # Dissociate QoS table from target port if present
        sudo ovs-vsctl --if-exists clear port "$PORT_NAME" qos || true
        # Destroy all orphaned qos and queue records from database
        sudo ovs-vsctl -- --all destroy qos -- --all destroy queue || true
        echo "[SUCCESS] QoS and queues removed."
        exit 0
        ;;

    # --------------------------------------------------------------------------
    # Status Action: Inspects active QoS mappings and queue limits in OVS
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # Apply Action: Programs Linux HTB dual-queue scheduler on the port
    # --------------------------------------------------------------------------
    apply)
        check_ovs
        echo "=================================================="
        echo " Configuring OVS QoS on Bottleneck Port: $PORT_NAME"
        echo "=================================================="

        # Check if the virtual ethernet port exists in OVS database
        if ! sudo ovs-vsctl list port "$PORT_NAME" >/dev/null 2>&1; then
            echo "[WARNING] Port '$PORT_NAME' not currently detected in OVS."
            echo "          Make sure Mininet topology is currently active!"
            echo "          Attempting configuration anyway..."
        fi

        # Clear existing QoS records on this port before re-creating
        sudo ovs-vsctl --if-exists clear port "$PORT_NAME" qos || true

        # Atomically configure HTB QoS and dual queues using ovs-vsctl transaction:
        # 1. Create QoS record of type linux-htb with 1.0 Mbps link ceiling
        # 2. Attach Queue 0: min 100 Kbps, capped at max 200 Kbps (Best Effort)
        # 3. Attach Queue 1: min 800 Kbps, up to 1.0 Mbps max (Protected Priority)
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
