#!/usr/bin/env python3
"""
Chronos Ryu OpenFlow 1.3 SDN Controller
Implements dynamic quality-of-service (QoS) flow control:
1. Acts as a Layer-2 learning switch with table-miss default routing.
2. Periodically polls flow statistics from Open vSwitch bridges.
3. Computes port throughput across the bottleneck switch (s2).
4. When throughput exceeds 650 Kbps, dynamically installs DiffServ OpenFlow flow rules
   mapping high-priority logs (DSCP 46/34) to Queue 1 (VIP) and best-effort to Queue 0.
"""

import time
from typing import Dict, List, Any

# Import Ryu SDN framework components with fallback dummies for linting outside Ryu environment
try:
    from ryu.base import app_manager
    from ryu.controller import ofp_event
    from ryu.controller.handler import (
        CONFIG_DISPATCHER,
        MAIN_DISPATCHER,
        set_ev_cls,
    )
    from ryu.ofproto import ofproto_v1_3
    from ryu.lib.packet import packet, ethernet, ipv4, udp
    from ryu.lib import hub
except ImportError:
    # Minimal mock classes allowing script inspection without ryu installed
    class DummyApp:
        OFP_VERSIONS = []
        def __init__(self, *args, **kwargs):
            pass
    app_manager = type("app_manager", (), {"RyuApp": DummyApp})
    ofp_event = type("ofp_event", (), {})
    CONFIG_DISPATCHER = 1
    MAIN_DISPATCHER = 2
    def set_ev_cls(*args, **kwargs):
        def dec(fn):
            return fn
        return dec
    ofproto_v1_3 = type("ofproto_v1_3", (), {"OFP_VERSION": 4})
    packet = None
    ethernet = None
    ipv4 = None
    udp = None
    hub = None


