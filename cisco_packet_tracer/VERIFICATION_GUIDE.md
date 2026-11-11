# Cisco Packet Tracer Verification & Viva Walkthrough Guide

## Distributed Log Aggregation System with SDN Prioritization (Chronos)

---

### 1. Executive Summary

This guide provides step-by-step instructions for launching, verifying, and demonstrating the **Cisco Packet Tracer** implementation of the Chronos Distributed Log Aggregation System.

Both topology editions are pre-built, pre-wired, and pre-configured:
1. **`chronos_topology.pkt`**: Standard edition utilizing Cisco Catalyst 2960-24TT access and core switches.
2. **`chronos_topology_3560_core.pkt`**: Enterprise edition utilizing a Cisco Catalyst 3560-24PS Multilayer Switch as the Core Switch (`s2`).

All IP addresses, subnet masks, default gateways, switch hostnames, port speeds, trunk encapsulations, and Cisco Modular QoS CLI (MQC) policies are already saved into NVRAM (`startup-config`) and active in RAM (`running-config`). No manual typing in the switch CLI is required to run the demo.

---

### 2. How to Launch on Linux

Open a terminal and execute either of the following commands:

#### Option A: Launch Standard Edition (Catalyst 2960 Core)
```bash
packettracer "/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log/cisco_packet_tracer/chronos_topology.pkt" &
```

#### Option B: Launch Multilayer Core Edition (Catalyst 3560 Core)
```bash
packettracer "/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log/cisco_packet_tracer/chronos_topology_3560_core.pkt" &
```

---

### 3. Visual Topology & Port Mapping Reference

```
  [h1: Web Client]         [c0: SDN Controller]   [h2: Database Client]
   (10.0.0.1/24)              (10.0.0.100/24)         (10.0.0.2/24)
         |                           |                      |
      (Fa0)                       (Fa0)                   (Fa0)
         |                           |                      |
      (Fa0/1)                     (Fa0/23)                (Fa0/1)
         v                           v                      v
    +---------+                 +-------------------------------+
    | Switch  |=== (Gi0/1) ====>| Switch s2 (Core Bottleneck)   |
    |   s1    |                 | Modular QoS CLI (MQC) Active  |
    +---------+                 +-------------------------------+
         ^                                   |               |
      (Fa0/2)                             (Gi0/2)         (Fa0/24) [BOTTLENECK: 10 Mbps Cap]
         |                                   ^               |
      (Fa0)                               (Gi0/1)            v
         |                                   |          +---------+
  [h5: Flooder]                         +---------+     | Switch  |---> (Fa0/1) ---> [h4: Log Server]
  (10.0.0.5/24)                         | Switch  |     |   s4    |                  (10.0.0.4/24)
                                        |   s3    |     +---------+
                                        +---------+
                                             ^
                                          (Fa0/1)
                                             |
                                          (Fa0)
                                             |
                                    [h3: Auth Client]
                                      (10.0.0.3/24)
```

#### Network Device Inventory Table

| Device Name | Device Model | IP Address | Subnet Mask | Default Gateway | Switch Port Connected | Role / Function |
|---|---|---|---|---|---|---|
| **h1** | PC-PT | `10.0.0.1` | `255.255.255.0` | `10.0.0.254` | `s1` FastEthernet0/1 | Web Microservice (Sends High-Priority Logs) |
| **h2** | PC-PT | `10.0.0.2` | `255.255.255.0` | `10.0.0.254` | `s2` FastEthernet0/1 | Database Microservice (Sends Logs) |
| **h3** | PC-PT | `10.0.0.3` | `255.255.255.0` | `10.0.0.254` | `s3` FastEthernet0/1 | Auth Microservice (Sends Critical Security Logs) |
| **h4** | Server-PT | `10.0.0.4` | `255.255.255.0` | `10.0.0.254` | `s4` FastEthernet0/1 | Centralized Log Aggregation Server (Port 5514) |
| **h5** | PC-PT | `10.0.0.5` | `255.255.255.0` | `10.0.0.254` | `s1` FastEthernet0/2 | Background Traffic Flooder (Generates Congestion) |
| **c0** | Server-PT | `10.0.0.100` | `255.255.255.0` | `10.0.0.254` | `s2` FastEthernet0/23 | SDN Controller Management Plane Interface |
| **s1** | 2960-24TT | Layer 2 Switch | N/A | N/A | Uplink: `Gi0/1` to `s2` | Ingress Access Switch for `h1` and `h5` |
| **s2** | 2960 / 3560 | Core Switch | N/A | N/A | Bottleneck: `Fa0/24` to `s4` | Core Aggregation Switch with MQC Policy |
| **s3** | 2960-24TT | Layer 2 Switch | N/A | N/A | Uplink: `Gi0/1` to `s2` | Ingress Access Switch for `h3` |
| **s4** | 2960-24TT | Egress Switch | N/A | N/A | Egress: `Fa0/1` to `h4` | Destination Aggregator Switch |

---

### 4. Step-by-Step Verification Procedure

#### Step 4.1: Realtime Mode End-to-End Connectivity Check
1. Ensure Packet Tracer is in **Realtime Mode** (clock icon selected in bottom left corner).
2. Click on host **`h1`** -> Click the **Desktop** tab -> Click **Command Prompt**.
3. Ping the Central Log Server:
   ```cmd
   ping 10.0.0.4
   ```
