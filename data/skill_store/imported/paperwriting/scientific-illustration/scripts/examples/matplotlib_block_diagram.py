#!/usr/bin/env python3
"""
System block diagram using Matplotlib.

Demonstrates: FancyBboxPatch for rounded boxes, FancyArrowPatch for labeled
connections, custom color palette, and dual-format export (PDF + PNG).

Install: pip install matplotlib
Run: python matplotlib_block_diagram.py
Output: iot_block_diagram.pdf, iot_block_diagram.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


# Okabe-Ito colorblind-friendly palette
COLORS = {
    'sensor': '#E69F00',      # orange
    'processor': '#56B4E9',   # sky blue
    'cloud': '#009E73',       # green
    'user': '#CC79A7',        # pink
}


def draw_box(ax, x, y, w, h, label, color, fontsize=11):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.2",
        facecolor=color, edgecolor='black', linewidth=1.2
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, label,
        ha='center', va='center',
        fontsize=fontsize, fontweight='bold', color='white'
    )


def draw_arrow(ax, start, end, label=None):
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle='->', mutation_scale=20,
        linewidth=1.5, color='#333333'
    )
    ax.add_patch(arrow)
    if label:
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(
            mid[0], mid[1] + 0.25, label,
            ha='center', va='bottom',
            fontsize=9, style='italic', color='#555555'
        )


def main():
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')

    # Draw boxes
    draw_box(ax, 0.5, 1.2, 1.8, 1.2, 'Sensors', COLORS['sensor'])
    draw_box(ax, 3.0, 1.2, 2.0, 1.2, 'ESP32\nMicrocontroller', COLORS['processor'])
    draw_box(ax, 5.8, 1.2, 1.8, 1.2, 'Cloud\nServer', COLORS['cloud'])
    draw_box(ax, 8.2, 1.2, 1.5, 1.2, 'Mobile\nApp', COLORS['user'])

    # Draw arrows
    draw_arrow(ax, (2.3, 1.8), (3.0, 1.8), 'I2C/UART')
    draw_arrow(ax, (5.0, 1.8), (5.8, 1.8), 'WiFi/HTTPS')
    draw_arrow(ax, (7.6, 1.8), (8.2, 1.8), 'REST API')

    ax.set_title('IoT System Architecture', fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig('iot_block_diagram.pdf', bbox_inches='tight', dpi=300)
    plt.savefig('iot_block_diagram.png', bbox_inches='tight', dpi=300)
    print("Saved: iot_block_diagram.pdf, iot_block_diagram.png")


if __name__ == '__main__':
    main()
