#!/usr/bin/env python3
"""
Generate TikZ code for a neural network from Python.

Demonstrates: Programmatic generation of LaTeX/TikZ code,
layered node placement, dense connection drawing, and
output to a standalone-compilable .tex file.

No install needed (generates .tex, compiles with pdflatex).
Run: python generate_tikz_network.py
Output: network.tex (compile with pdflatex)
"""

from pathlib import Path


def generate_tikz_neural_network(layers, output_file='network.tex'):
    """
    Generate TikZ code for a neural network architecture.

    Args:
        layers: list of (name, n_nodes, color_key)
                color_key: 'input', 'hidden', 'output'
        output_file: path to write the .tex file
    """
    colors = {
        'input': 'E69F00',
        'hidden': '56B4E9',
        'output': '009E73',
    }

    lines = [
        '\\begin{tikzpicture}',
        '  \\tikzset{neuron/.style={circle, draw=black, thick, '
        'minimum size=0.8cm, inner sep=0pt}}',
    ]

    x_spacing = 3
    for i, (name, n, color_key) in enumerate(layers):
        x = i * x_spacing
        color = colors.get(color_key, '999999')
        y_positions = [j - n / 2 + 0.5 for j in range(n)]

        for j, y in enumerate(y_positions):
            lines.append(
                f'  \\node[neuron, fill=#{color}] '
                f'(n{i}_{j}) at ({x},{y}) {{}};'
            )

        # Label below layer
        lines.append(f'  \\node at ({x}, {-n / 2 - 1}) {{{name}}};')

    # Connections between adjacent layers
    for i in range(len(layers) - 1):
        n1 = layers[i][1]
        n2 = layers[i + 1][1]
        for j in range(n1):
            for k in range(n2):
                lines.append(
                    f'  \\draw[gray, thin] (n{i}_{j}) -- (n{i + 1}_{k});'
                )

    lines.append('\\end{tikzpicture}')

    # Wrap in standalone document
    full_tex = (
        '\\documentclass[tikz,border=10pt]{standalone}\n'
        '\\usepackage{tikz}\n'
        '\\begin{document}\n'
        + '\n'.join(lines)
        + '\n\\end{document}\n'
    )

    Path(output_file).write_text(full_tex, encoding='utf-8')
    print(f"Saved: {output_file}")
    print(f"Compile with: pdflatex {output_file}")


def main():
    generate_tikz_neural_network([
        ('Input (784)', 4, 'input'),
        ('Hidden (128)', 6, 'hidden'),
        ('Output (10)', 3, 'output'),
    ])


if __name__ == '__main__':
    main()
