"""Generate the 5 Experimental Setup & Architectural Blueprint Figures for NetTwin 3.0 Papers.

Figures:
1. Paper 1: Figure 1 - NetTwin Organization Twin — Offline Evaluation Core (Paper 1 Scope)
2. Paper 2: Figure 2 - Dual-Region WAN Synchronization & Zero-Disk Streaming (Paper 2 Scope)
3. Paper 3: Figure 3 - IoT/5G Generalization Across 12 Next-Gen Datasets (Paper 3 Scope)
4. Paper 4: Figure 4 - Closed-Loop Safe Autonomous Response (Paper 4 Scope)
5. Paper 5: Figure 5 - Conformal LLM SOC Analyst — Air-Gapped Privacy (Paper 5 Scope)
"""
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Style constants
FONT_FAMILY = 'DejaVu Sans'
plt.rcParams['font.sans-serif'] = FONT_FAMILY
plt.rcParams['font.family'] = 'sans-serif'

COLOR_BLUE_PRIMARY = '#0078D4'
COLOR_BLUE_DARK = '#004B87'
COLOR_BLUE_LIGHT = '#F0F6FD'
COLOR_BLUE_BORDER = '#2B88D8'
COLOR_TEXT_MAIN = '#1F2428'
COLOR_TEXT_MUTED = '#586069'
COLOR_GREEN = '#107C41'
COLOR_GREEN_LIGHT = '#EBF8EE'
COLOR_RED = '#D13438'
COLOR_RED_LIGHT = '#FFF0F0'
COLOR_YELLOW_LIGHT = '#FFF4CE'
COLOR_YELLOW_BORDER = '#D89B00'
COLOR_FOOTER = '#004578'


def draw_box(ax, x, y, w, h, bg_color='#FFFFFF', border_color='#0078D4', lw=1.5, radius=1.5, zorder=1):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.1,rounding_size={radius}",
        facecolor=bg_color,
        edgecolor=border_color,
        linewidth=lw,
        zorder=zorder
    )
    ax.add_patch(box)
    return box


def draw_pill(ax, x, y, w, h, bg_color='#0078D4', border_color='none', radius=1.0, zorder=3):
    pill = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.05,rounding_size={radius}",
        facecolor=bg_color,
        edgecolor=border_color if border_color != 'none' else bg_color,
        linewidth=1.0,
        zorder=zorder
    )
    ax.add_patch(pill)
    return pill


def draw_arrow(ax, x1, y1, x2, y2, color='#0078D4', width=8, head_width=18, head_length=15, zorder=4):
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=f'simple,tail_width={width},head_width={head_width},head_length={head_length}',
        color=color,
        zorder=zorder
    )
    ax.add_patch(arrow)
    return arrow


