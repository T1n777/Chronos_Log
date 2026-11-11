#!/usr/bin/env python3
"""
Chronos Cisco Packet Tracer Lab Generator
Programmatically constructs offline .pkt files for Cisco Packet Tracer 7.x/8.x/9.x
representing the Chronos Distributed Log Aggregation System with SDN Prioritization.

Topology:
  - 4 Cisco Catalyst Switches: s1, s2, s3, s4
  - 5 End Hosts: h1, h2, h3, h4, h5 + 1 Controller interface c0
  - IP Subnet: 10.0.0.0/24
  - Bottleneck Link: s2 (Fa0/24) <-> s4 (Fa0/24) capped at 10 Mbps
  - Modular QoS CLI (MQC): DSCP-based classification and priority queueing on s2
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from pkt_core.builder.lab import Lab
except ImportError:
    print("[ERROR] pkt-core library not installed. Run 'pip install packet-tracer-pkt-format'", file=sys.stderr)
    sys.exit(1)


# Cisco IOS Configurations for Switches

S1_CONFIG = [
    "hostname s1",
    "interface FastEthernet0/1",
    " description Host h1 (Web Microservice - 10.0.0.1)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface FastEthernet0/2",
    " description Host h5 (Traffic Flooder - 10.0.0.5)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface GigabitEthernet0/1",
    " description Backbone Trunk Link to s2 (Core Switch)",
    " switchport mode trunk",
    " no shutdown",
]

S2_CONFIG = [
    "hostname s2",
    "interface FastEthernet0/1",
    " description Host h2 (Database Microservice - 10.0.0.2)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface FastEthernet0/23",
    " description SDN Controller Out-of-Band Management (c0 - 10.0.0.100)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface GigabitEthernet0/1",
    " description Backbone Trunk Link from s1 (Access Switch A)",
    " switchport mode trunk",
    " no shutdown",
    "interface GigabitEthernet0/2",
    " description Backbone Trunk Link from s3 (Access Switch B)",
    " switchport mode trunk",
    " no shutdown",
    "interface FastEthernet0/24",
    " description BOTTLENECK EGRESS LINK to s4 (Aggregator Switch) - Capped to 10 Mbps",
    " switchport mode trunk",
    " speed 10",
    " duplex full",
    " service-policy output PM_CHRONOS_SDN_QOS",
    " no shutdown",
    "access-list 100 permit ip any any dscp ef",
    "access-list 100 permit ip any any dscp af41",
    "access-list 101 permit ip any any dscp default",
    "access-list 101 permit ip any any dscp af11",
    "access-list 101 permit ip any any dscp af31",
    "class-map match-all CM_CRITICAL_LOGS",
    " match access-group 100",
    "class-map match-all CM_BESTEFFORT_LOGS",
    " match access-group 101",
    "policy-map PM_CHRONOS_SDN_QOS",
    " class CM_CRITICAL_LOGS",
    "  priority 800",
    " class CM_BESTEFFORT_LOGS",
    "  bandwidth 200",
]

S3_CONFIG = [
    "hostname s3",
    "interface FastEthernet0/1",
    " description Host h3 (Auth Microservice - 10.0.0.3)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface GigabitEthernet0/1",
    " description Backbone Trunk Link to s2 (Core Switch)",
    " switchport mode trunk",
    " no shutdown",
]

S4_CONFIG = [
    "hostname s4",
    "interface FastEthernet0/1",
    " description Destination Link to h4 (Central Log Server - 10.0.0.4)",
    " switchport mode access",
    " switchport access vlan 1",
    " spanning-tree portfast",
    " no shutdown",
    "interface FastEthernet0/24",
    " description BOTTLENECK INGRESS LINK from s2 (Core Switch)",
    " switchport mode trunk",
    " speed 10",
    " duplex full",
    " no shutdown",
]


def sync_startup_configs(lab: Lab) -> None:
    """
    Synchronizes RUNNINGCONFIG into STARTUPCONFIG on all switch nodes
    so that configurations persist upon device reload or fresh lab boot.
    """
    for dev in lab.devs:
        eng = dev.find("ENGINE")
        if eng is not None:
            rc = eng.find("RUNNINGCONFIG")
            if rc is not None:
                for sc in list(eng.findall("STARTUPCONFIG")):
                    eng.remove(sc)
                sc = ET.Element("STARTUPCONFIG")
                for line in rc.findall("LINE"):
                    l_elem = ET.SubElement(sc, "LINE")
                    l_elem.text = line.text
                eng.append(sc)


def build_topology(output_file: str, core_switch_model: str = "2960-24TT") -> None:
    """
    Builds the complete Chronos Packet Tracer topology and saves to output_file.
    """
    lab = Lab()
    lab.prune_seed_devices()

    # 1. Add Switches
    s1 = lab.add_device("2960-24TT", "s1", x=300, y=320, ios_config=S1_CONFIG)
    s2 = lab.add_device(core_switch_model, "s2", x=550, y=320, ios_config=S2_CONFIG)
    s3 = lab.add_device("2960-24TT", "s3", x=550, y=540, ios_config=S3_CONFIG)
    s4 = lab.add_device("2960-24TT", "s4", x=800, y=320, ios_config=S4_CONFIG)

    # 2. Add End Hosts
    # h1: Web Server (10.0.0.1)
    h1 = lab.add_device("PC-PT", "h1", x=130, y=200, pc_ip=["10.0.0.1", "255.255.255.0", "10.0.0.254"])
    # h5: Background Traffic Flooder (10.0.0.5)
    h5 = lab.add_device("PC-PT", "h5", x=130, y=440, pc_ip=["10.0.0.5", "255.255.255.0", "10.0.0.254"])
    # h2: Database Server (10.0.0.2)
    h2 = lab.add_device("PC-PT", "h2", x=550, y=140, pc_ip=["10.0.0.2", "255.255.255.0", "10.0.0.254"])
    # c0: Controller Node / SDN Interface (10.0.0.100)
    c0 = lab.add_device("Server-PT", "c0", x=360, y=140, pc_ip=["10.0.0.100", "255.255.255.0", "10.0.0.254"])
    # h3: Auth Server (10.0.0.3)
    h3 = lab.add_device("PC-PT", "h3", x=550, y=700, pc_ip=["10.0.0.3", "255.255.255.0", "10.0.0.254"])
    # h4: Central Log Server (10.0.0.4)
    h4 = lab.add_device("Server-PT", "h4", x=1020, y=320, pc_ip=["10.0.0.4", "255.255.255.0", "10.0.0.254"])

    # 3. Add Copper Straight-Through Cables (Hosts -> Switches)
    lab.link(h1, "FastEthernet0", s1, "FastEthernet0/1")
    lab.link(h5, "FastEthernet0", s1, "FastEthernet0/2")
    lab.link(h2, "FastEthernet0", s2, "FastEthernet0/1")
    lab.link(c0, "FastEthernet0", s2, "FastEthernet0/23")
    lab.link(h3, "FastEthernet0", s3, "FastEthernet0/1")
    lab.link(h4, "FastEthernet0", s4, "FastEthernet0/1")

    # 4. Add Inter-Switch Backbone Trunk Cables
    lab.link(s1, "GigabitEthernet0/1", s2, "GigabitEthernet0/1")
    lab.link(s3, "GigabitEthernet0/1", s2, "GigabitEthernet0/2")

    # 5. Add BOTTLENECK Trunk Cable: s2 (Fa0/24) <-> s4 (Fa0/24)
    lab.link(s2, "FastEthernet0/24", s4, "FastEthernet0/24")

    # 6. Synchronize Startup Configs
    sync_startup_configs(lab)

    # 7. Save Encrypted .pkt File
    output_path = Path(output_file).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lab.save(str(output_path))
    print(f"[OK] Generated Packet Tracer lab ({core_switch_model} core): {output_path}")


def main():
    base_dir = Path(__file__).resolve().parent

    # 1. Standard Edition (All 2960-24TT switches)
    pkt_std = base_dir / "chronos_topology.pkt"
    build_topology(str(pkt_std), core_switch_model="2960-24TT")

    # 2. Multilayer Core Switch Edition (3560-24PS Core Switch)
    pkt_3560 = base_dir / "chronos_topology_3560_core.pkt"
    build_topology(str(pkt_3560), core_switch_model="3560-24PS")

    # 3. Copy standard edition to project root
    root_dir = base_dir.parent
    root_pkt = root_dir / "chronos_topology.pkt"
    import shutil
    shutil.copy2(pkt_std, root_pkt)
    print(f"[OK] Copied {pkt_std.name} to {root_pkt}")

    # Also copy to parent Notes folder if it exists
    parent_notes_dir = root_dir.parent
    if parent_notes_dir.exists() and (parent_notes_dir / "Chronos_Log").exists():
        parent_pkt = parent_notes_dir / "chronos_topology.pkt"
        shutil.copy2(pkt_std, parent_pkt)
        print(f"[OK] Copied {pkt_std.name} to {parent_pkt}")


if __name__ == "__main__":
    main()
