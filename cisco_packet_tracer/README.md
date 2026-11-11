# Chronos Log: Cisco Packet Tracer Topology Package

This directory contains the ready-to-run Cisco Packet Tracer topology files and Cisco IOS configuration scripts for the **Chronos Distributed Log Aggregation System with SDN Prioritization**.

---

## Directory Inventory

| File | Description |
|---|---|
| [`chronos_topology.pkt`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/chronos_topology.pkt) | Standard Packet Tracer 7.x/8.x/9.x lab file with Cisco Catalyst 2960-24TT switches. Fully wired and configured. |
| [`chronos_topology_3560_core.pkt`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/chronos_topology_3560_core.pkt) | Multilayer Switch edition with a Cisco Catalyst 3560-24PS Core Switch. Fully wired and configured. |
| [`generate_pkt.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/generate_pkt.py) | Standalone Python generator script that rebuilds both `.pkt` files offline. |
| [`VERIFICATION_GUIDE.md`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/VERIFICATION_GUIDE.md) | Comprehensive step-by-step verification, simulation demonstration, and viva defense guide. |
| [`s1_access_switch.ios`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/s1_access_switch.ios) | Cisco IOS configuration script for Switch `s1` (Access switch for `h1` and `h5`). |
| [`s2_core_qos_switch.ios`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/s2_core_qos_switch.ios) | Cisco IOS configuration script for Switch `s2` (Core switch with MQC QoS policies). |
| [`s3_access_switch.ios`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/s3_access_switch.ios) | Cisco IOS configuration script for Switch `s3` (Access switch for `h3`). |
| [`s4_aggregator_switch.ios`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/s4_aggregator_switch.ios) | Cisco IOS configuration script for Switch `s4` (Destination switch for Server `h4`). |

---

## Quick Start: Launching in Cisco Packet Tracer

Launch directly from terminal:
```bash
packettracer "/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log/cisco_packet_tracer/chronos_topology.pkt" &
```

Or double-click [`chronos_topology.pkt`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/cisco_packet_tracer/chronos_topology.pkt) in your file manager.
