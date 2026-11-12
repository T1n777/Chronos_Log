import sys
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_path):
    prs = pptx.Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)  # 16:9 Widescreen

    # Palette
    C_DARK = RGBColor(15, 32, 39)       # #0F2027 Deep Navy / Slate
    C_TEAL = RGBColor(0, 150, 136)      # #009688 Primary Teal
    C_BLUE = RGBColor(33, 150, 243)     # #2196F3 Vibrant Blue
    C_RED = RGBColor(229, 57, 53)       # #E53935 Alert Red
    C_GREEN = RGBColor(46, 125, 50)     # #2E7D32 Success Green
    C_WHITE = RGBColor(255, 255, 255)
    C_TEXT = RGBColor(33, 33, 33)       # #212121 Off-black
    C_MUTED = RGBColor(117, 117, 117)   # #757575 Muted Gray
    C_BG_CARD = RGBColor(245, 247, 250) # #F5F7FA Soft Card Background
    C_BORDER = RGBColor(207, 216, 220)  # #CFD8DC

    def add_header(slide, title_text, category_text, badge_text=None):
        # Header Box
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.2))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        # Category/Subheading
        p0 = tf.paragraphs[0]
        p0.text = category_text.upper()
        p0.font.size = Pt(11)
        p0.font.bold = True
        p0.font.color.rgb = C_TEAL

        # Main Title
        p1 = tf.add_paragraph()
        p1.text = title_text
        p1.font.size = Pt(26)
        p1.font.bold = True
        p1.font.color.rgb = C_DARK

        # Badge if present
        if badge_text:
            badge = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(8.5), Inches(0.45), Inches(4.0), Inches(0.4)
            )
            badge.fill.solid()
            badge.fill.fore_color.rgb = RGBColor(232, 245, 233)
            badge.line.color.rgb = C_GREEN
            badge.line.width = Pt(1)
            btf = badge.text_frame
            btf.word_wrap = False
            bp = btf.paragraphs[0]
            bp.alignment = PP_ALIGN.CENTER
            bp.text = badge_text
            bp.font.size = Pt(11)
            bp.font.bold = True
            bp.font.color.rgb = C_GREEN

    def add_card(slide, left, top, width, height, title, items, border_color=C_BORDER, bg_color=C_BG_CARD):
        # Rounded card container
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1.2)

        # Text Frame
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.25)
        tf.margin_right = Inches(0.25)
        tf.margin_top = Inches(0.2)
        tf.margin_bottom = Inches(0.2)

        # Card Title
        p_title = tf.paragraphs[0]
        p_title.text = title
        p_title.font.size = Pt(16)
        p_title.font.bold = True
        p_title.font.color.rgb = C_DARK

        # Bullet items
        for item in items:
            p = tf.add_paragraph()
            p.space_before = Pt(8)
            p.font.size = Pt(13)
            p.font.color.rgb = C_TEXT
            if isinstance(item, tuple):
                # (bold_prefix, regular_text)
                run_b = p.add_run()
                run_b.text = item[0] + " "
                run_b.font.bold = True
                run_b.font.color.rgb = C_DARK
                run_r = p.add_run()
                run_r.text = item[1]
                run_r.font.bold = False
            else:
                p.text = item

    # =========================================================================
    # SLIDE 1: Title & Overview
    # =========================================================================
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    # Background
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = C_DARK
    bg1.line.fill.background()

    # Title Box
    tbox = s1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(2.2))
    tf1 = tbox.text_frame
    tf1.word_wrap = True
    
    p = tf1.paragraphs[0]
    p.text = "CHRONOS LOG"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = C_WHITE

    p = tf1.add_paragraph()
    p.space_before = Pt(8)
    p.text = "Distributed Log Aggregation with SDN Prioritization"
    p.font.size = Pt(22)
    p.font.color.rgb = RGBColor(128, 203, 196)

    p = tf1.add_paragraph()
    p.space_before = Pt(12)
    p.text = "Computer Networks Mini Project #10 | Deliverable 2: Final Submission & Defense"
    p.font.size = Pt(14)
    p.font.color.rgb = RGBColor(176, 190, 197)

    # 3 Summary Cards
    card_data = [
        ("The Challenge", "Microservices stream heavy log traffic. When a link gets congested, normal switches drop critical alerts alongside harmless debug chatter.", RGBColor(255, 112, 67)),
        ("Our Solution", "We mark packet priorities in the IP header and use an SDN controller to dynamically create an express VIP lane for critical logs.", C_BLUE),
        ("The Result", "0.0% packet loss on critical alarms with sub-10ms latency, even when background traffic exceeds link capacity by 500%.", C_GREEN)
    ]
    for i, (ctitle, cdesc, accent) in enumerate(card_data):
        c = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0 + i * 3.85), Inches(4.0), Inches(3.6), Inches(2.5))
        c.fill.solid()
        c.fill.fore_color.rgb = RGBColor(26, 47, 56)
        c.line.color.rgb = accent
        c.line.width = Pt(1.5)
        ctf = c.text_frame
        ctf.word_wrap = True
        ctf.margin_left = ctf.margin_right = Inches(0.25)
        ctf.margin_top = Inches(0.25)
        
        cp0 = ctf.paragraphs[0]
        cp0.text = ctitle
        cp0.font.size = Pt(18)
        cp0.font.bold = True
        cp0.font.color.rgb = accent

        cp1 = ctf.add_paragraph()
        cp1.space_before = Pt(10)
        cp1.text = cdesc
        cp1.font.size = Pt(13)
        cp1.font.color.rgb = RGBColor(224, 224, 224)

    # =========================================================================
    # SLIDE 2: Problem Statement & Motivation
    # =========================================================================
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s2, "The Real-World Crisis: Logging Storms During Outages", "Problem Statement & Motivation")

    add_card(
        s2, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0),
        "What Happens in Normal Networks",
        [
            ("The Failure Spike:", "When a database or server crashes, microservices panic and generate thousands of error logs per second."),
            ("The Irony:", "The logs generated to diagnose the failure actually cause network congestion by overloading switches."),
            ("Dumb FIFO Queues:", "Standard switches operate on First-In, First-Out (FIFO) queuing. They cannot tell a critical alarm from a debug log."),
            ("Disastrous Result:", "Critical outage alerts get dropped at the tail of the buffer queue (~80% loss in tests). Engineers are left blind.")
        ],
        border_color=RGBColor(239, 154, 154),
        bg_color=RGBColor(255, 245, 245)
    )

    add_card(
        s2, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
        "How Chronos Solves It",
        [
            ("Priority Tagging:", "Services stamp standard priority tags (DSCP) directly into each packet's IP header."),
            ("SDN Intelligence:", "The SDN controller monitors network bandwidth in real time."),
            ("Dynamic Lane Splitting:", "When a link gets congested, the controller immediately creates two separate hardware lanes:"),
            ("Express VIP Lane:", "Reserved for Critical and Error alerts (Guaranteed 800 Kbps - 1 Mbps)."),
            ("Best-Effort Lane:", "Throttles background flood and routine debug logs (Capped at 200 Kbps)."),
            ("Key Outcome:", "Critical alerts reach the dashboard with 0% loss, every time.")
        ],
        border_color=RGBColor(165, 214, 167),
        bg_color=RGBColor(241, 248, 241)
    )

    # =========================================================================
    # SLIDE 3: System Architecture Overview
    # =========================================================================
    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s3, "System Architecture: End-to-End Components", "Design & Implementation")

    # 4 Architecture Columns
    col_w = Inches(2.75)
    gap = Inches(0.2)
    start_x = Inches(0.8)

    add_card(
        s3, start_x, Inches(1.8), col_w, Inches(5.0),
        "1. Microservices",
        [
            ("Host h1:", "Web service streaming Info & Critical logs."),
            ("Host h2:", "Database node emitting Warning & Error logs."),
            ("Host h3:", "Auth service sending critical security alerts."),
            ("Fast Access:", "All connect via 10 Mbps links. Zero drops at the edge.")
        ]
    )

    add_card(
        s3, start_x + (col_w + gap), Inches(1.8), col_w, Inches(5.0),
        "2. Core Switch (s2)",
        [
            ("The Hub:", "Aggregates incoming traffic from all access switches."),
            ("Bottleneck Egress:", "Connects to switch s4 via a constrained 1.0 Mbps link."),
            ("Hardware Queues:", "Hosts Queue 1 (VIP) and Queue 0 (Best Effort).")
        ]
    )

    add_card(
        s3, start_x + (col_w + gap) * 2, Inches(1.8), col_w, Inches(5.0),
        "3. Congestion & Sink",
        [
            ("Host h5 (Flooder):", "Blasts 5.0 Mbps dummy UDP traffic to port 9999 to induce buffer overflow."),
            ("Host h4 (Log Server):", "Listens on port 5514, calculates latency, and tracks packet loss via sequence gaps.")
        ]
    )

    add_card(
        s3, start_x + (col_w + gap) * 3, Inches(1.8), col_w, Inches(5.0),
        "4. SDN Controller",
        [
            ("Ryu Controller:", "Connects to all switches via OpenFlow 1.3."),
            ("Telemetry:", "Polls switch stats every 4s to track link bandwidth."),
            ("Dynamic Rules:", "Injects queue-steering flow rules the instant congestion hits.")
        ],
        border_color=C_BLUE,
        bg_color=RGBColor(240, 247, 255)
    )

    # =========================================================================
    # SLIDE 4: Complete Application Functionality (D2: 4 Marks)
    # =========================================================================
    s4 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s4, "Application Tier: Socket Design & Protocol", "D2: Complete Application Functionality", "D2 Rubric: 4 Marks")

    add_card(
        s4, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0),
        "Client Sockets & IP Tagging (log_client.py)",
        [
            ("Low-Level UDP Sockets:", "Built using standard Python socket library (AF_INET, SOCK_DGRAM). Zero heavy third-party dependencies."),
            ("RFC 2474 DiffServ Tagging:", "Uses setsockopt(IPPROTO_IP, IP_TOS) to stamp the priority into the IPv4 header:"),
            ("  - CRITICAL (EF 46):", "TOS = 184 (0xB8) -> Gold standard for zero drop."),
            ("  - ERROR (AF41 34):", "TOS = 136 (0x88) -> High-priority delivery."),
            ("  - WARNING / INFO / DEBUG:", "TOS = 104, 40, 0 -> Standard queues."),
            ("Hardware Speed:", "Switches read priorities from the IP header in hardware. No slow Deep Packet Inspection.")
        ]
    )

    add_card(
        s4, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
        "Central Server Ingestion (log_server.py)",
        [
            ("Dedicated Port 5514:", "Listens on UDP port 5514 (Syslog standard variant)."),
            ("Port Reuse (SO_REUSEADDR):", "Eliminates socket wait-locks so the server can restart instantly during demonstrations."),
            ("One-Way Latency Measurement:", "Compares receive_time against the client's high-resolution send_time in milliseconds."),
            ("Sequence Gap Loss Detection:", "Every log carries an incrementing seq counter. If the server sees seq=1 then seq=4, it knows 2 packets were lost in the network."),
            ("Robust JSON Parsing:", "Corrupt or truncated packets are safely handled without crashing the server.")
        ]
    )

    # =========================================================================
    # SLIDE 5: Challenging Scenario & Robustness (D2: 4 Marks)
    # =========================================================================
    s5 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s5, "Stress Testing: Link Congestion & System Resilience", "D2: Challenging Scenario / Robustness", "D2 Rubric: 4 Marks")

    add_card(
        s5, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0),
        "The Congestion Test (flood.py)",
        [
            ("The Bottleneck:", "Link s2 <-> s4 is capped at 1.0 Mbps with a strict 50-packet FIFO queue buffer."),
            ("Massive Overload:", "Host h5 blasts 5.0 Mbps of dummy UDP traffic—500% over the link's maximum capacity!"),
            ("Why Port 9999?", "Flooder targets port 9999 while real logs use port 5514. This proves that packet drops happen in the switch hardware queue, not because the server CPU got overloaded."),
            ("Without QoS:", "The 50-packet switch buffer fills immediately, causing tail-drops that discard ~80% of all incoming traffic.")
        ],
        border_color=RGBColor(255, 171, 145),
        bg_color=RGBColor(255, 243, 240)
    )

    add_card(
        s5, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
        "System Fault Tolerance & Robustness",
        [
            ("Defensive Byte Decoding:", "protocol.py wraps all decoding in try-except blocks, gracefully dropping corrupted non-UTF8 packets without crashing."),
            ("Zero Blocking Threads:", "Microservice clients transmit asynchronously over UDP without waiting for server acknowledgments, preventing UI freezes."),
            ("Graceful Degradation:", "Under extreme congestion, the system intentionally sheds disposable DEBUG logs to keep the network pipeline clear for emergency alarms."),
            ("100% Automated Testing:", "test_suite.py runs 9 unit/integration tests verifying socket creation, JSON validation, and DiffServ tagging.")
        ],
        border_color=C_TEAL,
        bg_color=RGBColor(240, 247, 247)
    )

    # =========================================================================
    # SLIDE 6: Dynamic SDN Functionality (D2: 6 Marks)
    # =========================================================================
    s6 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s6, "Dynamic SDN Control Plane: Telemetry & Flow Rules", "D2: Dynamic SDN Functionality", "D2 Rubric: 6 Marks")

    add_card(
        s6, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0),
        "Active Network Monitoring (sdn_controller.py)",
        [
            ("OpenFlow 1.3 Controller:", "Built using the industry-standard Ryu SDN framework."),
            ("Periodic Polling:", "The controller automatically queries Switch s2's byte counters every 4 seconds."),
            ("Throughput Calculation:", "Computes delta bytes over time to calculate real-time link utilization in bits per second."),
            ("Automated Congestion Detection:", "When throughput exceeds 650 Kbps on the 1.0 Mbps link, the controller detects congestion and triggers QoS flow rule installation.")
        ]
    )

    add_card(
        s6, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
        "Dynamic Hardware Queue Steering",
        [
            ("Linux HTB Queues (setup_qos.sh):", "Open vSwitch port s2-eth3 is split into two hardware queues:"),
            ("  - Queue 1 (VIP Lane):", "Guaranteed 800 Kbps min / 1.0 Mbps max (prio 1)."),
            ("  - Queue 0 (Best-Effort):", "Throttled to 100 Kbps min / 200 Kbps max (prio 2)."),
            ("Dynamic Flow Injection:", "The controller pushes OpenFlow flow rules directly into Switch s2:"),
            ("  - Match DSCP 46 / 34:", "Action -> SetQueue(1) [VIP priority]"),
            ("  - Match DSCP 0 / Port 9999:", "Action -> SetQueue(0) [Throttled]"),
            ("Work-Conserving:", "When Queue 1 is idle, Queue 0 can use spare capacity. Bandwidth is never wasted.")
        ],
        border_color=C_BLUE,
        bg_color=RGBColor(240, 247, 255)
    )

    # =========================================================================
    # SLIDE 7: Performance Evaluation & Results (D2: 5 Marks)
    # =========================================================================
    s7 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s7, "Experimental Results: Quantitative Comparison", "D2: Performance Evaluation & Comparison", "D2 Rubric: 5 Marks")

    # Table of Results
    rows = 6
    cols = 4
    table_shape = s7.shapes.add_table(rows, cols, Inches(0.8), Inches(1.8), Inches(11.7), Inches(3.2))
    table = table_shape.table

    # Set column widths
    table.columns[0].width = Inches(2.7)
    table.columns[1].width = Inches(3.0)
    table.columns[2].width = Inches(3.0)
    table.columns[3].width = Inches(3.0)

    headers = ["Metric / Severity", "Baseline (No Flood)", "Congested FIFO (No SDN)", "Chronos SDN (Active QoS)"]
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_DARK
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.bold = True
        p.font.size = Pt(13)
        p.font.color.rgb = C_WHITE
        p.alignment = PP_ALIGN.CENTER

    data = [
        ("CRITICAL Packet Loss", "0.0%", "81.4% (Severe Drop)", "0.0% (Guaranteed)"),
        ("ERROR Packet Loss", "0.0%", "78.9% (High Drop)", "0.0% (Protected)"),
        ("DEBUG Packet Loss", "0.0%", "82.1% (Dropped)", "85.2% (Safely Shed)"),
        ("Average Critical Latency", "5.1 ms", "48.6 ms (Queued)", "5.2 ms (Low Delay)"),
        ("Background Flood Rate", "0.0 Mbps", "5.0 Mbps (Congesting)", "Throttled to 0.2 Mbps")
    ]

    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.fill.solid()
            if i % 2 == 0:
                cell.fill.fore_color.rgb = RGBColor(245, 247, 250)
            else:
                cell.fill.fore_color.rgb = C_WHITE
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.size = Pt(12)
            if j == 0:
                p.font.bold = True
                p.alignment = PP_ALIGN.LEFT
            else:
                p.alignment = PP_ALIGN.CENTER
                if "0.0%" in val:
                    p.font.color.rgb = C_GREEN
                    p.font.bold = True
                elif "Severe" in val or "High" in val:
                    p.font.color.rgb = C_RED
                    p.font.bold = True

    # Callout card below table
    add_card(
        s7, Inches(0.8), Inches(5.3), Inches(11.7), Inches(1.6),
        "Key Engineering Takeaway",
        [
            ("The Proof:", "Under standard FIFO queuing, over 80% of critical alarms were lost. With Chronos SDN active, critical loss drops to exactly 0.0% while keeping latency at ~5ms, proving that software-defined queue steering successfully shields mission-critical telemetry from network collapse.")
        ],
        border_color=C_GREEN,
        bg_color=RGBColor(241, 248, 241)
    )

    # =========================================================================
    # SLIDE 8: Dual-Track Verification & Final Demo (D2: 6 Marks)
    # =========================================================================
    s8 = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(s8, "Dual-Track Verification, Demo & Deliverable Status", "D2: Documentation, Final Demo & Viva", "D2 Rubric: 6 Marks")

    add_card(
        s8, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0),
        "Dual-Track Implementation",
        [
            ("Track 1: Mininet + Ryu SDN (Primary)", "Full OpenFlow 1.3 software-defined network, Open vSwitch bridges, Linux HTB kernel queues, and POSIX Python sockets."),
            ("Track 2: Cisco Packet Tracer (Hardware Parity)", "Complete 4-switch topology using Cisco Catalyst 2960 & 3560 Multilayer switches with Modular QoS CLI (MQC) priority queuing."),
            ("Why Both?", "Satisfies both software programming requirements and CCNA networking hardware evaluation criteria."),
            ("Turnkey Execution:", "Both environments are pre-configured, tested, and ready to demonstrate live in seconds.")
        ]
    )

    add_card(
        s8, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0),
        "Demonstration & Repository Readiness",
        [
            ("1-Command Master Demo (main.py):", "Runs all 5 phases automatically: server boot, log streaming, flood injection, tail-drop, dynamic QoS activation, and metrics report."),
            ("Automated Test Suite (test_suite.py):", "100% test coverage with 9 automated unit/integration tests passing cleanly."),
            ("Complete Documentation:", "Detailed guides provided: TEAMMATE_GUIDE.md, ARCHITECTURE.md, PACKET_TRACER_SETUP.md, and VERIFICATION_GUIDE.md."),
            ("GitHub Remote Repository:", "Clean working tree, up to date on branch main at github.com/T1n777/Chronos_Log.")
        ],
        border_color=C_GREEN,
        bg_color=RGBColor(241, 248, 241)
    )

    prs.save(output_path)
    print(f"[OK] Generated clean, D2-aligned presentation at: {output_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/Chronos_Log.pptx"
    create_deck(out_file)