class ChronosQoSController(app_manager.RyuApp):
    """
    Ryu OpenFlow 1.3 Application managing dynamic telemetry and DiffServ queue assignment.
    """

    # Enforce OpenFlow 1.3 protocol negotiation
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Telemetry and threshold parameters
    STATS_POLL_INTERVAL = 4              # Polling period in seconds for flow statistics requests
    CONGESTION_THRESHOLD_BPS = 650000     # Bandwidth threshold: 650 Kbps triggers QoS activation
    BOTTLENECK_DPID = 2                   # Datapath ID of switch s2 (bottleneck gateway)
    BOTTLENECK_OUT_PORT = 3               # Egress port on s2 facing switch s4 (s2-eth3)

    def __init__(self, *args, **kwargs):
        super(ChronosQoSController, self).__init__(*args, **kwargs)
        # MAC-to-port learning table: {dpid: {mac_address: ingress_port}}
        self.mac_to_port: Dict[int, Dict[str, int]] = {}
        # Connected datapath switch objects: {dpid: datapath}
        self.datapaths: Dict[int, Any] = {}
        # Byte count history for calculating derivative bandwidth: {dpid: total_bytes}
        self.prev_byte_counts: Dict[int, int] = {}
        # Timestamp history for exact delta-time calculation: {dpid: epoch_time}
        self.last_stats_time: Dict[int, float] = {}

        # Operational status flags
        self.congestion_detected = False
        self.qos_rules_installed = False

        # Spawn asynchronous green thread for polling switch telemetry
        if hub is not None:
            self.monitor_thread = hub.spawn(self._telemetry_monitor_loop)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Invoked upon switch handshake completion (EventOFPSwitchFeatures).
        Installs the initial priority-0 Table-Miss flow entry directing unmatched packets to controller.
        """
        datapath = ev.msg.datapath
        dpid = datapath.id
        self.datapaths[dpid] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info(f"[SWITCH CONNECTED] DPID: {dpid} (OpenFlow 1.3)")

        # Create wildcard match object matching every incoming packet
        match = parser.OFPMatch()
        # Action: forward entire packet to the SDN controller without truncation
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]
        # Install rule with priority 0 (lowest possible priority in OpenFlow pipeline)
        self._add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(f"[FLOW INSTALL] Installed table-miss on DPID {dpid}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Processes PacketIn events sent when an incoming packet matches the table-miss rule.
        Implements self-learning switch behavior and installs precise forwarding flow entries.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        # Parse Ethernet layer headers
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        dst = eth.dst
        src = eth.src

        # Initialize MAC table for this switch DPID if unseen
        self.mac_to_port.setdefault(dpid, {})

        # Learn mapping between source MAC address and incoming switch port
        self.mac_to_port[dpid][src] = in_port

        # Determine egress forwarding port
        if dst in self.mac_to_port[dpid]:
            # Destination MAC is known: unicast out specific learned port
            out_port = self.mac_to_port[dpid][dst]
        else:
            # Destination MAC is unknown: flood across all ports except ingress
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # If destination was known, install flow entry with 60-second idle timeout to bypass controller next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self._add_flow(
                datapath,
                priority=1,
                match=match,
                actions=actions,
                idle_timeout=60,
            )

        # Handle buffer ID in case switch buffered the packet
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        # Push PacketOut to switch to transmit the currently buffered packet
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    def _telemetry_monitor_loop(self):
        """
        Periodic telemetry polling thread running continuously every STATS_POLL_INTERVAL seconds.
        """
        while True:
            # Dispatch statistics request to all registered switches
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            # Sleep until next polling cycle
            hub.sleep(self.STATS_POLL_INTERVAL)

    def _request_stats(self, datapath):
        """
        Transmits an OpenFlow 1.3 OFPFlowStatsRequest message to query byte and packet counters.
        """
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """
        Handles statistics reply messages from switches.
        Computes aggregate bandwidth and evaluates against congestion threshold.
        """
        body = ev.msg.body
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()

        total_bytes = 0
        total_packets = 0

        # Accumulate byte and packet counts across all flow entries
        for stat in body:
            total_bytes += stat.byte_count
            total_packets += stat.packet_count

        # Retrieve prior telemetry samples
        prev_bytes = self.prev_byte_counts.get(dpid, total_bytes)
        prev_time = self.last_stats_time.get(dpid, now)
        elapsed = max(now - prev_time, 0.001)

        # Compute delta bandwidth in bits per second: (delta_bytes * 8) / delta_seconds
        delta_bytes = max(total_bytes - prev_bytes, 0)
        current_bps = (delta_bytes * 8.0) / elapsed

        # Cache current values for subsequent measurement delta
        self.prev_byte_counts[dpid] = total_bytes
        self.last_stats_time[dpid] = now

        # Focus monitoring on bottleneck switch s2 (DPID 2)
        if dpid == self.BOTTLENECK_DPID:
            throughput_kbps = current_bps / 1000.0
            self.logger.info(
                f"[TELEMETRY] Switch s2 (DPID {dpid}) Throughput: {throughput_kbps:6.1f} Kbps "
                f"| Aggregate Packets: {total_packets}"
            )

            # Evaluate congestion condition against 650 Kbps threshold
            if current_bps >= self.CONGESTION_THRESHOLD_BPS:
                if not self.congestion_detected:
                    self.logger.warning(
                        f"[CONGESTION DETECTED] Bottleneck utilization ({throughput_kbps:.1f} Kbps) "
                        f"exceeded threshold ({self.CONGESTION_THRESHOLD_BPS/1000.0:.1f} Kbps)!"
                    )
                    self.congestion_detected = True
                    # Dynamically inject QoS prioritization flow rules
                    self._activate_qos_prioritization(datapath)
            else:
                if self.congestion_detected:
                    self.logger.info(
                        f"[CONGESTION CLEARED] Traffic decreased to {throughput_kbps:.1f} Kbps."
                    )
                    self.congestion_detected = False

    def _activate_qos_prioritization(self, datapath):
        """
        Dynamically installs OpenFlow 1.3 flow matching rules matching IPv4 DSCP tags
        and steering them into corresponding Linux HTB hardware queues on egress:
          - DSCP 46 (CRITICAL) -> Queue 1 (VIP Priority, 800k - 1000k bps)
          - DSCP 34 (ERROR)    -> Queue 1 (VIP Priority, 800k - 1000k bps)
          - DSCP 26 (WARNING)  -> Queue 0 (Best Effort, 100k - 200k bps)
          - DSCP 10 (INFO)     -> Queue 0 (Best Effort, 100k - 200k bps)
          - DSCP 0  (DEBUG)    -> Queue 0 (Best Effort, 100k - 200k bps)
        """
        if self.qos_rules_installed:
            return

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id

        self.logger.info(f"[QoS ACTIVE] Installing priority queue rules on DPID {dpid}...")

        # Rule 1: CRITICAL Traffic (DSCP 46 -> Queue 1, Priority 100)
        match_critical = parser.OFPMatch(
            eth_type=0x0800,  # Match IPv4 packets
            ip_proto=17,      # Match UDP protocol
            ip_dscp=46,       # Match Expedited Forwarding (EF) DSCP 46
        )
        actions_critical = [
            parser.OFPActionSetQueue(queue_id=1),       # Direct into VIP hardware queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL), # Normal forwarding pipeline
        ]
        self._add_flow(datapath, priority=100, match=match_critical, actions=actions_critical)
        self.logger.info(" -> Rule Added: DSCP 46 (CRITICAL) mapped to Queue 1 (Priority=100)")

        # Rule 2: ERROR Traffic (DSCP 34 -> Queue 1, Priority 90)
        match_error = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=34,       # Match AF41 DSCP 34
        )
        actions_error = [
            parser.OFPActionSetQueue(queue_id=1),       # Direct into VIP hardware queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=90, match=match_error, actions=actions_error)
        self.logger.info(" -> Rule Added: DSCP 34 (ERROR) mapped to Queue 1 (Priority=90)")

        # Rule 3: WARNING Traffic (DSCP 26 -> Queue 0, Priority 50)
        match_warning = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=26,       # Match AF31 DSCP 26
        )
        actions_warning = [
            parser.OFPActionSetQueue(queue_id=0),       # Direct into Best-Effort queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=50, match=match_warning, actions=actions_warning)

        # Rule 4: INFO Traffic (DSCP 10 -> Queue 0, Priority 40)
        match_info = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=10,       # Match AF11 DSCP 10
        )
        actions_info = [
            parser.OFPActionSetQueue(queue_id=0),       # Direct into Best-Effort queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=40, match=match_info, actions=actions_info)

        # Rule 5: DEBUG Traffic (DSCP 0 -> Queue 0, Priority 30)
        match_debug = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=0,        # Match Best Effort (CS0) DSCP 0
        )
        actions_debug = [
            parser.OFPActionSetQueue(queue_id=0),       # Direct into Best-Effort queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=30, match=match_debug, actions=actions_debug)

        self.qos_rules_installed = True
        self.logger.info("[QoS COMPLETE] All DiffServ prioritization rules installed successfully.")

    def _add_flow(
        self,
        datapath,
        priority: int,
        match,
        actions: list,
        idle_timeout: int = 0,
        hard_timeout: int = 0,
    ):
        """
        Helper method to construct and transmit an OFPFlowMod message to the switch datapath.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Instructions encapsulate actions to apply immediately upon matching
        instructions = [
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
        ]

        # Construct FlowMod modification command
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        )
        # Send FlowMod message over OpenFlow control channel to switch
        datapath.send_msg(mod)
