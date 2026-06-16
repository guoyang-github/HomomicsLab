#!/bin/bash
# Example usage of scientific-illustration skill
#
# This script demonstrates TWO paths:
#   1. Code-Based (zero configuration, recommended)
#   2. AI API (requires API key)
#
# For most users, Code-Based paths are preferred: reproducible,
# version-controllable, and produce vector (PDF/SVG) output.

set -e

echo "=========================================="
echo "Scientific Illustration - Example Usage"
echo "=========================================="
echo ""

mkdir -p figures

# ============================================================================
# PATH 1: Code-Based (Zero Configuration - RECOMMENDED)
# ============================================================================

echo "PATH 1: Code-Based Diagrams (Zero Config)"
echo "-------------------------------------------"
echo "These examples use Python + standard packages only."
echo "No API keys. No external services. Fully reproducible."
echo ""

# Example 1: Block diagram with Matplotlib
echo "Example 1.1: IoT System Block Diagram (Matplotlib)"
cat > /tmp/block_diagram.py << 'PYEOF'
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(10, 3))
ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis('off')
COLORS = {'sensor': '#E69F00', 'mcu': '#56B4E9', 'cloud': '#009E73', 'app': '#CC79A7'}

def box(ax, x, y, w, h, label, color):
    b = FancyBboxPatch((x,y), w, h, boxstyle="round,pad=0.02,rounding_size=0.2",
                       facecolor=color, edgecolor='black', linewidth=1.2)
    ax.add_patch(b)
    ax.text(x+w/2, y+h/2, label, ha='center', va='center', fontsize=11, fontweight='bold', color='white')

def arrow(ax, s, e, label=None):
    a = FancyArrowPatch(s, e, arrowstyle='->', mutation_scale=20, linewidth=1.5, color='#333')
    ax.add_patch(a)
    if label:
        ax.text((s[0]+e[0])/2, (s[1]+e[1])/2+0.25, label, ha='center', fontsize=9, style='italic', color='#555')

box(ax, 0.5, 0.9, 1.8, 1.2, 'Sensors', COLORS['sensor'])
box(ax, 3.0, 0.9, 2.0, 1.2, 'ESP32\nMicrocontroller', COLORS['mcu'])
box(ax, 5.8, 0.9, 1.8, 1.2, 'Cloud\nServer', COLORS['cloud'])
box(ax, 8.2, 0.9, 1.5, 1.2, 'Mobile\nApp', COLORS['app'])
arrow(ax, (2.3, 1.5), (3.0, 1.5), 'I2C/UART')
arrow(ax, (5.0, 1.5), (5.8, 1.5), 'WiFi')
arrow(ax, (7.6, 1.5), (8.2, 1.5), 'REST API')
ax.set_title('IoT System Architecture', fontsize=14, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig('figures/iot_block_diagram.pdf', bbox_inches='tight')
plt.savefig('figures/iot_block_diagram.png', bbox_inches='tight', dpi=300)
print("  -> figures/iot_block_diagram.{pdf,png}")
PYEOF
python /tmp/block_diagram.py

echo ""
echo "Example 1.2: Neural Network Layers (Matplotlib)"
cat > /tmp/neural_net.py << 'PYEOF'
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(7, 4.5))
def draw_layer(ax, x, n, label, color):
    ys = np.linspace(0.8, 4.2, n)
    for y in ys:
        ax.add_patch(plt.Circle((x, y), 0.18, color=color, ec='black', linewidth=1))
    ax.text(x, 0.2, label, ha='center', fontsize=10, fontweight='bold')
    return ys

def connect(ax, x1, y1s, x2, y2s):
    for y1 in y1s:
        for y2 in y2s:
            ax.plot([x1, x2], [y1, y2], 'k-', alpha=0.25, linewidth=0.4)

