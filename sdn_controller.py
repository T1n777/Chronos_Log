#!/usr/bin/env python3

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

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    STATS_POLL_INTERVAL = 4
    CONGESTION_THRESHOLD_BPS = 650000
    BOTTLENECK_DPID = 2
    BOTTLENECK_OUT_PORT = 3

    def __init__(self, *args, **kwargs):
        super(ChronosQoSController, self).__init__(*args, **kwargs)
        self.mac_to_port: Dict[int, Dict[str, int]] = {}
        self.datapaths: Dict[int, Any] = {}
        self.prev_byte_counts: Dict[int, int] = {}
        self.last_stats_time: Dict[int, float] = {}

        self.congestion_detected = False
        self.qos_rules_installed = False

        if hub is not None:
            self.monitor_thread = hub.spawn(self._telemetry_monitor_loop)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id
        self.datapaths[dpid] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.logger.info(f"[SWITCH CONNECTED] DPID: {dpid} (OpenFlow 1.3)")

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )
        ]
        self._add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(f"[FLOW INSTALL] Installed table-miss on DPID {dpid}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

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

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)

            self._add_flow(
                datapath,
                priority=1,
                match=match,
                actions=actions,
                idle_timeout=60,
            )

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

    def _telemetry_monitor_loop(self):

        while True:
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            hub.sleep(self.STATS_POLL_INTERVAL)

    def _request_stats(self, datapath):

        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):

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

        delta_bytes = max(total_bytes - prev_bytes, 0)
        current_bps = (delta_bytes * 8.0) / elapsed

        self.prev_byte_counts[dpid] = total_bytes
        self.last_stats_time[dpid] = now

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

    def _activate_qos_prioritization(self, datapath):

        if self.qos_rules_installed:
            return

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id

        self.logger.info(f"[QoS ACTIVE] Installing priority queue rules on DPID {dpid}...")

        match_critical = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=46,
        )
        actions_critical = [
            parser.OFPActionSetQueue(queue_id=1),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=100, match=match_critical, actions=actions_critical)
        self.logger.info(" -> Rule Added: DSCP 46 (CRITICAL) mapped to Queue 1 (Priority=100)")

        match_error = parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=17,
            ip_dscp=34,
        )
        actions_error = [
            parser.OFPActionSetQueue(queue_id=1),
            parser.OFPActionOutput(ofproto.OFPP_NORMAL),
        ]
        self._add_flow(datapath, priority=90, match=match_error, actions=actions_error)
        self.logger.info(" -> Rule Added: DSCP 34 (ERROR) mapped to Queue 1 (Priority=90)")

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

    def _add_flow(
        self,
        datapath,
        priority: int,
        match,
        actions: list,
        idle_timeout: int = 0,
        hard_timeout: int = 0,
    ):

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
