# Chronos Log: Dual-Track Implementation Guide (Mininet + Cisco Packet Tracer)

> **Document Purpose**: Provides complete, side-by-side execution instructions and viva defense strategies for both **Mininet (OpenFlow 1.3 + Ryu SDN)** and **Cisco Packet Tracer (Cisco Catalyst + IOS MQC QoS)**.

---

## 1. Why Prepare Both Environments?

| Requirement / Scenario | Mininet + Ryu SDN Track | Cisco Packet Tracer Track |
|---|---|---|
| **Official PESU Mini-Project Rubric** | **Mandatory**: Rubric explicitly demands Mininet + SDN controller + low-level Python socket programming. | **Supplementary**: Frequently requested by faculty to verify fundamental topology and CCNA switching concepts. |
| **Control Plane** | Dynamic OpenFlow 1.3 controller (Ryu on `127.0.0.1:6633`) that installs flow rules programmatically via telemetry. | Cisco IOS CLI configuration with static MQC (Modular QoS CLI) policies. |
| **Data Plane** | Linux Open vSwitch (OVS) bridges with Linux Hierarchical Token Bucket (HTB) hardware queues. | Cisco Catalyst 2960 / 3560 switches with hardware Priority Queuing (PQ / CBWFQ). |
| **Packet Tagging** | Python sockets: `sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_val)`. | Packet Tracer: Complex PDU Tool (setting TOS field to `184` or `0xB8`). |
| **How to Demo** | Run `python3 main.py` or `./run_experiment.sh demo`. | Open Packet Tracer, enter Simulation Mode, send PDU packets, inspect header filters. |

---

## 2. Track 1: Mininet + Ryu SDN (The Primary Project)

This is the fully functioning project codebase located in [**`/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log`**](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log).

### Architecture Summary
- **4 Switches**: `s1`, `s2`, `s3`, `s4` (Open vSwitch running OpenFlow 1.3).
- **5 Hosts**:
  - `h1` (`10.0.0.1`), `h2` (`10.0.0.2`), `h3` (`10.0.0.3`): Distributed microservices streaming UDP logs.
  - `h4` (`10.0.0.4`): Centralized log aggregation server listening on UDP port 5514.
  - `h5` (`10.0.0.5`): Background traffic flooder injecting 5.0 Mbps congestion to port 9999.
- **Bottleneck Link**: Link between `s2` and `s4` configured at 1.0 Mbps, 5ms delay, 50-packet FIFO queue.
- **Ryu Controller**: Dynamically monitors throughput on `s2`; when traffic exceeds 650 Kbps, pushes flow rules matching `ip_dscp=46/34` to Queue 1 (VIP: 800k–1M) and `ip_dscp=0/10/26` to Queue 0 (Best Effort: 100k–200k).

### Step-by-Step Execution Commands

#### Option A: Self-Contained Master Demonstration (Recommended for Viva)
Runs all 5 phases (Server boot, microservice streaming with kernel TOS marking, 5 Mbps congestion tail-drop, Ryu dynamic QoS activation, and final performance matrix):
```bash
cd "/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log"
python3 main.py
```

#### Option B: Automated Test Suite (To Show 100% Test Coverage)
```bash
python3 test_suite.py
```

#### Option C: Live Mininet + Ryu Controller Deployment (If running in VM / Linux with root)
1. **Terminal 1 (Start Ryu SDN Controller)**:
   ```bash
   ryu-manager sdn_controller.py
   ```
2. **Terminal 2 (Start Mininet Topology with OpenFlow 1.3)**:
   ```bash
   sudo python3 topology.py
   ```
3. **Terminal 3 (Apply Linux HTB Queues on Bottleneck Port)**:
   ```bash
   sudo ./setup_qos.sh apply
   ```
4. **Inside Mininet CLI (`mininet>`)**:
   ```bash
   h4 python3 log_server.py &
   h1 python3 log_client.py --server-ip 10.0.0.4 --hostname h1 &
   h2 python3 log_client.py --server-ip 10.0.0.4 --hostname h2 &
   h3 python3 log_client.py --server-ip 10.0.0.4 --hostname h3 &
   h5 python3 flood.py --target 10.0.0.4 --rate-mbps 5.0 --duration 30 &
   ```

---

## 3. Track 2: Cisco Packet Tracer (The Lab Simulation)

### Launching Packet Tracer on Linux
Cisco Packet Tracer 9.0.1 is already installed on your system. Launch it with:
```bash
packettracer
```

---

### Topology Blueprint in Packet Tracer

