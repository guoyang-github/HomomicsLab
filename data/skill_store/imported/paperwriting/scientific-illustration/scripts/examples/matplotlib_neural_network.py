#!/usr/bin/env python3
"""
Neural network layer diagram using Matplotlib.

Demonstrates: Circle patches for nodes, nested loops for dense connections,
layered layout with consistent spacing, and vector export.

Install: pip install matplotlib numpy
Run: python matplotlib_neural_network.py
Output: neural_network.pdf, neural_network.png
"""

import matplotlib.pyplot as plt
import numpy as np


def draw_layer(ax, x, n_nodes, label, color):
    y_positions = np.linspace(0.5, 4.5, n_nodes)
    for y in y_positions:
        circle = plt.Circle((x, y), 0.18, color=color, ec='black', linewidth=1)
        ax.add_patch(circle)
    ax.text(x, -0.3, label, ha='center', va='top', fontsize=10, fontweight='bold')
    return y_positions


def draw_connections(ax, x1, y1_list, x2, y2_list, alpha=0.3):
    for y1 in y1_list:
        for y2 in y2_list:
            ax.plot([x1, x2], [y1, y2], 'k-', alpha=alpha, linewidth=0.5)


def main():
    fig, ax = plt.subplots(figsize=(8, 5))

    # Draw layers
    input_y = draw_layer(ax, 1, 4, 'Input\n(784)', '#E69F00')
    hidden_y = draw_layer(ax, 3.5, 6, 'Hidden\n(128)', '#56B4E9')
    output_y = draw_layer(ax, 6, 3, 'Output\n(10)', '#009E73')

    # Draw connections
    draw_connections(ax, 1, input_y, 3.5, hidden_y)
    draw_connections(ax, 3.5, hidden_y, 6, output_y)

    ax.set_xlim(-0.5, 7)
    ax.set_ylim(-1, 5.5)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('Neural Network Architecture', fontsize=13, fontweight='bold', pad=10)
    plt.tight_layout()
    plt.savefig('neural_network.pdf', bbox_inches='tight')
    plt.savefig('neural_network.png', bbox_inches='tight', dpi=300)
    print("Saved: neural_network.pdf, neural_network.png")


if __name__ == '__main__':
    main()
