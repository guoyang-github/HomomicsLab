#!/usr/bin/env python3
"""
CONSORT participant flow diagram using NetworkX.

Demonstrates: Branching structures (screened → excluded / randomized),
custom node shapes/colors per category, manual layout for CONSORT standard
reading flow, and dual-format export.

Key advantage over Graphviz: handles branching correctly.

Install: pip install networkx matplotlib
Run: python networkx_consort.py
Output: consort_flowchart.pdf, consort_flowchart.png
"""

import matplotlib.pyplot as plt
import networkx as nx


def main():
    fig, ax = plt.subplots(figsize=(10, 12))
    G = nx.DiGraph()

    # Nodes with (x, y, label) — x scaled by 8 for final positioning
    nodes = {
        'screened': (0.5, 10, 'Assessed for\neligibility (n=500)'),
        'excluded': (0, 8.5, 'Excluded (n=150)'),
        'reasons': (0, 7.5, 'Age<18: 80\nDeclined: 50\nOther: 20'),
        'randomized': (0.5, 8, 'Randomized\n(n=350)'),
        'treat': (0.2, 6, 'Treatment\n(n=175)'),
        'control': (0.8, 6, 'Control\n(n=175)'),
        'lost_t': (0.2, 4.5, 'Lost to\nfollow-up\n(n=15)'),
        'lost_c': (0.8, 4.5, 'Lost to\nfollow-up\n(n=10)'),
        'analyzed_t': (0.2, 3, 'Analyzed\n(n=160)'),
        'analyzed_c': (0.8, 3, 'Analyzed\n(n=165)'),
    }

    for key, (x, y, label) in nodes.items():
        G.add_node(key, pos=(x * 8, y), label=label)

    # Edges
    edges = [
        ('screened', 'excluded'), ('screened', 'randomized'),
        ('excluded', 'reasons'),
        ('randomized', 'treat'), ('randomized', 'control'),
        ('treat', 'lost_t'), ('treat', 'analyzed_t'),
        ('control', 'lost_c'), ('control', 'analyzed_c'),
    ]
    G.add_edges_from(edges)

    pos = nx.get_node_attributes(G, 'pos')
    labels = nx.get_node_attributes(G, 'label')

    # Color coding by category
    node_colors = {
        'screened': '#56B4E9', 'randomized': '#56B4E9',
        'treat': '#009E73', 'control': '#009E73',
        'analyzed_t': '#E69F00', 'analyzed_c': '#E69F00',
        'excluded': '#D55E00', 'reasons': '#D55E00',
        'lost_t': '#CC79A7', 'lost_c': '#CC79A7',
    }

    for node in G.nodes():
        nx.draw_networkx_nodes(
            G, pos, nodelist=[node],
            node_shape='s',
            node_color=node_colors.get(node, '#999999'),
            node_size=3000, ax=ax
        )

    nx.draw_networkx_labels(G, pos, labels, font_size=8, font_weight='bold', ax=ax)
    nx.draw_networkx_edges(
        G, pos, edge_color='#333333', arrows=True,
        arrowsize=15, arrowstyle='->', ax=ax
    )

    ax.set_title('CONSORT Participant Flow Diagram', fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    plt.savefig('consort_flowchart.pdf', bbox_inches='tight')
    plt.savefig('consort_flowchart.png', bbox_inches='tight', dpi=300)
    print("Saved: consort_flowchart.pdf, consort_flowchart.png")


if __name__ == '__main__':
    main()
