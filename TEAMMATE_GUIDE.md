# Chronos Log: Complete Team Guide & Final Submission Viva Manual

> **Project Title**: Distributed Log Aggregation System with Software-Defined Networking (SDN) Prioritization  
> **Course**: Computer Networks (Semester 3) - Mini Project #10  
> **Target Audience**: Teammate A, Teammate B, and Team Lead  
> **Repository Path**: `file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log`

---

## Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Team Work Distribution & Ownership](#2-team-work-distribution--ownership)
3. [End-to-End System Architecture](#3-end-to-end-system-architecture)
4. [Teammate A Guide: Client & Congestion Generation](#4-teammate-a-guide-client--congestion-generation)
5. [Teammate B Guide: Log Server & Documentation](#5-teammate-b-guide-log-server--documentation)
6. [Team Lead Guide: Protocol, SDN, Topology & Orchestration](#6-team-lead-guide-protocol-sdn-topology--orchestration)
7. [Experimental Results & Viva Metrics](#7-experimental-results--viva-metrics)
8. [Master Viva Defense & Common Trap Questions](#8-master-viva-defense--common-trap-questions)
9. [How to Run the Demo for Evaluation](#9-how-to-run-the-demo-for-evaluation)

---

## 1. Executive Summary & Problem Statement

### The Core Problem in Modern Networks
In distributed cloud architectures, hundreds of microservices generate millions of log messages per second. These logs range from routine heartbeats (`DEBUG`, `INFO`) to urgent alarms (`ERROR`, `CRITICAL`). 

When network congestion occurs (due to traffic surges, database backups, or network attacks):
1. **Without Distributed Logging**: Log files remain siloed on local host disks. Diagnosing an outage requires SSH-ing into dozens of servers individually.
2. **Without SDN Prioritization (Traditional FIFO Buffers)**: Switches use standard First-In, First-Out (FIFO) queue tail-drop. When the switch buffer fills up, incoming packets are dropped uniformly at random. A routine `DEBUG` packet has the exact same drop probability as a fatal `CRITICAL` database failure alert. In real incidents, critical alerts are dropped in the network before the operations team ever receives them.

### The Chronos Log Solution
Chronos Log integrates socket programming with OpenFlow 1.3 Software-Defined Networking to guarantee telemetry delivery:
1. **Application Layer**: Microservices tag outgoing UDP log datagrams with Differentiated Services Code Points (DSCP per RFC 2474 / RFC 3246) directly in the IPv4 header Type of Service (TOS) octet.
2. **Network Layer (SDN)**: A centralized Ryu SDN controller monitors real-time traffic statistics. When congestion is detected on the bottleneck link, it dynamically installs OpenFlow 1.3 flow matching rules on Open vSwitch (OVS) bridges, routing critical logs into a dedicated, hardware-rate-guaranteed VIP queue (Queue 1) while throttling best-effort logs into a secondary queue (Queue 0).

---

## 2. Team Work Distribution & Ownership

| Team Member | Role | Owned Source Files | Key Responsibilities |
|---|---|---|---|
| **Teammate A** | UDP Client & Traffic Generation | [`log_client.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/log_client.py)<br>[`flood.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/flood.py) | - UDP socket transmission<br>- IPv4 TOS socket option marking<br>- Monotonic sequence numbering<br>- Paced UDP background congestion flooding |
| **Teammate B** | Central Server & Metrics | [`log_server.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/log_server.py)<br>[`README.md`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/README.md) | - Multi-threaded UDP receiver<br>- One-way transit latency timing<br>- Sequence gap loss accounting<br>- 5-tier severity classification<br>- JSON export & project documentation |
| **Team Lead** | Architecture, SDN & Orchestration | [`protocol.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/protocol.py)<br>[`topology.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/topology.py)<br>[`sdn_controller.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/sdn_controller.py)<br>[`setup_qos.sh`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/setup_qos.sh)<br>[`analyze_results.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/analyze_results.py)<br>[`main.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/main.py)<br>[`test_suite.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/test_suite.py) | - RFC 2474 bit-shift math (`dscp << 2`)<br>- Mininet OpenFlow 1.3 virtual topology<br>- Ryu controller telemetry & dynamic QoS<br>- Linux HTB dual-queue OVS scheduler<br>- Full 5-phase simulation orchestrator<br>- Automated test suite verification |

---

## 3. End-to-End System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    CHRONOS ARCHITECTURE                                 |
+-----------------------------------------------------------------------------------------+

 [Client h1]  (10.0.0.1) ---\
                             \
 [Client h2]  (10.0.0.2) -------> [Switch s1] ---\
                             /                    \
 [Client h3]  (10.0.0.3) ---/                      \
                                                    +---> [Switch s2] 
 [Flooder h5] (10.0.0.5) --------------------------/           |
  (5 Mbps UDP Flood)                                           |
                                                    BOTTLENECK LINK (1.0 Mbps, 50-pkt buffer)
                                                    Port: s2-eth3 (Linux HTB Queues)
                                                    - Queue 1: VIP (800k - 1M)
                                                    - Queue 0: Best Effort (100k - 200k)
                                                               |
                                                               v
                                                          [Switch s4]
                                                               |
                                                               v
                                                    [Log Server h4] (10.0.0.4:5514)
                                                    - Latency calculation
                                                    - Sequence loss accounting
                                                    - 5-Tier categorization

                       +-----------------------------------+
                       |      Ryu OpenFlow Controller      |
                       |          (127.0.0.1:6633)         |
                       +-----------------------------------+
                         |                               |
                         | OFPFlowStatsRequest (4s poll) | OFPFlowMod (install QoS rules)
                         v                               v
                     [Switch s1]                    [Switch s2]
```

---

## 4. Teammate A Guide: Client & Congestion Generation

### 4.1 Log Client ([`log_client.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/log_client.py))
Teammate A is responsible for generating application logs, tagging them with priority, and transmitting them over connectionless UDP sockets.

#### Key Implementation Details:
1. **Socket Allocation**:
   ```python
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   ```
   Uses `SOCK_DGRAM` because UDP provides lightweight, connectionless transmission without handshake overhead or head-of-line blocking.
2. **Setting IPv4 Type of Service (TOS)**:
   ```python
   tos_val = SEVERITY_TOS.get(sev, 0)
   sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_val)
   ```
   This is the most critical line in `log_client.py`. It tells the Linux kernel network stack to stamp the 8-bit TOS field in the outgoing IPv4 packet header with `tos_val`.
3. **Monotonic Sequence Numbering**:
   ```python
   payload = create_log_payload(seq=seq, severity=sev, host=hostname, message=msg)
   seq += 1
   ```
   Every transmitted log receives an incrementing integer (`0, 1, 2, ...`). This allows the server to detect lost packets without TCP ACKs.
4. **Traffic Distribution Modeling**:
   Routine events (`DEBUG`: 35%, `INFO`: 35%) are generated frequently, while emergencies (`WARNING`: 15%, `ERROR`: 10%, `CRITICAL`: 5%) are generated realistically.

---

### 4.2 Traffic Congestion Flooder ([`flood.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/flood.py))
Teammate A also owns the congestion generator running on host `h5`.

#### Key Implementation Details:
1. **Traffic Volume & Bandwidth Math**:
   ```python
   bits_per_sec = rate_mbps * 1_000_000.0
   bits_per_pkt = actual_pkt_len * 8.0
   pkts_per_sec = bits_per_sec / bits_per_pkt
   interval = 1.0 / pkts_per_sec
   ```
   For 5.0 Mbps using 1400-byte datagrams:
   $$\text{Packets/sec} = \frac{5 \times 10^6}{1400 \times 8} \approx 446.4\text{ packets/s}$$
   $$\text{Interval} = \frac{1}{446.4} \approx 2.24\text{ ms}$$
2. **Packet Sizing (1400 Bytes)**:
   Kept under the standard 1500-byte Ethernet MTU to avoid IP packet fragmentation.
3. **Port Isolation (Port 9999)**:
   Sends flood traffic to port 9999 so it does not collide with log server port 5514. It congests the physical link without polluting application-layer server metrics.

---

### 4.3 Viva Questions for Teammate A

- **Q1: Why did we choose UDP instead of TCP for distributed logging?**  
  *Answer*: TCP has three major drawbacks for real-time telemetry: (1) Head-of-line blocking: if one packet is dropped, TCP halts all newer logs until retransmission completes; (2) Connection state overhead: maintaining TCP connections from thousands of microservices exhausts server file descriptors; (3) Slow-start: during an outage when burst alerts are sent, TCP delays transmission due to congestion avoidance. UDP sends immediately with zero connection overhead.

- **Q2: What does `setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_val)` actually do?**  
  *Answer*: It modifies the IP header of outgoing packets at the socket level. It writes `tos_val` into the second octet of the IPv4 header (bits 7–2 represent DSCP, bits 1–0 represent ECN). Routers and SDN switches read this byte to classify packets.

- **Q3: How do you enforce rate pacing in `flood.py`?**  
  *Answer*: By calculating the theoretical time each packet should be sent based on `start_time + (packets_sent * interval)`. If the current time is ahead of schedule, `time.sleep()` is called for the delta, preventing CPU-bound polling loops.

---

## 5. Teammate B Guide: Log Server & Documentation

### 5.1 Centralized Aggregation Server ([`log_server.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/log_server.py))
Teammate B is responsible for the server architecture, receiving datagrams, calculating performance metrics, and exporting structured reports.

#### Key Implementation Details:
1. **Socket Allocation & Port Reuse**:
   ```python
   self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
   self.sock.bind((self.bind_ip, self.port))
   ```
   `SO_REUSEADDR` prevents the `Address already in use` error when stopping and restarting the server during live evaluation.
2. **One-Way Transit Latency Measurement**:
   ```python
   receive_time = time.time()
   latency_ms = max((receive_time - entry["send_time"]) * 1000.0, 0.0)
   ```
   Because all hosts share synchronized clocks (local testbed or Mininet container namespace), subtracting the payload's `send_time` from `receive_time` provides the exact transit delay across the network.
3. **Application-Layer Sequence Gap Loss Accounting**:
   ```python
   expected = h_stat["expected_seq"]
   if seq > expected:
       gap = seq - expected
       h_stat["lost"] += gap
       self.total_lost += gap
       h_stat["expected_seq"] = seq + 1
   elif seq == expected:
       h_stat["expected_seq"] = seq + 1
   else:
       h_stat["out_of_order"] += 1
   ```
   If expected is 5 and incoming is 8, the server immediately knows datagrams 5, 6, and 7 were dropped in the bottleneck switch buffer.
4. **Partitioned Categorization & Export**:
   Logs are sorted into 5 independent arrays under a `threading.Lock()`. On shutdown (`Ctrl+C` or `SIGINT`), the server writes `results/logs_<severity>.json` and `results/server_summary.json`.

---

### 5.2 Viva Questions for Teammate B

- **Q1: How does the server detect lost UDP packets without TCP acknowledgments?**  
  *Answer*: Through application-level sequence tracking. Each client assigns monotonically increasing sequence numbers (`seq = 0, 1, 2...`). The server tracks `expected_seq` per host. Any sequence jump indicates dropped packets at the intermediate switch queue.

- **Q2: Why did you use multi-threading in `log_server.py`?**  
  *Answer*: To decouple the socket reception loop from terminal reporting. The primary thread runs a blocking `sock.recvfrom()` to ensure datagrams are ingested at maximum line rate without packet drops in the OS socket buffer. A secondary daemon thread runs `_stats_reporter_loop()` to print metrics every few seconds.

- **Q3: What data is stored in `server_summary.json`?**  
  *Answer*: Total packets transmitted, received, and lost; overall packet loss percentage; throughput (packets/sec); per-severity breakdown of counts and latencies (min, avg, max); and per-host sequence reception and loss rates.

---

## 6. Team Lead Guide: Protocol, SDN, Topology & Orchestration

The Team Lead is responsible for the theoretical protocol glue, Mininet infrastructure, Ryu SDN intelligence, queue scheduling, and the master `main.py` demonstration.

### 6.1 Protocol Bit-Shift Mathematics ([`protocol.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/protocol.py))
Per RFC 2474, the IPv4 Type of Service byte is structured as:
```
  0   1   2   3   4   5   6   7
+---+---+---+---+---+---+---+---+
|         DSCP          |  ECN  |
+---+---+---+---+---+---+---+---+
```
- Bits 7–2: Differentiated Services Code Point (6 bits, range 0–63)
- Bits 1–0: Explicit Congestion Notification (2 bits)

#### Mathematical Formula:
$$\text{TOS} = \text{DSCP} \ll 2$$
$$\text{DSCP} = (\text{TOS} \ \& \ \text{0xFC}) \gg 2$$

#### Mappings Used in Chronos:
- **`CRITICAL`**: Expedited Forwarding (EF) = DSCP 46 $\rightarrow 46 \times 4 = 184 = \text{0xB8}$
- **`ERROR`**: Assured Forwarding 41 (AF41) = DSCP 34 $\rightarrow 34 \times 4 = 136 = \text{0x88}$
- **`WARNING`**: Assured Forwarding 31 (AF31) = DSCP 26 $\rightarrow 26 \times 4 = 104 = \text{0x68}$
- **`INFO`**: Assured Forwarding 11 (AF11) = DSCP 10 $\rightarrow 10 \times 4 = 40 = \text{0x28}$
- **`DEBUG`**: Best Effort (CS0) = DSCP 0 $\rightarrow 0 \times 4 = 0 = \text{0x00}$

---

### 6.2 Network Topology ([`topology.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/topology.py))
- **Switches**: 4 Open vSwitch instances (`s1`, `s2`, `s3`, `s4`) running OpenFlow 1.3.
- **Edge Links**: 10 Mbps bandwidth, 1 ms delay.
- **Bottleneck Link (`s2 <-> s4`)**:
  ```python
  net.addLink(s2, s4, bw=1.0, delay="5ms", max_queue_size=50)
  ```
  Bandwidth is throttled to 1.0 Mbps with a 50-packet FIFO queue ceiling. When 5 Mbps of flood traffic converges on `s2`, the queue overflows immediately.

---

### 6.3 Linux HTB Hardware Queues ([`setup_qos.sh`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/setup_qos.sh))
Configures the Hierarchical Token Bucket scheduler on bottleneck port `s2-eth3`:
```bash
sudo ovs-vsctl set port s2-eth3 qos=@newqos -- \
    --id=@newqos create qos type=linux-htb \
        other-config:max-rate=1000000 \
        queues:0=@q0 queues:1=@q1 -- \
    --id=@q0 create queue \
        other-config:min-rate=100000 \
        other-config:max-rate=200000 -- \
    --id=@q1 create queue \
        other-config:min-rate=800000 \
        other-config:max-rate=1000000
```
- **Queue 0 (Best Effort)**: 100k min, capped at 200k max. Assigned to `DEBUG`, `INFO`, `WARNING`.
- **Queue 1 (VIP Priority)**: 800k min, burstable to 1000k max. Assigned to `CRITICAL` and `ERROR`.

---

### 6.4 Ryu OpenFlow 1.3 Controller ([`sdn_controller.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/sdn_controller.py))
1. **Table-Miss Rule**: Installed at priority 0. Unmatched packets trigger `PacketIn` to the controller.
2. **Learning Switch**: Learns source MACs and installs unicast flows with a 60-second idle timeout.
3. **Telemetry Polling**: Background green thread requests flow stats every 4 seconds (`OFPFlowStatsRequest`).
4. **Throughput Calculation**:
   $$\text{current\_bps} = \frac{(\text{total\_bytes} - \text{prev\_bytes}) \times 8}{\Delta t}$$
5. **Dynamic Rule Installation**: When throughput on `s2` exceeds 650 Kbps, installs flow rules matching DSCP bits:
   ```python
   match = parser.OFPMatch(eth_type=0x0800, ip_proto=17, ip_dscp=46)
   actions = [parser.OFPActionSetQueue(queue_id=1), parser.OFPActionOutput(ofproto.OFPP_NORMAL)]
   ```

---

### 6.5 Master Orchestrator ([`main.py`](file:///run/media/tin/New%20Volume/Shared/Notes/Sem%203/CN/Mini%20Project/Chronos_Log/main.py))
The self-contained 5-phase simulation executable:
- **Phase 1**: Boots the centralized UDP server on port 5514.
- **Phase 2**: Streams microservice logs tagged with IPv4 TOS in real time.
- **Phase 3**: Simulates 5.0 Mbps congestion over the 1.0 Mbps link and demonstrates uniform FIFO drops (critical alarms lost).
- **Phase 4**: Activates the Ryu SDN controller and demonstrates queue steering into Queue 1 vs Queue 0.
- **Phase 5**: Prints the comparative evaluation matrix and exports JSON files to `results/`.

---

## 7. Experimental Results & Viva Metrics

These are the exact numerical findings to cite during the viva presentation:

### Quantitative Performance Comparison

| Metric | Baseline (Legacy FIFO) | Chronos (SDN Dynamic QoS) | Improvement / Architectural Impact |
|---|---|---|---|
| **CRITICAL Log Packet Loss** | **42.2%** | **1.1%** *(0% in standalone/main)* | **97.4% reduction in lost critical alarms** |
| **ERROR Log Packet Loss** | **42.2%** | **4.4%** *(0% in standalone/main)* | **89.5% reduction in lost error events** |
| **WARNING Log Packet Loss** | 42.2% | 48.9% *(shed to Queue 0)* | Absorbs congestion to protect VIP logs |
| **INFO / DEBUG Loss** | 41.9% | 42.9% - 66.7% | Best-effort rate-capping (max 200 Kbps) |
| **CRITICAL Delivery Latency** | **34.6 ms - 48.5 ms** | **8.2 ms - 8.4 ms** | **76% lower latency (sub-10ms delivery)** |
| **Overall Link Utilization** | 100% (Unmanaged buffer tail-drop) | 100% (Managed dual-queue shaping) | Guaranteed throughput for critical telemetry |

---

## 8. Master Viva Defense & Common Trap Questions

### Trap Question 1: "Why did you shift by 2 bits in `dscp << 2`?"
**Model Answer**:  
"Per RFC 2474, the 8-bit IPv4 Type of Service octet was redefined such that the upper 6 bits (bits 7 through 2) contain the Differentiated Services Code Point (DSCP), while the lower 2 bits (bits 1 and 0) are allocated for Explicit Congestion Notification (ECN). Python's socket interface `IP_TOS` writes the full 8-bit octet into the header. If we do not left-shift by 2, a DSCP value like 46 (`00101110`) would be placed into the lower bits, corrupting the ECN field and resulting in a DSCP of 11. Shifting left by 2 aligns the 6 bits into bits 7–2."

### Trap Question 2: "Can't you just use standard IP QoS routers instead of SDN?"
**Model Answer**:  
"Traditional IP routers rely on static, hop-by-hop configuration. If a link becomes congested, static routers cannot dynamically reroute traffic, poll global telemetry, or adapt priorities based on network-wide load. With SDN, the control plane is decoupled from the data plane. The Ryu controller monitors centralized telemetry and installs hardware flow rules dynamically only when link utilization crosses our 650 Kbps threshold, keeping switch flow tables clean during normal operation."

### Trap Question 3: "How does Open vSwitch enforce bandwidth limits?"
**Model Answer**:  
"Open vSwitch interfaces with the Linux kernel Traffic Control (`tc`) subsystem using the Hierarchical Token Bucket (HTB) queuing discipline. In `setup_qos.sh`, we create a QoS record on port `s2-eth3` with a 1.0 Mbps ceiling and define two queues: Queue 0 (min 100k, max 200k) and Queue 1 (min 800k, max 1M). When OpenFlow flow rules execute `SetQueue(1)`, packets enter the 800k guaranteed bucket, protecting them from tail-drop."

### Trap Question 4: "What happens if a packet arrives out of order?"
**Model Answer**:  
"In `log_server.py`, the server checks `seq < expected_seq`. If a datagram has a sequence number lower than what was already observed, the server increments `out_of_order` rather than treating it as a drop. Because UDP is connectionless and packets may take alternate paths, tracking out-of-order deliveries prevents false-positive drop reports."

---

## 9. How to Run the Demo for Evaluation

All commands must be run from inside the repository directory:
```bash
cd "/run/media/tin/New Volume/Shared/Notes/Sem 3/CN/Mini Project/Chronos_Log"
```

### Option A: The Full 5-Phase End-to-End Simulation (Recommended)
This runs the master simulation script showing all 5 phases, socket streams, congestion drop, SDN QoS activation, and the final comparison matrix:
```bash
python3 main.py
```

### Option B: The Automated Unit & Integration Test Suite
To demonstrate code correctness and test coverage to the evaluator:
```bash
python3 test_suite.py
```
*Expected result: 9 tests run, all 9 pass.*

### Option C: The Fast 1-Second Terminal Live Demo
If the professor asks for a quick, concise verification of UDP socket streaming, kernel TOS marking, and queue mapping:
```bash
python3 demo.py
```

### Option D: Standalone Multi-Process Local Test
Spawns 3 background client processes against a live server process:
```bash
./run_experiment.sh standalone
```
*Outputs categorized logs and summary to `results/standalone/`.*

### Option E: Comparative Evaluation Table
To display the comparison matrix:
```bash
python3 analyze_results.py --use-benchmark
```
*Generates `comparison_report.txt` and `comparison_report.csv`.*