iy = draw_layer(ax, 1.2, 4, 'Input (784)', '#E69F00')
hy = draw_layer(ax, 3.8, 6, 'Hidden (128)', '#56B4E9')
oy = draw_layer(ax, 6.4, 3, 'Output (10)', '#009E73')
connect(ax, 1.2, iy, 3.8, hy)
connect(ax, 3.8, hy, 6.4, oy)
ax.set_xlim(0, 7.5); ax.set_ylim(-0.3, 5); ax.set_aspect('equal'); ax.axis('off')
ax.set_title('Neural Network Architecture', fontsize=13, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig('figures/neural_network.pdf', bbox_inches='tight')
plt.savefig('figures/neural_network.png', bbox_inches='tight', dpi=300)
print("  -> figures/neural_network.{pdf,png}")
PYEOF
python /tmp/neural_net.py

echo ""
echo "Example 1.3: CONSORT Flowchart (NetworkX)"
cat > /tmp/consort.py << 'PYEOF'
import matplotlib.pyplot as plt
import networkx as nx

fig, ax = plt.subplots(figsize=(9, 10))
G = nx.DiGraph()
nodes = {
    'screened': (0.5, 9, 'Assessed for\neligibility\n(n=500)'),
    'excluded': (0, 7.5, 'Excluded\n(n=150)'),
    'randomized': (0.5, 7.5, 'Randomized\n(n=350)'),
    'treat': (0.2, 5.5, 'Treatment\n(n=175)'),
    'control': (0.8, 5.5, 'Control\n(n=175)'),
    'analyzed_t': (0.2, 3.5, 'Analyzed\n(n=160)'),
    'analyzed_c': (0.8, 3.5, 'Analyzed\n(n=165)'),
}
for k, (x, y, lab) in nodes.items():
    G.add_node(k, pos=(x*8, y), label=lab)

edges = [('screened','excluded'),('screened','randomized'),('randomized','treat'),
         ('randomized','control'),('treat','analyzed_t'),('control','analyzed_c')]
G.add_edges_from(edges)

pos = {n: (p[0], p[1]) for n, p in nx.get_node_attributes(G, 'pos').items()}
labels = nx.get_node_attributes(G, 'label')
colors = {'screened':'#56B4E9','randomized':'#56B4E9','treat':'#009E73',
          'control':'#009E73','analyzed_t':'#E69F00','analyzed_c':'#E69F00','excluded':'#D55E00'}

for n in G.nodes():
    nx.draw_networkx_nodes(G, pos, [n], node_shape='s', node_color=colors.get(n,'#999'),
                           node_size=4500, ax=ax)
nx.draw_networkx_labels(G, pos, labels, font_size=8, font_weight='bold', ax=ax)
nx.draw_networkx_edges(G, pos, edge_color='#333', arrows=True, arrowsize=15, ax=ax)
ax.set_title('CONSORT Participant Flow', fontsize=13, fontweight='bold')
ax.axis('off')
plt.tight_layout()
plt.savefig('figures/consort_flowchart.pdf', bbox_inches='tight')
plt.savefig('figures/consort_flowchart.png', bbox_inches='tight', dpi=300)
print("  -> figures/consort_flowchart.{pdf,png}")
PYEOF
python /tmp/consort.py

echo ""
echo "✓ Code-Based examples complete. Output: figures/*.pdf and figures/*.png"
echo ""

# ============================================================================
# PATH 2: AI API (Requires Configuration)
# ============================================================================

echo "PATH 2: AI API Generation"
echo "-------------------------"

# Check for API key
ENV_KEY_NAME=$(python -c "import json; print(json.load(open('scripts/config/ai_models.json')).get('env_key_name','OPENROUTER_API_KEY'))" 2>/dev/null || echo "OPENROUTER_API_KEY")

if [ -z "${!ENV_KEY_NAME}" ]; then
    echo "⚠️  Skipping API examples: \$${ENV_KEY_NAME} not set."
    echo "   To run API examples: export ${ENV_KEY_NAME}='your_key'"
    echo "   Code-Based examples above are recommended for most use cases."
    echo ""
else
    echo "✓ ${ENV_KEY_NAME} is set"
    echo ""

    echo "Example 2.1: CONSORT Flowchart (AI)"
    python scripts/generate_schematic.py \
      "CONSORT participant flow diagram. Assessed for eligibility (n=500). Excluded (n=150). Randomized (n=350) into Treatment (n=175) and Control (n=175). Final analysis: 160 and 165." \
      -o figures/consort_ai.png --iterations 2 || echo "  (API generation failed, use Code-Based path above)"

    echo ""
    echo "Example 2.2: Neural Network (AI)"
    python scripts/generate_schematic.py \
      "Transformer encoder-decoder architecture with multi-head attention" \
      -o figures/transformer_ai.png --iterations 2 || echo "  (API generation failed)"
fi

echo ""
echo "=========================================="
echo "All examples complete!"
echo "=========================================="
echo ""
echo "Generated files in figures/:"
ls -lh figures/*.{pdf,png} 2>/dev/null || echo "  (Check figures/ directory)"
echo ""
echo "Recommended next steps:"
echo "  1. For reproducible, publication-quality diagrams: Use Code-Based paths"
echo "  2. For quick drafts: Use LLM Native mode (Claude Code direct generation)"
echo "  3. For biological schematics: Use BioRender or Inkscape (Manual path)"
echo ""