4. Verify standard ICMP reply:
   ```
   Pinging 10.0.0.4 with 32 bytes of data:
   Reply from 10.0.0.4: bytes=32 time<1ms TTL=128
   Reply from 10.0.0.4: bytes=32 time<1ms TTL=128
   Reply from 10.0.0.4: bytes=32 time<1ms TTL=128
   Reply from 10.0.0.4: bytes=32 time<1ms TTL=128
   Ping statistics: Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
   ```
5. Test connectivity from `h2`, `h3`, and `h5` to `10.0.0.4` to confirm 100% end-to-end reachability across the core switches.

---

#### Step 4.2: Inspecting Switch QoS Configuration via Cisco IOS CLI
1. Click on Switch **`s2`** on the workspace canvas.
2. Click the **CLI** tab and press `Enter`.
3. Verify the running configuration and QoS policies:
   ```cisco
   enable
   show running-config
   ```
4. Confirm the following blocks appear in the configuration:
   - **Access-Lists**:
     ```cisco
     access-list 100 permit ip any any dscp ef
     access-list 100 permit ip any any dscp af41
     access-list 101 permit ip any any dscp default
     access-list 101 permit ip any any dscp af11
     access-list 101 permit ip any any dscp af31
     ```
   - **Class-Maps**:
     ```cisco
     class-map match-all CM_CRITICAL_LOGS
      match access-group 100
     class-map match-all CM_BESTEFFORT_LOGS
      match access-group 101
     ```
   - **Policy-Map**:
     ```cisco
     policy-map PM_CHRONOS_SDN_QOS
      class CM_CRITICAL_LOGS
       priority 800
      class CM_BESTEFFORT_LOGS
       bandwidth 200
     ```
   - **Interface Attachment**:
     ```cisco
     interface FastEthernet0/24
      speed 10
      duplex full
      service-policy output PM_CHRONOS_SDN_QOS
     ```

---

#### Step 4.3: Demonstrating DSCP Marking and Queuing in Simulation Mode
This demonstration showcases packet-level Differentiated Services (DiffServ) inspection:

1. Switch Packet Tracer to **Simulation Mode** (Click the stopwatch icon behind the Realtime button, or press `Shift + S`).
2. On the right-side palette, click **Add Complex PDU** (the open envelope icon with a small plus sign).
3. Click on host **`h1`** (Source):
   - **Application**: Ping (ICMP) or Custom.
   - **Destination IP**: `10.0.0.4`.
   - **TOS**: Enter **`184`** (Decimal `184` = Hex `0xB8` = Binary `10111000`, matching **DSCP 46 / Expedited Forwarding**).
   - **Simulation Settings**: Periodic, Interval `1` second.
   - Click **Create PDU**.
4. Click **Add Complex PDU** again and click on host **`h5`** (Background Flooder):
   - **Destination IP**: `10.0.0.4`.
   - **TOS**: Enter **`0`** (Best Effort).
   - **Simulation Settings**: Periodic, Interval `0.1` seconds.
   - Click **Create PDU**.
5. Click the **Play** button or click **Capture / Forward** step-by-step:
   - Observe both streams flowing towards Core Switch `s2`.
   - When the packets reach `s2`, click on the packet envelope icon on the canvas.
   - In the **PDU Information** dialog, select **In Layers** / **Out Layers**:
   - Under **Out Layers**, point out the **IP Header**:
     - `TOS: 0xB8 (DSCP 46: Expedited Forwarding)` on `h1`'s packet.
     - `TOS: 0x00 (DSCP 0: Best Effort)` on `h5`'s packet.
   - Explain that on port `FastEthernet0/24`, `s2` maps `TOS 0xB8` to `CM_CRITICAL_LOGS` which enters the strict priority queue (`priority 800`), bypassing best-effort flood traffic during congestion.

---

### 5. Concept Cross-Reference (Mininet vs Cisco Packet Tracer)

Use this table during evaluation to demonstrate mastery across both environments:

| System Layer | Mininet + Ryu SDN Track (Primary) | Cisco Packet Tracer Track (Supplementary) |
|---|---|---|
| **Control Plane** | OpenFlow 1.3 Ryu Python Controller (`sdn_controller.py`) dynamically injecting flow rules upon detecting link load > 650 Kbps. | Cisco IOS MQC Static Policy Engine (`class-map` + `policy-map`) pre-installed on the Core Switch. |
| **Data Plane** | Linux Open vSwitch (OVS kernel module) with Linux Hierarchical Token Bucket (`tc / HTB`) hardware queuing. | Cisco Catalyst 2960 / 3560 ASIC switching fabric with Class-Based Weighted Fair Queuing (CBWFQ + Strict PQ). |
| **Packet Tagging** | Python standard library socket options: `sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_val)`. | Complex PDU Generator setting the IPv4 Type of Service byte to `184` (`0xB8`). |
| **Priority Queue** | Queue 1: `min-rate=800000 max-rate=1000000` (800 Kbps - 1 Mbps). | `class CM_CRITICAL_LOGS` with `priority 800`. |
| **Best-Effort Queue**| Queue 0: `min-rate=100000 max-rate=200000` (100 Kbps - 200 Kbps). | `class CM_BESTEFFORT_LOGS` with `bandwidth 200`. |
| **Traffic Flooder** | Multi-threaded Python UDP flooder (`flood.py`) transmitting 5.0 Mbps dummy payloads. | High-frequency periodic PDU generation or Cisco IOS traffic generation. |
| **Bottleneck Link** | Switch `s2` port 3 to Switch `s4` port 1 configured at 1.0 Mbps, 5ms delay, 50-packet FIFO limit. | Switch `s2` `FastEthernet0/24` to Switch `s4` `FastEthernet0/24` forced to `speed 10 duplex full`. |