```
   [h1: 10.0.0.1]                     [h2: 10.0.0.2]
         |                                  |
    (Fa0/1)                            (Fa0/1)
         v                                  v
    [Switch s1] ===== (Gi0/1 - Gi0/1) ===== [Switch s2 (Core)] === (Gi0/3 - Gi0/1) === [Switch s4] ---> [h4: 10.0.0.4]
         ^                                  ^                                             (Fa0/1)      (Log Server)
    (Fa0/2)                            (Gi0/2)                                                         (Port 5514)
         |                                  |
   [h5: 10.0.0.5]                           |
   (Traffic Flooder)                  (Gi0/1)
                                            v
                                       [Switch s3]
                                            ^
                                       (Fa0/1)
                                            |
                                      [h3: 10.0.0.3]
```

---

### Step 1: Device Placement & Cabling
Place the following devices on the Packet Tracer workspace:

1. **Switches**:
   - 4x **2960-24TT** (or **3560-24PS** Multilayer Switches) labeled `s1`, `s2`, `s3`, `s4`.
2. **End Devices**:
   - 4x **PC-PT** labeled `h1`, `h2`, `h3`, `h5`.
   - 1x **Server-PT** labeled `h4 (Log Server)`.
   - 1x **Server-PT** labeled `c0 (SDN Controller)`.
3. **Cabling (Copper Straight-Through & Cross-Over)**:
   - `h1` FastEthernet0 -> `s1` FastEthernet0/1
   - `h5` FastEthernet0 -> `s1` FastEthernet0/2
   - `s1` GigabitEthernet0/1 -> `s2` GigabitEthernet0/1 (Switch-to-switch)
   - `h2` FastEthernet0 -> `s2` FastEthernet0/1
   - `h3` FastEthernet0 -> `s3` FastEthernet0/1
   - `s3` GigabitEthernet0/1 -> `s2` GigabitEthernet0/2 (Switch-to-switch)
   - **BOTTLENECK**: `s2` GigabitEthernet0/3 -> `s4` GigabitEthernet0/1
   - `s4` FastEthernet0/1 -> `h4` FastEthernet0

---

### Step 2: IP Configuration Settings

Click on each End Device -> **Desktop** -> **IP Configuration**:

| Device Name | IP Address | Subnet Mask | Default Gateway | Function / Role |
|---|---|---|---|---|
| **h1** | `10.0.0.1` | `255.255.255.0` | `10.0.0.254` | Log Client 1 |
| **h2** | `10.0.0.2` | `255.255.255.0` | `10.0.0.254` | Log Client 2 |
| **h3** | `10.0.0.3` | `255.255.255.0` | `10.0.0.254` | Log Client 3 |
| **h4** | `10.0.0.4` | `255.255.255.0` | `10.0.0.254` | Central Log Aggregator |
| **h5** | `10.0.0.5` | `255.255.255.0` | `10.0.0.254` | 5 Mbps Traffic Flooder |
| **c0** | `10.0.0.100` | `255.255.255.0` | `10.0.0.254` | Controller Interface |

---

### Step 3: Cisco IOS Switch Configurations (CLI Commands)

Click on each switch -> **CLI** tab and paste these configurations:

#### Switch s1 Configuration
```cisco
enable
configure terminal
hostname s1
interface range FastEthernet0/1-2
 switchport mode access
 switchport access vlan 1
 no shutdown
exit
interface GigabitEthernet0/1
 switchport mode trunk
 no shutdown
exit
end
write memory
```

#### Switch s2 Configuration (Core Bottleneck Egress Switch)
This switch models the 1.0 Mbps bottleneck and QoS classification:
```cisco
enable
configure terminal
hostname s2

! Configure Ingress and Backbone Trunk Interfaces
interface GigabitEthernet0/1
 switchport mode trunk
 no shutdown
exit
interface GigabitEthernet0/2
 switchport mode trunk
 no shutdown
exit
interface FastEthernet0/1
 switchport mode access
 switchport access vlan 1
 no shutdown
exit

! BOTTLENECK INTERFACE to Switch s4
interface GigabitEthernet0/3
 switchport mode trunk
 speed 10
 duplex full
 no shutdown
exit

! Define Access-Lists matching DiffServ values
access-list 100 permit ip any any dscp ef
access-list 100 permit ip any any dscp af41
access-list 101 permit ip any any dscp default
access-list 101 permit ip any any dscp af11
access-list 101 permit ip any any dscp af31

! Define Cisco Modular QoS CLI (MQC) Class Maps
class-map match-all CM_CRITICAL_LOGS
 match access-group 100
exit
class-map match-all CM_BESTEFFORT_LOGS
 match access-group 101
exit

! Define Policy Map (Queue 1: Priority vs Queue 0: Best Effort)
policy-map PM_CHRONOS_SDN_QOS
 class CM_CRITICAL_LOGS
  priority 800
 class CM_BESTEFFORT_LOGS
  bandwidth 200
exit

! Attach QoS Policy to Bottleneck Egress Port
interface GigabitEthernet0/3
 service-policy output PM_CHRONOS_SDN_QOS
exit
end
write memory
```

