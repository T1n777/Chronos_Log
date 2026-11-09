#!/usr/bin/env python3
"""
Chronos Mininet Network Topology Configuration
Constructs an OpenFlow 1.3 software-defined network with 4 Open vSwitch instances,
5 network hosts, 10 Mbps edge links, and a strict 1.0 Mbps bottleneck link (s2-s4)
with a 50-packet FIFO queue buffer to emulate real-world wide-area congestion.
"""

import sys
import argparse
from typing import Optional

# Attempt importing Mininet modules; fallback safely if running outside virtual environment
try:
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
    from mininet.link import TCLink
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
except ImportError:
    # Graceful degradation for standalone inspection outside Mininet VM
    Mininet = None
    OVSSwitch = None
    RemoteController = None
    TCLink = None
    CLI = None
    setLogLevel = None
    info = print


def build_chronos_network(
    controller_ip: str = "127.0.0.1",
    controller_port: int = 6633,
    bottleneck_bw: float = 1.0,
    bottleneck_delay: str = "5ms",
    access_bw: float = 10.0,
    access_delay: str = "1ms",
):
    """
    Constructs and boots the Chronos Mininet topology:
      - c0: Remote Ryu SDN controller on 127.0.0.1:6633.
      - s1, s2, s3, s4: Open vSwitch bridges configured for OpenFlow 1.3.
      - h1, h2, h3: Distributed microservice log clients (10.0.0.1, 10.0.0.2, 10.0.0.3).
      - h4: Centralized log aggregation server (10.0.0.4).
      - h5: Background traffic flooder (10.0.0.5).
      - Bottleneck Link: s2 <-> s4 (Bandwidth: 1.0 Mbps, Delay: 5ms, Queue: 50 packets).
    """
    # Verify Mininet package availability
    if Mininet is None:
        print("[ERROR] Mininet library not found. Please install Mininet or run inside VM.", file=sys.stderr)
        sys.exit(1)

    info("*** Initializing Mininet with OpenFlow 1.3 switches\n")
    # Instantiate Mininet object with TCLink for rate limiting and traffic control
    net = Mininet(
        controller=RemoteController,  # Use external controller process (Ryu)
        switch=OVSSwitch,             # Open vSwitch layer-2/3 bridges
        link=TCLink,                  # Traffic Control links enabling bandwidth and delay emulation
        autoSetMacs=True,             # Automatically assign readable MAC addresses (00:00:00:00:00:0X)
        autoStaticArp=True,           # Pre-populate static ARP tables to eliminate ARP flood overhead
    )

    info(f"*** Connecting to Remote SDN Controller at {controller_ip}:{controller_port}\n")
    # Add external Ryu OpenFlow 1.3 controller handle
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip=controller_ip,
        port=controller_port,
    )

    info("*** Creating OpenFlow 1.3 Switches\n")
    # Instantiate four Open vSwitch datapath instances running OpenFlow 1.3 protocol
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")  # Primary aggregation switch before bottleneck
    s3 = net.addSwitch("s3", protocols="OpenFlow13")
    s4 = net.addSwitch("s4", protocols="OpenFlow13")  # Destination switch connecting to central server h4

    info("*** Creating Network Hosts\n")
    # Allocate hosts with designated static IP and MAC addresses in the 10.0.0.0/24 subnet
    h1 = net.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")  # Log Client 1
    h2 = net.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")  # Log Client 2
    h3 = net.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")  # Log Client 3
    h4 = net.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")  # Centralized Log Server
    h5 = net.addHost("h5", ip="10.0.0.5/24", mac="00:00:00:00:00:05")  # Background Traffic Flooder

    info("*** Adding Host-to-Switch Access Links\n")
    # Connect edge hosts to switches via 10 Mbps access links (low delay)
    net.addLink(h1, s1, bw=access_bw, delay=access_delay)
    net.addLink(h5, s1, bw=access_bw, delay=access_delay)  # Flooder attached to switch s1
    net.addLink(h2, s2, bw=access_bw, delay=access_delay)
    net.addLink(h3, s3, bw=access_bw, delay=access_delay)
    net.addLink(h4, s4, bw=access_bw, delay=access_delay)  # Server attached to switch s4

    info("*** Adding Inter-Switch Backbone Links\n")
    # Inter-switch transit backbone links
    net.addLink(s1, s2, bw=access_bw, delay="2ms")
    net.addLink(s2, s3, bw=access_bw, delay="2ms")

    # CRITICAL: Bottleneck Link between s2 and s4
    # All client traffic and flood traffic converging towards server h4 must traverse this link
    info(f"*** Establishing BOTTLENECK LINK s2 <-> s4 (Bandwidth: {bottleneck_bw} Mbps, Delay: {bottleneck_delay})\n")
    net.addLink(
        s2,
        s4,
        bw=bottleneck_bw,       # Capped to 1.0 Mbps bandwidth ceiling
        delay=bottleneck_delay, # 5ms propagation latency
        max_queue_size=50,      # Strict 50-packet queue limit: causes buffer tail-drop when saturated
    )

    info("*** Building Network and Starting Switches\n")
    # Build internal graph structure and initialize devices
    net.build()
    # Connect controller
    c0.start()
    # Start switches with reference to remote controller
    for sw in [s1, s2, s3, s4]:
        sw.start([c0])

    # Print summary of active topology
    info("\n" + "=" * 65 + "\n")
    info(" Chronos Network Topology Active\n")
    info("=" * 65 + "\n")
    info(" Log Clients      : h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3)\n")
    info(" Log Server       : h4 (10.0.0.4)\n")
    info(" Congestion Host  : h5 (10.0.0.5)\n")
    info(f" Bottleneck Link  : Switch s2 <-> Switch s4 ({bottleneck_bw} Mbps)\n")
    info(" SDN Controller   : Remote (127.0.0.1:6633)\n")
    info("=" * 65 + "\n\n")

    return net


def main():
    """
    Parses CLI parameters and launches Mininet CLI or automated ping test.
    """
    parser = argparse.ArgumentParser(
        description="Launch Mininet topology for Distributed Log Aggregation System."
    )
    # Controller IP
    parser.add_argument(
        "--controller-ip",
        default="127.0.0.1",
        help="IP address of the remote SDN controller (default: 127.0.0.1)",
    )
    # Controller OpenFlow port
    parser.add_argument(
        "--controller-port",
        type=int,
        default=6633,
        help="OpenFlow port of the remote SDN controller (default: 6633)",
    )
    # Bottleneck link bandwidth
    parser.add_argument(
        "--bottleneck-bw",
        type=float,
        default=1.0,
        help="Bandwidth in Mbps for the bottleneck link s2-s4 (default: 1.0)",
    )
    # Flag to run automated ping test instead of interactive CLI
    parser.add_argument(
        "--test",
        action="store_true",
        help="Perform automated ping test between all pairs and exit",
    )
    args = parser.parse_args()

    # Enable Mininet informative logging
    if setLogLevel:
        setLogLevel("info")

    # Construct network
    net = build_chronos_network(
        controller_ip=args.controller_ip,
        controller_port=args.controller_port,
        bottleneck_bw=args.bottleneck_bw,
    )

    try:
        if args.test:
            # Perform all-pairs reachability ping verification
            info("*** Running All-Pairs Ping Test...\n")
            loss = net.pingAll()
            info(f"*** PingAll Finished with {loss}% packet drop.\n")
        else:
            # Drop into interactive Mininet command-line interface
            CLI(net)
    finally:
        # Tear down network, interfaces, and namespaces on exit
        info("*** Stopping Mininet network\n")
        net.stop()


if __name__ == "__main__":
    main()
