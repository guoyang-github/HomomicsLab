#!/usr/bin/env python3
"""
MAPK signaling pathway using NetworkX.

Demonstrates: Linear signaling cascade with edge labels,
membrane boundary line, different node shapes (circles vs squares),
and publication-quality export.

Install: pip install networkx matplotlib
Run: python networkx_pathway.py
Output: mapk_pathway.pdf, mapk_pathway.png
"""

import matplotlib.pyplot as plt
import networkx as nx


def main():
    fig, ax = plt.subplots(figsize=(10, 6))
    G = nx.DiGraph()

    # Nodes with positions
    pathway_nodes = {
        'egfr': (0.5, 3, 'EGFR'),
        'ras': (2.5, 3, 'RAS\n(GTP-bound)'),
        'raf': (4.5, 3, 'RAF'),
        'mek': (6.5, 3, 'MEK'),
        'erk': (8.5, 3, 'ERK'),
        'nucleus': (10, 3, 'Gene\nTranscription'),
    }

    for key, (x, y, label) in pathway_nodes.items():
        G.add_node(key, pos=(x, y), label=label)

    edges = [
        ('egfr', 'ras'), ('ras', 'raf'), ('raf', 'mek'),
        ('mek', 'erk'), ('erk', 'nucleus')
    ]
    G.add_edges_from(edges)

    pos = nx.get_node_attributes(G, 'pos')
    labels = nx.get_node_attributes(G, 'label')

    # Membrane boundary line
    ax.axhline(y=3.5, xmin=0.02, xmax=0.15, color='#D4A574', linewidth=4)
    ax.text(0.5, 3.9, 'Cell Membrane', ha='center', va='bottom',
            fontsize=9, style='italic')

    # Draw pathway nodes (circles)
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=['egfr', 'ras', 'raf', 'mek', 'erk'],
        node_shape='o', node_color='#56B4E9',
        node_size=3500, edgecolors='black', linewidths=1.5, ax=ax
    )
    # Nucleus (square)
    nx.draw_networkx_nodes(
        G, pos, nodelist=['nucleus'],
        node_shape='s', node_color='#E69F00',
        node_size=4000, edgecolors='black', linewidths=1.5, ax=ax
    )

    # Edges with phosphorylation labels
    nx.draw_networkx_edges(
        G, pos, edge_color='#333333', arrows=True,
        arrowsize=20, arrowstyle='->', width=2, ax=ax
    )
    edge_labels = {
        ('egfr', 'ras'): 'P', ('ras', 'raf'): 'P',
        ('raf', 'mek'): 'P', ('mek', 'erk'): 'P',
        ('erk', 'nucleus'): 'activation'
    }
    nx.draw_networkx_edge_labels(
        G, pos, edge_labels, font_size=9,
        font_color='#D55E00', font_weight='bold', ax=ax
    )

    nx.draw_networkx_labels(
        G, pos, labels, font_size=10, font_weight='bold', ax=ax
    )

    ax.set_title('MAPK Signaling Pathway', fontsize=14, fontweight='bold')
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(2, 4.5)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig('mapk_pathway.pdf', bbox_inches='tight')
    plt.savefig('mapk_pathway.png', bbox_inches='tight', dpi=300)
    print("Saved: mapk_pathway.pdf, mapk_pathway.png")


if __name__ == '__main__':
    main()
