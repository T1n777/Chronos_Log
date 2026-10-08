#!/usr/bin/env python3
"""
topology.py - Mininet Network Topology for Distributed Log Aggregation

Constructs a multi-switch OpenFlow network with a designated 1 Mbps bottleneck
link interconnecting distributed log client hosts (h1, h2, h3), a background
congestion generator (h5), and the centralized log server (h4).
"""

import sys
import argparse
from typing import Optional

try:
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
    from mininet.link import TCLink
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
except ImportError:
    # Allow importing/viewing without mininet installed
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
    Build and initialize the Mininet topology.

    Network Diagram:
        h1 (10.0.0.1) --- s1 -----------------+
        h5 (10.0.0.5) --- s1                  |
                                              |
        h2 (10.0.0.2) --- s2 --- (1 Mbps) --- s4 --- h4 (10.0.0.4 Server)
                          |   (bottleneck)
        h3 (10.0.0.3) --- s3
    """
    if Mininet is None:
        print("[ERROR] Mininet library not found. Please install Mininet or run inside VM.", file=sys.stderr)
        sys.exit(1)

    info("*** Initializing Mininet with OpenFlow 1.3 switches\n")
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    info(f"*** Connecting to Remote SDN Controller at {controller_ip}:{controller_port}\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip=controller_ip,
        port=controller_port,
    )

    info("*** Creating OpenFlow 1.3 Switches\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")
    s3 = net.addSwitch("s3", protocols="OpenFlow13")
    s4 = net.addSwitch("s4", protocols="OpenFlow13")

    info("*** Creating Network Hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2 = net.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3 = net.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    h4 = net.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")  # Central Log Server
    h5 = net.addHost("h5", ip="10.0.0.5/24", mac="00:00:00:00:00:05")  # Congestion Generator

    info("*** Adding Host-to-Switch Access Links\n")
    net.addLink(h1, s1, bw=access_bw, delay=access_delay)
    net.addLink(h5, s1, bw=access_bw, delay=access_delay)
    net.addLink(h2, s2, bw=access_bw, delay=access_delay)
    net.addLink(h3, s3, bw=access_bw, delay=access_delay)
    net.addLink(h4, s4, bw=access_bw, delay=access_delay)

    info("*** Adding Inter-Switch Backbone Links\n")
    net.addLink(s1, s2, bw=access_bw, delay="2ms")
    net.addLink(s2, s3, bw=access_bw, delay="2ms")

    info(f"*** Establishing BOTTLENECK LINK s2 <-> s4 (Bandwidth: {bottleneck_bw} Mbps, Delay: {bottleneck_delay})\n")
    net.addLink(
        s2,
        s4,
        bw=bottleneck_bw,
        delay=bottleneck_delay,
        max_queue_size=50,  # Constrained buffer to trigger packet drops under congestion
    )

    info("*** Building Network and Starting Switches\n")
    net.build()
    c0.start()
    for sw in [s1, s2, s3, s4]:
        sw.start([c0])

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
    parser = argparse.ArgumentParser(
        description="Launch Mininet topology for Distributed Log Aggregation System."
    )
    parser.add_argument(
        "--controller-ip",
        default="127.0.0.1",
        help="IP address of the remote SDN controller (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--controller-port",
        type=int,
        default=6633,
        help="OpenFlow port of the remote SDN controller (default: 6633)",
    )
    parser.add_argument(
        "--bottleneck-bw",
        type=float,
        default=1.0,
        help="Bandwidth in Mbps for the bottleneck link s2-s4 (default: 1.0)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Perform automated ping test between all pairs and exit",
    )
    args = parser.parse_args()

    if setLogLevel:
        setLogLevel("info")

    net = build_chronos_network(
        controller_ip=args.controller_ip,
        controller_port=args.controller_port,
        bottleneck_bw=args.bottleneck_bw,
    )

    try:
        if args.test:
            info("*** Running All-Pairs Ping Test...\n")
            loss = net.pingAll()
            info(f"*** PingAll Finished with {loss}% packet drop.\n")
        else:
            CLI(net)
    finally:
        info("*** Stopping Mininet network\n")
        net.stop()


if __name__ == "__main__":
    main()