# ==============================================================================
# FIGURE 1: Paper 1 Architecture & Setup
# ==============================================================================
def generate_figure_1(output_dir):
    fig, ax = plt.subplots(figsize=(15, 9.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Top Header
    ax.text(3, 94.5, "Figure 1: NetTwin Organization Twin — Offline Evaluation Core (Paper 1 Scope)",
            fontsize=17, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(3, 91.5, "Paper 1: 28 Years Elapsed [29 Years Inclusive] of Intrusion Detection — 30 Benchmarks (1998–2026)",
            fontsize=12, color='#444444', style='italic')
    ax.plot([3, 97], [90, 90], color=COLOR_BLUE_PRIMARY, lw=1.5)

    # Left Container: Enterprise Organization Network
    draw_box(ax, 3, 16, 33, 71, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    
    # Header inside Left Container
    draw_box(ax, 4.5, 78.5, 30, 7.5, bg_color='#EBF3FC', border_color=COLOR_BLUE_BORDER, lw=1.0, radius=1.2)
    ax.text(6, 82.8, "[ORG] Enterprise Organization Network", fontsize=12, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(6, 80.2, "Acme Global Cloud • vpc-prod-east", fontsize=10, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(6, 76.5, "10.0.0.0/16   •   12 Nodes   •   5 Tiers", fontsize=9.5, color=COLOR_TEXT_MUTED)

    # "Being Twinned" badge
    draw_pill(ax, 13.5, 71.5, 12, 3.2, bg_color='#EBF3FC', border_color=COLOR_BLUE_PRIMARY, radius=0.8)
    ax.text(19.5, 73.1, "Being Twinned", fontsize=9.5, fontweight='bold', color=COLOR_BLUE_PRIMARY, ha='center', va='center')

    # Topology lattice diagram (5 Tiers)
    tiers = [
        ("Tier 1: Edge / Gateway", "• 3 nodes", 64.5),
        ("Tier 2: Web / API", "• 3 nodes", 55.5),
        ("Tier 3: App / Service", "• 2 nodes", 46.5),
        ("Tier 4: Data / Storage", "• 2 nodes", 37.5),
        ("Tier 5: Security / Mgmt", "• 2 nodes", 28.5)
    ]
    
    # Diamond graph connections
    tier_y = [65.5, 56.5, 47.5, 38.5, 29.5]
    for i in range(len(tier_y) - 1):
        y_top = tier_y[i]
        y_bot = tier_y[i+1]
        ax.plot([10, 10], [y_top-1, y_bot+1], color='#B4D4F5', lw=1.2, zorder=2)
        ax.plot([10, 13], [y_top-1, y_bot+1], color='#B4D4F5', lw=1.2, zorder=2)
        ax.plot([13, 10], [y_top-1, y_bot+1], color='#B4D4F5', lw=1.2, zorder=2)
        ax.plot([13, 13], [y_top-1, y_bot+1], color='#B4D4F5', lw=1.2, zorder=2)

    for name, nodes, y_pos in tiers:
        draw_box(ax, 6.5, y_pos - 3, 26, 6, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.0)
        ax.plot([9.5, 11.5], [y_pos, y_pos], 'o', color=COLOR_BLUE_PRIMARY, markersize=5, zorder=3)
        ax.text(14, y_pos + 0.8, name, fontsize=10, fontweight='bold', color=COLOR_TEXT_MAIN)
        ax.text(14, y_pos - 1.5, nodes, fontsize=8.8, color=COLOR_TEXT_MUTED)

    # Center Transition: Onboarding Relation
    ax.text(50, 61, "Onboarding\nRelation", fontsize=15, fontweight='bold', color=COLOR_BLUE_DARK, ha='center', va='center')
    draw_arrow(ax, 38, 51.5, 62, 51.5, color=COLOR_BLUE_PRIMARY, width=6, head_width=16, head_length=14)
    ax.text(50, 44.5, "4 Modes • 5-Stage Synthesis • 99.4% Fidelity", fontsize=10, fontweight='bold', color=COLOR_TEXT_MAIN, ha='center')
    ax.text(50, 41.2, "Offline replay • Topology mapping", fontsize=9, color=COLOR_TEXT_MUTED, ha='center')
    ax.text(50, 38.2, "Traffic synthesis • Label projection", fontsize=9, color=COLOR_TEXT_MUTED, ha='center')

    # Right Container: NetTwin Engine LOCAL LAPTOP
    draw_box(ax, 64, 16, 33, 71, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    
    # Header inside Right Container
    draw_box(ax, 65.5, 78.5, 30, 7.5, bg_color='#EBF3FC', border_color=COLOR_BLUE_BORDER, lw=1.0, radius=1.2)
    ax.text(67, 82.8, "[HOST] NetTwin Engine LOCAL LAPTOP", fontsize=11.5, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(67, 80.2, "127.0.0.1:8000   •   OFFLINE SIMULATED Mode", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(67, 76.5, "• Stable & Standard", fontsize=9, fontweight='bold', color=COLOR_GREEN)

    # 5 Internal Stacked Components
    components = [
        ("DatasetCatalog", "9.21 GB", "vs ~65 GB full", 67.5, True),
        ("TwinState", "12 nodes mirrored • state synced • versioned snapshot", "", 57.5, False),
        ("Ensemble Detection", "Seasonal EMA + iForest + PCA SPE", "", 47.5, False),
        ("Conformal Calibrator", "alpha = 0.10 • Coverage 92.47%", "", 37.5, False),
        ("Page-Hinkley Drift", "Drift detection -> trigger re-calibration", "", 27.5, False)
    ]

    for title, desc, sub, y_pos, has_badge in components:
        draw_box(ax, 66, y_pos - 3.5, 29, 7.5, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
        ax.text(68, y_pos + 1.2, title, fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
        if has_badge:
            draw_pill(ax, 81.5, y_pos + 0.3, 5.5, 2.5, bg_color='#0078D4', radius=0.6)
            ax.text(84.25, y_pos + 1.5, desc, fontsize=8, fontweight='bold', color='#FFFFFF', ha='center', va='center')
            ax.text(88, y_pos + 1.2, sub, fontsize=8.5, color=COLOR_TEXT_MUTED)
        else:
            ax.text(68, y_pos - 1.5, desc, fontsize=8.8, color=COLOR_TEXT_MUTED)

    # Bottom Banner
    draw_box(ax, 3, 5.5, 94, 8.5, bg_color=COLOR_FOOTER, border_color='none', radius=1.5)
    ax.text(50, 10.8, "Output: Table A — 30 Datasets • 430,951 Records • 97.49% Detection • 92.47% Coverage",
            fontsize=12.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 7.5, "Benchmarks: DARPA 98 • KDD 99 • NSL-KDD • CIC-IDS2017 • CSE2018 • ... • ASEADOS-SDN-IoT 2026 (30 Benchmarks)",
            fontsize=9.5, color='#BFE0FF', ha='center')

    # Footer Subtext
    ax.text(50, 2.2, "All processing offline on local host. No external data egress. Deterministic, reproducible evaluation pipeline.",
            fontsize=9, color='#666666', ha='center')

    plt.tight_layout()
    png_path = os.path.join(output_dir, "fig1_0_org_twin_offline_evaluation_core.png")
    pdf_path = os.path.join(output_dir, "fig1_0_org_twin_offline_evaluation_core.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [+] Generated Fig 1.0: {png_path} & {pdf_path}")


# ==============================================================================
# FIGURE 2: Paper 2 Architecture & Setup
# ==============================================================================
def generate_figure_2(output_dir):
    fig, ax = plt.subplots(figsize=(15, 9.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Top Header
    ax.text(3, 94.5, "Figure 2: Dual-Region WAN Synchronization & Zero-Disk Streaming (Paper 2 Scope)",
            fontsize=17, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(3, 91.5, "Paper 2 — NetTwin: Zero-Disk Streaming Across 78ms WAN | NSDI / SIGCOMM",
            fontsize=12, color='#444444', style='italic')
    ax.plot([3, 97], [90, 90], color=COLOR_BLUE_PRIMARY, lw=1.5)

    # Top Left: vpc-traffic-west
    draw_box(ax, 5, 41, 30, 46, bg_color='#FFFFFF', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 5, 80, 30, 7, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(20, 83.5, "[CLOUD] vpc-traffic-west  10.1.0.0/16", fontsize=11, fontweight='bold', color='#FFFFFF', ha='center')
    
    ax.text(7.5, 76, "us-west-2", fontsize=11, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(7.5, 73, "Oregon - Adversary Company", fontsize=9.5, color=COLOR_TEXT_MUTED)

    draw_box(ax, 7, 44, 26, 26, bg_color='#F8FAFD', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(9, 66, "[SRC] traffic-gen t3.small", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(9, 62, "• Streams s3://cse-cic-ids2018/", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(9, 58.5, "• 450GB • 0MB • $0", fontsize=9.2, fontweight='bold', color=COLOR_BLUE_PRIMARY)
    ax.text(9, 55, "• via botocore.UNSIGNED", fontsize=9.2, color=COLOR_TEXT_MUTED)
    ax.text(9, 51.5, "[AUTH] HMAC-SHA256 Signed", fontsize=9.2, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(9, 48, "• 1450 eps at 5x", fontsize=9.2, color=COLOR_TEXT_MAIN)

    # Center: Public Internet WAN Latency
    ax.text(50, 70, "Public Internet", fontsize=16, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')
    ax.text(50, 66.5, "62–78ms WAN Latency • Real Enterprise WAN", fontsize=9.5, color=COLOR_TEXT_MAIN, ha='center')
    draw_arrow(ax, 37, 57, 63, 57, color=COLOR_BLUE_PRIMARY, width=8, head_width=20, head_length=16)
    ax.text(50, 50, "[LOCK] HMAC anti-replay 30s", fontsize=9.5, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')

    # Top Right: vpc-prod-east
    draw_box(ax, 65, 41, 30, 46, bg_color='#FFFFFF', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 65, 80, 30, 7, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(80, 83.5, "[CLOUD] vpc-prod-east  10.0.0.0/16", fontsize=11, fontweight='bold', color='#FFFFFF', ha='center')

    ax.text(67.5, 76, "us-east-1", fontsize=11, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(67.5, 73, "Virginia - Victim Company", fontsize=9.5, color=COLOR_TEXT_MUTED)

    draw_box(ax, 67, 44, 26, 26, bg_color='#F8FAFD', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(69, 66, "[WAF] ALB WAF COUNT mode", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(69, 62, "• web1/web2 t3.micro /health", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(69, 58.5, "• app1/app2", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(69, 55, "[RDS] db1 RDS Aurora", fontsize=9.2, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(69, 51.5, "• S3 VPCE $0 (PrivateLink Invariant)", fontsize=9.2, fontweight='bold', color=COLOR_GREEN)
    ax.text(69, 48, "• CloudWatch Poller 5s/10s", fontsize=9.2, color=COLOR_TEXT_MUTED)

    # Bottom Container: NetTwin Engine LOCAL LAPTOP HYBRID Mode
    draw_box(ax, 5, 11, 90, 26, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    ax.text(8, 32.5, "[HOST] NetTwin Engine — LOCAL LAPTOP HYBRID Mode", fontsize=13, fontweight='bold', color=COLOR_BLUE_DARK)

    # 3 Internal sub-columns
    # Col 1: SyncEngine
    draw_box(ax, 7, 18, 26, 12, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(9, 26.5, "SyncEngine:", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(9, 22.5, "SIMULATED → SHADOW → HYBRID", fontsize=9.2, fontweight='bold', color=COLOR_BLUE_PRIMARY)

    # Col 2: Fidelity
    draw_box(ax, 35, 18, 29, 12, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(37, 26.5, "Fidelity:", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(37, 23.2, "RMSE 3.2% benign • 4.1% DDoS 5x", fontsize=9, color=COLOR_TEXT_MAIN)
    ax.text(37, 20.2, "Pearson r 0.98", fontsize=9, fontweight='bold', color=COLOR_GREEN)

    # Col 3: Staleness & Ingestion
    draw_box(ax, 66, 18, 27, 12, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(68, 26.5, "Staleness: 8s Reversion", fontsize=9.8, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(68, 23.5, "Ingestion: HMAC + mTLS FP + Whitelist", fontsize=8.5, color=COLOR_TEXT_MUTED)
    ax.text(68, 20.5, "Zero-Disk Assertion: 0 MB", fontsize=9, fontweight='bold', color=COLOR_GREEN)

    # Centered Synchronized badge
    draw_pill(ax, 41, 13, 18, 3.8, bg_color=COLOR_BLUE_PRIMARY, radius=1.0)
    ax.text(50, 14.9, "[OK] SYNCHRONIZED", fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')

    # Caption
    ax.text(50, 4.5, "Paper 2 — NetTwin: Zero-Disk Streaming Across 78ms WAN | NSDI / SIGCOMM",
            fontsize=10.5, color='#444444', ha='center', style='italic')

    plt.tight_layout()
    png_path = os.path.join(output_dir, "fig2_0_dual_region_wan_sync_zero_disk.png")
    pdf_path = os.path.join(output_dir, "fig2_0_dual_region_wan_sync_zero_disk.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [+] Generated Fig 2.0: {png_path} & {pdf_path}")


# ==============================================================================
# FIGURE 3: Paper 3 Architecture & Setup
# ==============================================================================
def generate_figure_3(output_dir):
    fig, ax = plt.subplots(figsize=(15, 9.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Top Header
    ax.text(3, 94.5, "Figure 3: IoT/5G Generalization Across 12 Next-Gen Datasets (Paper 3 Scope)",
            fontsize=17, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(3, 91.5, "Paper 3: Edge-IIoTset to CIC IoT 2024 Generalization — IEEE IoT Journal",
            fontsize=12, color='#444444', style='italic')
    ax.plot([3, 97], [90, 90], color=COLOR_BLUE_PRIMARY, lw=1.5)

    # 3-Column Layout
    # Column 1: Organization IoT Tier
    draw_box(ax, 3, 17, 28, 70, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 3, 80.5, 28, 6.5, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(17, 83.7, "[IOT] ORGANIZATION IOT TIER", fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center')
    
    ax.text(5.5, 76.5, "10.0.5.0/24", fontsize=11, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(5.5, 73.5, "Edge & IoT Subnet", fontsize=9.5, color=COLOR_TEXT_MUTED)

    iot_nodes = [
        ("iot1 • Smart Sensor", "Environmental, Motion, Thermal\n• Data Collection", 64),
        ("iot-gw • IoT Gateway", "Protocol Bridge: MQTT/Zigbee/Matter\n• Edge Ingestion", 52),
        ("ws1 • Bastion Host", "Secure Access / SSH Jumpbox\n• Admin Control", 40),
        ("s3 • Lakehouse Sink", "Immutable Storage\n• Raw Data Reservoir", 28)
    ]
    for title, desc, y_pos in iot_nodes:
        draw_box(ax, 4.5, y_pos - 4, 25, 9, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
        ax.text(6, y_pos + 2.5, title, fontsize=9.8, fontweight='bold', color=COLOR_TEXT_MAIN)
        ax.text(6, y_pos - 1.2, desc, fontsize=8.2, color=COLOR_TEXT_MUTED)

    draw_pill(ax, 6.5, 19.5, 21, 3.2, bg_color='#EBF3FC', border_color=COLOR_BLUE_PRIMARY, radius=0.8)
    ax.text(17, 21.1, "Subnet: 10.0.5.0/24 | Edge Layer", fontsize=8.5, fontweight='bold', color=COLOR_BLUE_PRIMARY, ha='center', va='center')

    # Column 2: NetTwin Engine LOCAL OFFLINE IoT Profiling
    draw_box(ax, 33, 17, 34, 70, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 33, 80.5, 34, 6.5, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(50, 83.7, "[TWIN] NETTWIN ENGINE LOCAL OFFLINE", fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center')
    
    ax.text(35, 76.5, "IoT Device Profiling", fontsize=11, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(35, 72.8, "12 Next-Gen Datasets Evaluated:", fontsize=9.5, fontweight='bold', color=COLOR_BLUE_DARK)

    # 12 Dataset pills grid
    datasets_12 = [
        ("ToN_IoT", 35, 66), ("Bot-IoT", 43, 66), ("MQTT-IoT", 51, 66), ("Edge-IIoTset", 59, 66),
        ("CIC IoT 2022", 35, 60), ("CIC IoT 2023", 43.5, 60), ("CIC IoT 2024", 52, 60), ("MalMem2022", 60.5, 60),
        ("HIKARI", 35, 54), ("5G-NIDD", 43, 54), ("EIoT2025", 51, 54), ("Darknet", 59, 54)
    ]
    for dname, dx, dy in datasets_12:
        draw_pill(ax, dx, dy, 7.5, 3.8, bg_color='#E0EDFA', border_color=COLOR_BLUE_PRIMARY, radius=0.6)
        ax.text(dx + 3.75, dy + 1.9, dname, fontsize=7.2, fontweight='bold', color=COLOR_BLUE_DARK, ha='center', va='center')

    # Sub-info cards in Center column
    draw_box(ax, 35, 41, 30, 9, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(36.5, 46.5, "[DS] 212.7MB staged vs 35GB full", fontsize=9.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(36.5, 43.2, "Staged subset for generalization experiments", fontsize=8.5, color=COLOR_TEXT_MUTED)

    draw_box(ax, 35, 30, 30, 9, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(36.5, 35.5, "[PART] Stratified Partitions", fontsize=9.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(36.5, 32.2, "25k–157k flows per dataset • Class-balanced", fontsize=8.5, color=COLOR_TEXT_MUTED)

    draw_box(ax, 35, 19, 30, 9, bg_color='#FFFFFF', border_color=COLOR_GREEN, lw=1.0, radius=1.2)
    ax.text(36.5, 24.5, "[SAFE] Processing: Offline", fontsize=9.5, fontweight='bold', color=COLOR_GREEN)
    ax.text(36.5, 21.2, "Zero external network egress or leak", fontsize=8.5, color=COLOR_TEXT_MUTED)

    # Column 3: Cross-Evaluation Matrix
    draw_box(ax, 69, 17, 28, 70, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 69, 80.5, 28, 6.5, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(83, 83.7, "[EVAL] CROSS-EVALUATION MATRIX", fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center')

    ax.text(71, 76.5, "Generalization Evaluation", fontsize=11, fontweight='bold', color=COLOR_TEXT_MAIN)

    # Train / Test Flow
    draw_box(ax, 71, 67, 24, 7.5, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(83, 71.8, "TRAIN: Edge-IIoTset 2022", fontsize=9.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(83, 69, "Source Domain • Feature Dist D2022", fontsize=7.8, color='#BFE0FF', ha='center')

    draw_arrow(ax, 83, 66, 83, 60, color=COLOR_BLUE_PRIMARY, width=4, head_width=12, head_length=10)
    ax.text(83, 62.5, "Cross-Domain Evaluation", fontsize=8, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')

    draw_box(ax, 71, 51.5, 24, 8, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(83, 56.5, "TEST: CIC IoT 2024", fontsize=9.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(83, 53.5, "• Matter Attacks • Zigbee • MQTT", fontsize=8, color='#BFE0FF', ha='center')

    # Results cards
    # Baseline
    draw_box(ax, 71, 38.5, 24, 10.5, bg_color=COLOR_YELLOW_LIGHT, border_color=COLOR_YELLOW_BORDER, lw=1.2, radius=1.2)
    ax.text(72.5, 46, "Baseline (In-Domain):", fontsize=9, color='#665500')
    ax.text(72.5, 42.5, "98.9% [OK]", fontsize=13.5, fontweight='bold', color=COLOR_GREEN)
    ax.text(72.5, 39.8, "F1-Score on Edge-IIoTset 2022", fontsize=8, color=COLOR_TEXT_MUTED)

    # Generalized
    draw_box(ax, 71, 26, 24, 10.5, bg_color=COLOR_RED_LIGHT, border_color=COLOR_RED, lw=1.2, radius=1.2)
    ax.text(72.5, 33.5, "Generalized (Out-of-Domain):", fontsize=9, color=COLOR_RED)
    ax.text(72.5, 30, "84.2% [DROP]", fontsize=13.5, fontweight='bold', color=COLOR_RED)
    ax.text(72.5, 27.2, "F1-Score on CIC IoT 2024", fontsize=8, color=COLOR_TEXT_MUTED)

    # Gap
    draw_box(ax, 71, 18.5, 24, 6, bg_color=COLOR_BLUE_DARK, border_color='none', radius=1.0)
    ax.text(83, 22.2, "Generalization Gap: -14.7 pp", fontsize=9.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(83, 19.8, "Delta = 98.9% -> 84.2%", fontsize=8.5, color='#BFE0FF', ha='center')

    # Bottom Objective Banner
    draw_box(ax, 3, 5.5, 94, 8.5, bg_color=COLOR_FOOTER, border_color='none', radius=1.5)
    ax.text(50, 10.8, "Core Objective: Does model trained on 2022 IoT generalize to 2024 Matter protocol? — MQTT vs RTSP vs Zigbee vs Matter Spoof",
            fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 7.5, "Key Question: Evaluating cross-protocol, cross-temporal, cross-dataset generalization for next-gen IoT/5G security models",
            fontsize=9.2, color='#BFE0FF', ha='center')

    # Caption
    ax.text(50, 2.2, "Figure 3 | Workflow for cross-dataset generalization evaluation between Edge-IIoTset (2022) and CIC IoT 2024",
            fontsize=9.5, color='#444444', ha='center', style='italic')

    plt.tight_layout()
    png_path = os.path.join(output_dir, "fig3_0_iot_generalization_12_datasets.png")
    pdf_path = os.path.join(output_dir, "fig3_0_iot_generalization_12_datasets.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [+] Generated Fig 3.0: {png_path} & {pdf_path}")


# ==============================================================================
# FIGURE 4: Paper 4 Architecture & Setup
# ==============================================================================
def generate_figure_4(output_dir):
    fig, ax = plt.subplots(figsize=(15, 9.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Top Header
    ax.text(3, 94.5, "Figure 4: Closed-Loop Safe Autonomous Response (Paper 4 Scope)",
            fontsize=17, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(3, 91.5, "Sandbox-Gated Thompson Sampling Safe Autonomous Response — ACM CCS/NDSS",
            fontsize=12, color='#444444', style='italic')
    ax.plot([3, 97], [90, 90], color=COLOR_BLUE_PRIMARY, lw=1.5)

    # Top Left: WEST Traffic Adversary
    draw_box(ax, 3, 44, 25, 43, bg_color=COLOR_RED_LIGHT, border_color=COLOR_RED, lw=1.6, radius=1.8)
    ax.text(5, 83.5, "[ADV] WEST Traffic Adversary", fontsize=11.5, fontweight='bold', color=COLOR_RED)
    ax.text(6, 75, "• ddos_alb 5x (Floods)", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(6, 68, "• sqli_db1 (SQL Injections)", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(6, 61, "• iot_botnet (Mirai Incursions)", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)

    ax.text(15.5, 52, "Malicious Traffic", fontsize=11, fontweight='bold', color=COLOR_RED, ha='center')
    draw_arrow(ax, 5, 47.5, 26, 47.5, color=COLOR_RED, width=4, head_width=12, head_length=10)

    # Top Center: EAST — Prod VPC
    draw_box(ax, 30, 44, 40, 43, bg_color='#F0F6FD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    ax.text(50, 83.5, "EAST — Prod VPC  (vpc-prod-east 10.0.0.0/16)", fontsize=12, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')
    
    # ALB block
    draw_box(ax, 35, 67, 30, 12, bg_color='#FFFFFF', border_color=COLOR_BLUE_BORDER, lw=1.2, radius=1.2)
    ax.text(37, 75.5, "[ALB] Application Load Balancer", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(37, 70.5, "ALB 82.2 health -> 76.3 drop [Delta 5.9]", fontsize=9.5, fontweight='bold', color=COLOR_RED)

    # Backend Instances (web1, web2)
    draw_box(ax, 33, 47.5, 16, 15.5, bg_color='#EBF8EE', border_color=COLOR_GREEN, lw=1.2, radius=1.2)
    ax.text(35, 59, "[SRV] web1 [OK]", fontsize=10.5, fontweight='bold', color=COLOR_GREEN)
    ax.text(35, 53.5, "Backend Instances\nt3.micro /health", fontsize=8.2, color=COLOR_TEXT_MUTED)

    draw_box(ax, 52, 47.5, 16, 15.5, bg_color='#EBF8EE', border_color=COLOR_GREEN, lw=1.2, radius=1.2)
    ax.text(54, 59, "[SRV] web2 [OK]", fontsize=10.5, fontweight='bold', color=COLOR_GREEN)
    ax.text(54, 53.5, "Backend Instances\nt3.micro /health", fontsize=8.2, color=COLOR_TEXT_MUTED)

    # Top Right: Safety & Safeguards
    draw_box(ax, 72, 44, 25, 43, bg_color=COLOR_GREEN_LIGHT, border_color=COLOR_GREEN, lw=1.6, radius=1.8)
    ax.text(74, 83.5, "[SAFE] Safety & Safeguards", fontsize=11.5, fontweight='bold', color=COLOR_GREEN)
    
    safeguards = [
        ("• dry_run=true default", 76),
        ("• Protected CIDR whitelist", 70),
        ("• Core Infra Protection", 64),
        ("• Kill Switch: POST /disable 1ms", 57),
        ("• RRI 0.928–1.0 Recovery", 50)
    ]
    for text, y_pos in safeguards:
        ax.text(74, y_pos, text, fontsize=9.2, fontweight='bold', color=COLOR_TEXT_MAIN)

    # Bottom Section: Closed-Loop Control Loop (<10ms Actuation)
    # Sidecar box
    draw_box(ax, 3, 10, 16, 29, bg_color='#F0F6FD', border_color=COLOR_BLUE_PRIMARY, lw=1.6, radius=1.5)
    ax.text(11, 34.5, "[SIDECAR] NetTwin", fontsize=10.5, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')
    ax.text(11, 28, "t3.micro — Inside VPC\nfor <10ms Actuation", fontsize=8.5, color=COLOR_TEXT_MAIN, ha='center')
    draw_pill(ax, 4.5, 14, 13, 7, bg_color=COLOR_BLUE_PRIMARY, radius=0.8)
    ax.text(11, 18, "Closed-Loop\n<10ms Actuation", fontsize=8.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')

    # 5 Sequential Pipeline Stages
    stages = [
        ("1. Detector", "triggers anomaly\nSPE 0.984", 21, False),
        ("2. Thompson Sampling", "proposes action:\n• rate_limit\n• isolate_node\n• ACL_block", 36, False),
        ("3. Sandbox Gate", "clones Twin state\n• 15-tick forecast\n• checks Delta Health\n• if Delta < 0 -> DROP", 51, False),
        ("4. AWSActuator", "SG revoke ingress\n+ NACL DENY rule\nvia boto3 API", 67, False),
        ("5. ActuationBridge", "verifies recovery\nHealth -> 99.2%\nRRI = 0.962", 83, True)
    ]

    for title, desc, x_pos, is_green in stages:
        bg = COLOR_GREEN_LIGHT if is_green else '#FFFFFF'
        border = COLOR_GREEN if is_green else COLOR_BLUE_BORDER
        tcolor = COLOR_GREEN if is_green else COLOR_BLUE_DARK
        draw_box(ax, x_pos, 13, 13.5, 23, bg_color=bg, border_color=border, lw=1.3, radius=1.2)
        ax.text(x_pos + 6.75, 32.5, title, fontsize=9.2, fontweight='bold', color=tcolor, ha='center')
        ax.text(x_pos + 1.2, 23, desc, fontsize=8, color=COLOR_TEXT_MAIN)

    # Arrows between stages
    draw_arrow(ax, 34.7, 24.5, 35.8, 24.5, color=COLOR_BLUE_PRIMARY, width=3, head_width=9, head_length=8)
    draw_arrow(ax, 49.7, 24.5, 50.8, 24.5, color=COLOR_BLUE_PRIMARY, width=3, head_width=9, head_length=8)
    draw_arrow(ax, 64.7, 24.5, 66.8, 24.5, color=COLOR_BLUE_PRIMARY, width=3, head_width=9, head_length=8)
    draw_arrow(ax, 80.7, 24.5, 82.8, 24.5, color=COLOR_GREEN, width=3, head_width=9, head_length=8)

    # Subtext right
    ax.text(50, 7.5, "Safe Execution Guarantees: All remediation actions strictly gated by sandbox twin simulation prior to live AWS production mutation",
            fontsize=9.2, fontweight='bold', color=COLOR_TEXT_MAIN, ha='center')

    # Legend
    ax.text(50, 2.5, "Legend:  [Red] = Attack / Threat     [Blue] = NetTwin / Sandbox Simulation     [Green] = Safe / Recovery Verified",
            fontsize=9.5, fontweight='bold', color=COLOR_TEXT_MUTED, ha='center')

    plt.tight_layout()
    png_path = os.path.join(output_dir, "fig4_0_architecture_closed_loop_safe_response.png")
    pdf_path = os.path.join(output_dir, "fig4_0_architecture_closed_loop_safe_response.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [+] Generated Fig 4.0: {png_path} & {pdf_path}")


# ==============================================================================
# FIGURE 5: Paper 5 Architecture & Setup
# ==============================================================================
def generate_figure_5(output_dir):
    fig, ax = plt.subplots(figsize=(15, 9.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Top Header
    ax.text(3, 94.5, "Figure 5: Conformal LLM SOC Analyst — Air-Gapped Privacy (Paper 5 Scope)",
            fontsize=17, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(3, 91.5, "When LLMs Meet Conformal Prediction — Uncertainty-Aware SOC — IEEE TIFS/TNSM",
            fontsize=12, color='#444444', style='italic')
    ax.plot([3, 97], [90, 90], color=COLOR_BLUE_PRIMARY, lw=1.5)

    # Left Box: Organization Twin (width 21: x from 3 to 24)
    draw_box(ax, 3, 17, 21, 70, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 3, 80.5, 21, 6.5, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(13.5, 83.7, "[TWIN] Organization Twin", fontsize=10.2, fontweight='bold', color='#FFFFFF', ha='center')

    ax.text(4.5, 76, "Acme Global Cloud", fontsize=10.5, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(4.5, 72.8, "vpc-07b94a12ec8", fontsize=9, color=COLOR_TEXT_MUTED)

    draw_pill(ax, 4.5, 66.5, 14, 3.8, bg_color='#EBF3FC', border_color=COLOR_BLUE_PRIMARY, radius=0.8)
    ax.text(11.5, 68.3, "SYNCHRONIZED", fontsize=8.8, fontweight='bold', color=COLOR_BLUE_PRIMARY, ha='center', va='center')

    ax.text(4.5, 59.5, "Scoped Telemetry:", fontsize=10, fontweight='bold', color=COLOR_BLUE_DARK)
    ax.text(5.5, 54, "• health metrics", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(5.5, 48.5, "• aggregate KPIs", fontsize=9.2, color=COLOR_TEXT_MAIN)
    ax.text(5.5, 43, "• anomaly scores", fontsize=9.2, color=COLOR_TEXT_MAIN)

    draw_box(ax, 4.2, 20, 18.5, 17, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
    ax.text(5, 32.5, "Privacy Invariant:", fontsize=8.8, fontweight='bold', color=COLOR_GREEN)
    ax.text(5, 25, "Aggregated counters only.\nNo customer PII or raw\npayloads egress cloud.", fontsize=7.8, color=COLOR_TEXT_MUTED)

    # Arrow Left to Center (gap from 24 to 28)
    ax.text(26.2, 54.5, "Secure Sync", fontsize=8.2, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')
    draw_arrow(ax, 24.3, 51, 28, 51, color=COLOR_BLUE_PRIMARY, width=3.5, head_width=10, head_length=8)

    # Center Box: NetTwin Engine LOCAL LAPTOP Air-Gapped (width 42: x from 28.5 to 70.5)
    draw_box(ax, 28.5, 17, 42, 70, bg_color='#F8FAFD', border_color=COLOR_BLUE_PRIMARY, lw=1.8, radius=2.0)
    draw_box(ax, 28.5, 79, 42, 8, bg_color=COLOR_BLUE_PRIMARY, border_color='none', radius=1.0)
    ax.text(49.5, 84, "[ENGINE] NetTwin Engine LOCAL LAPTOP", fontsize=11, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(49.5, 80.5, "Air-Gapped — No Internet Privacy Guaranteed", fontsize=9.2, color='#BFE0FF', ha='center')

    ax.text(49.5, 75.2, "Fully air-gapped; no external network connectivity; all processing on device",
            fontsize=8.2, color=COLOR_TEXT_MUTED, ha='center')

    # 4 Components
    center_components = [
        ("SubspaceDetector", "conformal score 0.984 • p < 0.003 • conf 99.7%", "p < 0.003 [OK]", 66),
        ("SecurityAnalyst", "gathers context <6000 chars\n• live health + top anomaly + alerts + drills", "", 55),
        ("MITRE ATT&CK STIX Vector DB RAG", "cosine similarity for relevant ATT&CK techniques", "", 44),
        ("OllamaProvider (llama3.2)", "127.0.0.1:11434 — local daemon\nTTL 30s cache • non-blocking inference", "", 33)
    ]
    for title, desc, badge, y_pos in center_components:
        draw_box(ax, 30.5, y_pos - 4, 38, 9.5, bg_color='#FFFFFF', border_color='#C7DDF7', lw=1.0, radius=1.2)
        ax.text(32, y_pos + 3.2, title, fontsize=9.5, fontweight='bold', color=COLOR_TEXT_MAIN)
        ax.text(32, y_pos - 1.5, desc, fontsize=8.2, color=COLOR_TEXT_MUTED)
        if badge:
            draw_pill(ax, 54.5, y_pos + 2, 13, 2.8, bg_color=COLOR_BLUE_PRIMARY, radius=0.6)
            ax.text(61, y_pos + 3.4, badge, fontsize=7.2, fontweight='bold', color='#FFFFFF', ha='center', va='center')

    # Three-Tier Fail-Safe Box
    draw_box(ax, 30.5, 19, 38, 8.5, bg_color=COLOR_YELLOW_LIGHT, border_color=COLOR_YELLOW_BORDER, lw=1.2, radius=1.0)
    ax.text(32, 24.8, "[FAIL-SAFE] Three-Tier Fail-Safe Reasoning Engine:", fontsize=8.5, fontweight='bold', color='#665500')
    ax.text(32, 21.2, "Ollama LLM (primary) -> Bedrock (fallback) -> RuleBasedAnalyst (<1ms)", fontsize=7.8, fontweight='bold', color=COLOR_TEXT_MAIN)

    # Arrow Center to Right (gap from 70.5 to 74.5)
    ax.text(72.7, 54.5, "Grounded Output", fontsize=8.2, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')
    draw_arrow(ax, 70.8, 51, 74.3, 51, color=COLOR_BLUE_PRIMARY, width=3.5, head_width=10, head_length=8)

    # Right Box: AI Analyst Output (width 22.5: x from 74.5 to 97)
    draw_box(ax, 74.5, 17, 22.5, 70, bg_color='#F8FAFD', border_color=COLOR_GREEN, lw=1.8, radius=2.0)
    draw_box(ax, 74.5, 80.5, 22.5, 6.5, bg_color=COLOR_GREEN, border_color='none', radius=1.0)
    ax.text(85.7, 83.7, "[OUTPUT] AI Analyst Output", fontsize=10.2, fontweight='bold', color='#FFFFFF', ha='center')

    # Before Card (Hallucination)
    draw_box(ax, 75.8, 59, 20, 18, bg_color=COLOR_RED_LIGHT, border_color=COLOR_RED, lw=1.2, radius=1.2)
    ax.text(77, 73, "[!] Before — hallucination", fontsize=9, fontweight='bold', color=COLOR_RED)
    ax.text(77, 68.5, "maybe DDoS", fontsize=10.2, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(77, 64.5, "Uncertainty: unknown\nLow confidence\n• No evidence", fontsize=7.8, color=COLOR_TEXT_MUTED)

    # Filter Arrow Down
    draw_arrow(ax, 85.8, 58, 85.8, 52.5, color=COLOR_BLUE_PRIMARY, width=3, head_width=9, head_length=8)
    ax.text(85.8, 54.5, "Conformal Filtering", fontsize=7.5, fontweight='bold', color=COLOR_BLUE_DARK, ha='center')

    # After Card (Grounded)
    draw_box(ax, 75.8, 25, 20, 26, bg_color=COLOR_GREEN_LIGHT, border_color=COLOR_GREEN, lw=1.2, radius=1.2)
    ax.text(77, 47.5, "[OK] After — grounded:", fontsize=9.2, fontweight='bold', color=COLOR_GREEN)
    ax.text(77, 43.5, "DDoS — LOIC UDP on alb", fontsize=9.2, fontweight='bold', color=COLOR_TEXT_MAIN)
    ax.text(77, 34, "• conformal 0.984\n• p < 0.003\n• 99.7% confidence\n• MITRE T1498 UDP Flood\n• Rec: WAF rate-limit alb", fontsize=7.8, color=COLOR_TEXT_MAIN)

    draw_pill(ax, 76.5, 19, 18.5, 4, bg_color=COLOR_GREEN, radius=0.8)
    ax.text(85.8, 21, "[OK] Stops Hallucination", fontsize=8.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')

    # Bottom Objective Banner
    draw_box(ax, 3, 5.5, 94, 8.5, bg_color=COLOR_FOOTER, border_color='none', radius=1.5)
    ax.text(50, 10.8, "Core Objective: Uncertainty-aware SOC — Conformal p-value grounds LLM answer — Telemetry never leaves laptop",
            fontsize=10.5, fontweight='bold', color='#FFFFFF', ha='center')
    ax.text(50, 7.5, "• All data retained locally • Air-gapped • Privacy-by-design • Reproducible & auditable results",
            fontsize=9.2, color='#BFE0FF', ha='center')

    # Legend
    ax.text(50, 2.5, "Legend:  [Blue] = System Component    [Green] = Grounded Output    [Yellow] = Fail-Safe Engine    [Privacy] = Air-Gapped",
            fontsize=9.5, fontweight='bold', color=COLOR_TEXT_MUTED, ha='center')

    plt.tight_layout()
    png_path = os.path.join(output_dir, "fig5_0_conformal_llm_soc_analyst_airgapped.png")
    pdf_path = os.path.join(output_dir, "fig5_0_conformal_llm_soc_analyst_airgapped.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  [+] Generated Fig 5.0: {png_path} & {pdf_path}")


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    papers_dir = os.path.join(root, 'papers')
    
    print("=" * 70)
    print("Generating Architectural Diagrams for all 5 NetTwin 3.0 Papers...")
    print("=" * 70)

    # 1. Paper 1
    p1_dir = os.path.join(papers_dir, 'paper1_usenix_sec_30datasets', 'figures')
    os.makedirs(p1_dir, exist_ok=True)
    generate_figure_1(p1_dir)

    # 2. Paper 2
    p2_dir = os.path.join(papers_dir, 'paper2_nsdi_zerodisk_sync', 'figures')
    os.makedirs(p2_dir, exist_ok=True)
    generate_figure_2(p2_dir)

    # 3. Paper 3
    p3_dir = os.path.join(papers_dir, 'paper3_ieee_iot_generalization', 'figures')
    os.makedirs(p3_dir, exist_ok=True)
    generate_figure_3(p3_dir)

    # 4. Paper 4
    p4_dir = os.path.join(papers_dir, 'paper4_ccs_safe_autonomous_response', 'figures')
    os.makedirs(p4_dir, exist_ok=True)
    generate_figure_4(p4_dir)

    # 5. Paper 5
    p5_dir = os.path.join(papers_dir, 'paper5_tifs_conformal_llm_soc', 'figures')
    os.makedirs(p5_dir, exist_ok=True)
    generate_figure_5(p5_dir)

    print("=" * 70)
    print("SUCCESS: All 5 Architecture & Setup Figures generated!")
    print("=" * 70)


if __name__ == '__main__':
    main()
