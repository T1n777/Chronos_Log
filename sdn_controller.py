#!/usr/bin/env python3
"""
sdn_controller.py - Ryu SDN Controller with Dynamic Congestion Detection and QoS

An OpenFlow 1.3 controller application that provides:
1. Standard Layer 2 MAC learning and packet forwarding.
2. Periodic flow and port statistics telemetry across all connected switches.
3. Automated congestion detection on the bottleneck link (switch s2 / s4).
4. Dynamic installation of DiffServ/DSCP-aware QoS flow entries that steer
   CRITICAL and ERROR UDP log datagrams into priority hardware queues.
"""

import time
from typing import Dict, List, Any

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
    # Dummy mock classes to allow syntax checking without ryu installed
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
    OpenFlow 1.3 Ryu Application for Log Aggregation QoS Management.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Telemetry and Congestion Threshold Parameters
    STATS_POLL_INTERVAL = 4              # Poll switches every 4 seconds
    CONGESTION_THRESHOLD_BPS = 650000    # >650 Kbps on 1 Mbps link indicates congestion
    BOTTLENECK_DPID = 2                  # Switch s2 DPID in Mininet
    BOTTLENECK_OUT_PORT = 3              # Typical port on s2 toward s4 (auto-learned if dynamic)

    def __init__(self, *args, **kwargs):
        super(ChronosQoSController, self).__init__(*args, **kwargs)
        self.mac_to_port: Dict[int, Dict[str, int]] = {}
        self.datapaths: Dict[int, Any] = {}
        self.prev_byte_counts: Dict[int, int] = {}
        self.last_stats_time: Dict[int, float] = {}

        # Congestion and QoS state flags
        self.congestion_detected = False
        self.qos_rules_installed = False

        # Spawn background monitoring thread if hub is available
        if hub is not None:
            self.monitor_thread = hub.spawn(self._telemetry_monitor_loop)

    # -------------------------------------------------------------------------
    # Switch Handshake & Table-Miss Installation
    # -------------------------------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Executed when a switch connects to the controller.
        Installs the default table-miss entry (priority 0) to forward unmatched
        packets to the controller for MAC learning.
        """
        datapath = ev.msg.datapath
        dpid = datapath.id
        self.datapaths[dpid] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info(f"[SWITCH CONNECTED] DPID: {dpid} (OpenFlow 1.3)")

        # Table-miss flow entry: Match all packets -> send to Controller
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]
        self._add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(f"[FLOW INSTALL] Installed table-miss on DPID {dpid}")

    # -------------------------------------------------------------------------
    # Layer-2 MAC Learning & Packet Forwarding
    # -------------------------------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Handles packets forwarded to the controller.
        Learns source MAC port mappings and installs unicast forwarding flows.
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return

        dst = eth.dst
        src = eth.src

        self.mac_to_port.setdefault(dpid, {})
        # Record source MAC address to input port
        self.mac_to_port[dpid][src] = in_port

        # Determine destination port
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # If unicast destination is known, install flow rule (priority 1)
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            # Flow rule with idle timeout to allow dynamic updates
            self._add_flow(
                datapath,
                priority=1,
                match=match,
                actions=actions,
                idle_timeout=60,
            )

        # Forward current packet out
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    # -------------------------------------------------------------------------
    # Network Flow Telemetry & Congestion Monitoring
    # -------------------------------------------------------------------------

    def _telemetry_monitor_loop(self):
        """
        Background loop requesting flow statistics from all switches.
        """
        while True:
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            hub.sleep(self.STATS_POLL_INTERVAL)

    def _request_stats(self, datapath):
        """
        Send an OpenFlow flow stats request.
        """
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """
        Processes switch flow statistics reply.
        Calculates aggregate link utilization and evaluates congestion.
        """
        body = ev.msg.body
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()

        total_bytes = 0
        total_packets = 0

        for stat in body:
            total_bytes += stat.byte_count
            total_packets += stat.packet_count

        prev_bytes = self.prev_byte_counts.get(dpid, total_bytes)
        prev_time = self.last_stats_time.get(dpid, now)
        elapsed = max(now - prev_time, 0.001)

        # Calculate throughput in bits per second (bps)
        delta_bytes = max(total_bytes - prev_bytes, 0)
        current_bps = (delta_bytes * 8.0) / elapsed

        self.prev_byte_counts[dpid] = total_bytes
        self.last_stats_time[dpid] = now

        # Focus congestion monitoring on the designated bottleneck switch (s2)
        if dpid == self.BOTTLENECK_DPID:
            throughput_kbps = current_bps / 1000.0
            self.logger.info(
                f"[TELEMETRY] Switch s2 (DPID {dpid}) Throughput: {throughput_kbps:6.1f} Kbps "
                f"| Aggregate Packets: {total_packets}"
            )

            if current_bps >= self.CONGESTION_THRESHOLD_BPS:
                if not self.congestion_detected:
                    self.logger.warning(
                        f"[CONGESTION DETECTED] Bottleneck utilization ({throughput_kbps:.1f} Kbps) "
                        f"exceeded threshold ({self.CONGESTION_THRESHOLD_BPS/1000.0:.1f} Kbps)!"
                    )
                    self.congestion_detected = True
                    self._activate_qos_prioritization(datapath)
            else:
                if self.congestion_detected:
                    self.logger.info(
                        f"[CONGESTION CLEARED] Traffic decreased to {throughput_kbps:.1f} Kbps."
                    )
                    self.congestion_detected = False

    # -------------------------------------------------------------------------
    # Dynamic QoS Prioritization Rule Installation
    # -------------------------------------------------------------------------

    def _activate_qos_prioritization(self, datapath):
        """
        Install high-priority OpenFlow flow rules matching on IP DSCP values.
        Critical (DSCP 46) and Error (DSCP 34) packets are routed to priority Queue 1.
        All other traffic routes through best-effort Queue 0.
        """
        if self.qos_rules_installed:
            return

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id

        self.logger.info(f"[QoS ACTIVE] Installing priority queue rules on DPID {dpid}...")

        # Rule 1: CRITICAL Logs (DSCP 46 / EF) -> Priority Queue 1 (High priority)
        match_critical = parser.OFPMatch(
            eth_type=0x0800,  # IPv4
            ip_proto=17,      # UDP
            ip_dscp=46,       # Expedited Forwarding (EF)
        )
        actions_critical = [
            parser.OFPActionSetQueue(queue_id=1),  # Send to High-Priority Queue
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=100, match=match_critical, actions=actions_critical)
        self.logger.info(" -> Rule Added: DSCP 46 (CRITICAL) mapped to Queue 1 (Priority=100)")

        # Rule 2: ERROR Logs (DSCP 34 / AF41) -> Priority Queue 1
        match_error = parser.OFPMatch(
            eth_type=0x0800,  # IPv4
            ip_proto=17,      # UDP
            ip_dscp=34,       # Assured Forwarding 41
        )
        actions_error = [
            parser.OFPActionSetQueue(queue_id=1),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=90, match=match_error, actions=actions_error)
        self.logger.info(" -> Rule Added: DSCP 34 (ERROR) mapped to Queue 1 (Priority=90)")

        # Rule 3: WARNING Logs (DSCP 26 / AF31) -> Best Effort Queue 0
        match_warning = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=26,
        )
        actions_warning = [
            parser.OFPActionSetQueue(queue_id=0),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=50, match=match_warning, actions=actions_warning)

        # Rule 4: INFO Logs (DSCP 10 / AF11) -> Best Effort Queue 0
        match_info = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=10,
        )
        actions_info = [
            parser.OFPActionSetQueue(queue_id=0),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=40, match=match_info, actions=actions_info)

        # Rule 5: DEBUG Logs (DSCP 0 / BE) -> Best Effort Queue 0
        match_debug = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=0,
        )
        actions_debug = [
            parser.OFPActionSetQueue(queue_id=0),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=30, match=match_debug, actions=actions_debug)

        self.qos_rules_installed = True
        self.logger.info("[QoS COMPLETE] All DiffServ prioritization rules installed successfully.")

    # -------------------------------------------------------------------------
    # Helper: Flow Mod Installation
    # -------------------------------------------------------------------------

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
        Construct and transmit an OFPFlowMod message to a switch.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        )
        datapath.send_msg(mod)