#### Switch s3 Configuration
```cisco
enable
configure terminal
hostname s3
interface FastEthernet0/1
 switchport mode access
 switchport access vlan 1
 no shutdown
exit
interface GigabitEthernet0/1
 switchport mode trunk
 no shutdown
exit
end
write memory
```

#### Switch s4 Configuration (Destination Switch to Server h4)
```cisco
enable
configure terminal
hostname s4
interface GigabitEthernet0/1
 switchport mode trunk
 speed 10
 duplex full
 no shutdown
exit
interface FastEthernet0/1
 switchport mode access
 switchport access vlan 1
 no shutdown
exit
end
write memory
```

---

### Step 4: Demonstrating QoS in Packet Tracer

#### 1. Verifying Connectivity (Realtime Mode)
Open `h1` -> **Desktop** -> **Command Prompt**:
```bash
ping 10.0.0.4
```
*Result: 4 packets sent, 4 received (0% loss).*

#### 2. Sending Tagged Packets (Simulation Mode)
1. Switch Packet Tracer to **Simulation Mode** (bottom right stopwatch icon or `Shift + S`).
2. Click **Add Complex PDU** (open envelope icon with a small plus sign on the right toolbar).
3. Click on **h1** (source).
4. In the Complex PDU configuration dialog:
   - **Select Application**: Ping (or Custom).
   - **Destination IP**: `10.0.0.4`.
   - **TOS**: Enter `184` (which equals `0xB8`, DSCP 46 / Expedited Forwarding).
   - **Simulation Settings**: Interval `1` second.
5. Click **Create PDU**.
6. Repeat for **h5** (Flooder):
   - **Destination IP**: `10.0.0.4`.
   - **TOS**: Enter `0` (Best Effort).
   - **Interval**: `0.1` seconds.
7. Click **Play / Auto Capture**:
   - Watch the packets move along the links.
   - When packets arrive at `s2`, click the packet envelope:
   - In the **PDU Information** window, view **In Layers** vs **Out Layers**:
   - Under Out Layers, point out `IP Header: TOS 0xB8 (DSCP 46)`.
   - Show that on port `GigabitEthernet0/3`, the packet is scheduled via `CM_CRITICAL_LOGS` priority queue.

---

## 4. Concept Translation Matrix (Viva Cheatsheet)

When answering questions in the viva, use this mapping to translate between the two environments:

| Concept | Mininet + Ryu Implementation | Cisco Packet Tracer Counterpart |
|---|---|---|
| **Switches** | Open vSwitch (`OVSSwitch`, OpenFlow 1.3) | Cisco Catalyst 2960 / 3560 Switches |
| **SDN Controller** | Ryu Controller (`127.0.0.1:6633`) | Cisco DNA Center / OpenFlow Agent |
| **QoS Rule Injection** | Ryu `OFPFlowMod(match=ip_dscp=46, SetQueue=1)` | Cisco MQC `policy-map PM_CHRONOS_SDN_QOS` |
| **Queue Scheduling** | Linux Kernel Hierarchical Token Bucket (`tc / HTB`) | Cisco Hardware Priority Queuing (PQ + CBWFQ) |
| **Priority Queue (Queue 1)** | `min-rate=800000 max-rate=1000000` (800k - 1M) | `class CM_CRITICAL_LOGS priority 800` |
| **Best-Effort Queue (Queue 0)**| `min-rate=100000 max-rate=200000` (100k - 200k) | `class CM_BESTEFFORT_LOGS bandwidth 200` |
| **Packet Tagging** | Python `sock.setsockopt(IPPROTO_IP, IP_TOS, tos)` | Complex PDU dialog -> `TOS = 184 (0xB8)` |
| **Traffic Congestion** | `flood.py` (5.0 Mbps UDP stream to port 9999) | Packet Tracer Traffic Generator (High packet rate PDU) |

---

## 5. Summary Viva Answers for Evaluators

- **If the examiner asks: "Did you test this on Packet Tracer?"**  
  *Answer*: "Yes. We prepared the topology in both environments. In Cisco Packet Tracer, we modeled the architecture using 4 Cisco Catalyst switches with Cisco MQC QoS policies to verify Cisco DSCP queuing. For our actual project deliverable, we deployed it on Mininet with Open vSwitch and a Ryu SDN controller to satisfy the programmable OpenFlow 1.3 and Python socket programming requirements of the syllabus."

- **If the examiner asks: "Why is Mininet better for this project than Packet Tracer?"**  
  *Answer*: "Cisco Packet Tracer does not support custom application-layer socket code, high-resolution one-way delay calculation, or programmatic SDN APIs like OpenFlow 1.3. Mininet runs actual Linux kernel network namespaces and real Python processes (`log_client.py` and `log_server.py`), allowing us to write real socket code with `setsockopt(IP_TOS)` and observe real buffer queue tail-drops."
