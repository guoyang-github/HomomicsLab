---
name: scientific-visualization
description: "Create publication-ready scientific figures with matplotlib, seaborn, and plotly. Multi-panel layouts, statistical annotations, colorblind-safe palettes, journal-specific formatting (Nature, Cell, Science, 中国科学, 科学通报, 计算机学报, 物理学报, Chinese thesis), Chinese font support, and export to PDF/EPS/PNG/TIFF. Includes practical code examples for common plot types from scatter plots to volcano plots."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Visualization

## Overview

Scientific visualization transforms data into clear, accurate figures for publication. Create journal-ready plots with multi-panel layouts, error bars, significance markers, and colorblind-safe palettes. Export as PDF/EPS/PNG/TIFF using matplotlib, seaborn, and plotly. This skill runs locally, making it compatible with all LLM providers and environments.

## When to Use This Skill

This skill should be used when:
- Creating plots or visualizations for scientific manuscripts
- Preparing figures for journal submission (Nature, Science, Cell, PLOS, **中国科学, 科学通报, 计算机学报, 物理学报**, etc.)
- Preparing figures for **Chinese master's or doctoral dissertations (学位论文)**
- Ensuring figures are colorblind-friendly and accessible
- Making multi-panel figures with consistent styling
- Exporting figures at correct resolution and format
- Following specific publication guidelines
- Improving existing figures to meet publication standards
- Creating figures that need to work in both color and grayscale
- **Creating figures with Chinese labels, titles, and legends**
- **Ensuring Chinese fonts render correctly in matplotlib figures**

## Quick Start Guide

### Basic Publication-Quality Figure

```python
import matplotlib.pyplot as plt
import numpy as np

# Apply publication style (from scripts/style_presets.py)
from style_presets import apply_publication_style
apply_publication_style('default')

# Create figure with appropriate size (single column = 3.5 inches)
fig, ax = plt.subplots(figsize=(3.5, 2.5))

# Plot data
x = np.linspace(0, 10, 100)
ax.plot(x, np.sin(x), label='sin(x)')
ax.plot(x, np.cos(x), label='cos(x)')

# Proper labeling with units
ax.set_xlabel('Time (seconds)')
ax.set_ylabel('Amplitude (mV)')
ax.legend(frameon=False)

# Remove unnecessary spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Save in publication formats (from scripts/figure_export.py)
from figure_export import save_publication_figure
save_publication_figure(fig, 'figure1', formats=['pdf', 'png'], dpi=300)
```

### Using Pre-configured Styles

```python
import matplotlib.pyplot as plt

# Option 1: Use style file directly
plt.style.use('assets/nature.mplstyle')

# Option 2: Use style_presets.py helper
from style_presets import configure_for_journal
configure_for_journal('nature', figure_width='single')
```

### Using Chinese Journal Styles

```python
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Option 1: Use Chinese journal style file directly
plt.style.use('assets/science_china.mplstyle')

# Option 2: Use style_presets.py helper
from style_presets import configure_for_journal
configure_for_journal('science_china', figure_width='double')

# Option 3: Use for Chinese thesis/dissertation
from style_presets import apply_publication_style
apply_publication_style('chinese_thesis')

# Add Chinese text to figures
fig, ax = plt.subplots()
ax.set_xlabel('时间 (秒)', fontsize=12)
ax.set_ylabel('幅值 (mV)', fontsize=12)
ax.set_title('实验结果', fontsize=14)
ax.plot([1, 2, 3], [1, 4, 9], label='实验组')
ax.plot([1, 2, 3], [2, 3, 5], label='对照组')
ax.legend()
plt.show()
```

---

# Part 1: Core Principles and Best Practices

## 1. Resolution and File Format

- **Raster images** (photos, microscopy): 300-600 DPI
- **Line art** (graphs, plots): 600-1200 DPI or vector format
- **Vector formats** (preferred): PDF, EPS, SVG
- **Raster formats**: TIFF, PNG (never JPEG for scientific data)

```python
from figure_export import save_publication_figure
save_publication_figure(fig, 'myfigure', formats=['pdf', 'png'], dpi=300)
```

## 2. Color Selection — Colorblind Accessibility

**Always use colorblind-friendly palettes.**

**Recommended: Okabe-Ito palette:**
```python
from color_palettes import OKABE_ITO_LIST, apply_palette
apply_palette('okabe_ito')

# Manual specification
okabe_ito = ['#E69F00', '#56B4E9', '#009E73', '#F0E442',
             '#0072B2', '#D55E00', '#CC79A7', '#000000']
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=okabe_ito)
```

**For heatmaps/continuous data:**
- Use perceptually uniform colormaps: `viridis`, `plasma`, `cividis`
- Avoid red-green diverging maps (use `PuOr`, `RdBu`, `BrBG` instead)
- Never use `jet` or `rainbow` colormaps

**Always test figures in grayscale** to ensure interpretability.

## 3. Typography and Text

### English/International Journals
- Sans-serif fonts: Arial, Helvetica, Calibri
- Minimum sizes at **final print size**:
  - Axis labels: 7-9 pt
  - Tick labels: 6-8 pt
  - Panel labels: 8-12 pt (bold)
- Sentence case for labels: "Time (hours)" not "TIME (HOURS)"
- Always include units in parentheses

### Chinese Journals and Theses
- **Chinese fonts**: SimHei (黑体) for labels/titles, SimSun (宋体) for body text
- **English fonts in Chinese figures**: Arial or Times New Roman
- **Minimum sizes** (Chinese characters need slightly larger sizes):
  - Axis labels: 8-10 pt
  - Tick labels: 7-9 pt
  - Chinese labels may need 1-2 pt larger than English equivalents
- **Font configuration**:
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Source Han Sans CN',
                                    'Noto Sans CJK SC', 'Arial']
plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign display
```

**Important**: Ensure Chinese fonts are installed on your system. Common options:
- **Windows**: SimHei (黑体), SimSun (宋体), Microsoft YaHei (微软雅黑)
- **Linux**: Noto Sans CJK SC, WenQuanYi Micro Hei, Source Han Sans
- **macOS**: PingFang SC, Heiti SC, Source Han Sans

## 4. Figure Dimensions

### International Journals
- **Nature**: Single 89 mm, Double 183 mm
- **Science**: Single 55 mm, Double 175 mm
- **Cell**: Single 85 mm, Double 178 mm

### Chinese Journals
- **中国科学 / 科学通报**: Single 82 mm, Double 170 mm
- **物理学报**: Double 170 mm (rarely single column)
- **计算机学报**: Double 160 mm

### Chinese Thesis/Dissertation (A4)
- Full width: 140-160 mm
- Figure height: Typically 100-120 mm
- Larger fonts for readability

```python
from figure_export import check_figure_size

# International journal
fig = plt.figure(figsize=(3.5, 3))  # 89 mm for Nature
check_figure_size(fig, journal='nature')

# Chinese journal
fig = plt.figure(figsize=(3.23, 2.43))  # 82 mm for Science China
check_figure_size(fig, journal='science_china')

# Chinese thesis (A4)
fig = plt.figure(figsize=(5.5, 4.1))  # 140 mm width
check_figure_size(fig, journal='chinese_thesis')
```

## 5. Multi-Panel Figures

- Label panels with bold letters: **A**, **B**, **C**
- Maintain consistent styling across all panels
- Align panels along edges where possible
- Use adequate white space between panels

---

# Part 2: Practical Code Examples

## Scatter Plot

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(6, 5))
ax.scatter(x_data, y_data, s=20, alpha=0.6, c='steelblue',
           edgecolors='k', linewidths=0.5)
ax.set_xlabel('Gene Expression (log2)', fontsize=12)
ax.set_ylabel('Cell Count', fontsize=12)
ax.set_title('Expression vs. Cell Count', fontsize=14, fontweight='bold')
ax.grid(alpha=0.3)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig('scatter_plot.png', dpi=300, bbox_inches='tight')
plt.show()
```

## Line Plot with Multiple Series

```python
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(time_points, group1_values, marker='o',
        label='Group 1', color='#E74C3C', linewidth=2)
ax.plot(time_points, group2_values, marker='s',
        label='Group 2', color='#3498DB', linewidth=2)
ax.set_xlabel('Time Point', fontsize=12)
ax.set_ylabel('Expression Level', fontsize=12)
ax.legend(frameon=True, loc='best', fontsize=10)
ax.grid(alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig('line_plot.png', dpi=300, bbox_inches='tight')
```

## Box Plot and Violin Plot

```python
import seaborn as sns

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

sns.boxplot(data=df, x='cluster', y='expression', palette='Set2', ax=ax1)
ax1.set_title('Box Plot: Expression by Cluster',
              fontsize=12, fontweight='bold')

sns.violinplot(data=df, x='cluster', y='expression',
               palette='muted', ax=ax2, inner='quartile')
ax2.set_title('Violin Plot: Expression Distribution',
              fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('box_violin_plot.png', dpi=300, bbox_inches='tight')
```

## Heatmap

```python
fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(
    gene_expression_matrix,
    cmap='viridis',
    cbar_kws={'label': 'Expression'},
    xticklabels=True,
    yticklabels=True,
    linewidths=0.5,
    linecolor='gray',
    ax=ax
)
ax.set_title('Gene Expression Heatmap', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('heatmap.png', dpi=300, bbox_inches='tight')
```

## Bar Plot with Error Bars

```python
fig, ax = plt.subplots(figsize=(7, 5))
categories = ['Cluster 0', 'Cluster 1', 'Cluster 2', 'Cluster 3']
means = [120, 85, 200, 150]
errors = [15, 10, 25, 20]

bars = ax.bar(categories, means, yerr=errors, capsize=5,
              color=['#E74C3C', '#3498DB', '#2ECC71', '#F39C12'],
              edgecolor='black', linewidth=1.2, alpha=0.8)
ax.set_ylabel('Cell Count', fontsize=12)
ax.set_title('Cell Counts by Cluster', fontsize=14, fontweight='bold')

for bar, mean in zip(bars, means):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 5,
            f'{mean}', ha='center', va='bottom', fontsize=10)

plt.tight_layout()
plt.savefig('bar_plot.png', dpi=300, bbox_inches='tight')
```

## Multi-Panel Figure

```python
from matplotlib import gridspec

fig = plt.figure(figsize=(12, 8))
gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.3, wspace=0.3)

ax1 = fig.add_subplot(gs[0, :2])
ax1.scatter(x_data, y_data, c=cluster_labels, cmap='tab10',
            s=10, alpha=0.6)
ax1.set_title('A. UMAP Projection', fontsize=12,
              fontweight='bold', loc='left')

ax2 = fig.add_subplot(gs[0, 2])
sns.violinplot(data=df, y='expression', palette='Set2', ax=ax2)
ax2.set_title('B. Expression', fontsize=12, fontweight='bold', loc='left')

ax3 = fig.add_subplot(gs[1, :])
sns.heatmap(matrix, cmap='coolwarm', center=0, ax=ax3,
            cbar_kws={'label': 'Z-score'})
ax3.set_title('C. Gene Expression Heatmap', fontsize=12,
              fontweight='bold', loc='left')

plt.savefig('multi_panel_figure.png', dpi=300, bbox_inches='tight')
```

## Volcano Plot (Differential Expression)

```python
fig, ax = plt.subplots(figsize=(8, 7))
deg_df['-log10_pvalue'] = -np.log10(deg_df['pvalue'])

deg_df['significant'] = 'Not Significant'
deg_df.loc[(deg_df['log2FC'] > 1) & (deg_df['pvalue'] < 0.05),
           'significant'] = 'Up-regulated'
deg_df.loc[(deg_df['log2FC'] < -1) & (deg_df['pvalue'] < 0.05),
           'significant'] = 'Down-regulated'

for category, color in zip(['Not Significant', 'Up-regulated', 'Down-regulated'],
                           ['gray', 'red', 'blue']):
    mask = deg_df['significant'] == category
    ax.scatter(deg_df.loc[mask, 'log2FC'],
               deg_df.loc[mask, '-log10_pvalue'],
               c=color, label=category, s=20, alpha=0.6)

ax.axvline(x=1, color='black', linestyle='--', linewidth=1, alpha=0.5)
ax.axvline(x=-1, color='black', linestyle='--', linewidth=1, alpha=0.5)
ax.axhline(y=-np.log10(0.05), color='black', linestyle='--',
           linewidth=1, alpha=0.5)
ax.set_xlabel('log2 Fold Change', fontsize=12)
ax.set_ylabel('-log10(p-value)', fontsize=12)
ax.set_title('Volcano Plot', fontsize=14, fontweight='bold')
ax.legend(frameon=True, loc='upper right')
plt.tight_layout()
plt.savefig('volcano_plot.png', dpi=300, bbox_inches='tight')
```

## UMAP/tSNE Visualization

```python
fig, ax = plt.subplots(figsize=(8, 7))
clusters = adata.obs['clusters'].unique()
n_clusters = len(clusters)
colors = plt.cm.tab20(np.linspace(0, 1, n_clusters))

for i, cluster in enumerate(clusters):
    mask = adata.obs['clusters'] == cluster
    ax.scatter(
        adata.obsm['X_umap'][mask, 0],
        adata.obsm['X_umap'][mask, 1],
        c=[colors[i]],
        label=f'Cluster {cluster}',
        s=10, alpha=0.7, edgecolors='none'
    )

ax.set_xlabel('UMAP1', fontsize=12)
ax.set_ylabel('UMAP2', fontsize=12)
ax.set_title('UMAP Projection by Cluster',
             fontsize=14, fontweight='bold')
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left',
          frameon=True, fontsize=9)
plt.tight_layout()
plt.savefig('umap_clusters.png', dpi=300, bbox_inches='tight')
```

---

# Part 3: Statistical Rigor

**Always include:**
- Error bars (SD, SEM, or CI — specify which in caption)
- Sample size (n) in figure or caption
- Statistical significance markers (*, **, ***)
- Individual data points when possible (not just summary statistics)

**Example with statistics:**
```python
# Show individual points with summary statistics
ax.scatter(x_jittered, individual_points, alpha=0.4, s=8)
ax.errorbar(x, means, yerr=sems, fmt='o', capsize=3)

# Mark significance
ax.text(1.5, max_y * 1.1, '***', ha='center', fontsize=8)
```

---

# Part 4: Working with Seaborn

Seaborn provides a high-level interface for statistical graphics built on matplotlib.

## Configuration for Publication

```python
import seaborn as sns
import matplotlib.pyplot as plt
from style_presets import apply_publication_style

apply_publication_style('default')
sns.set_theme(style='ticks', context='paper', font_scale=1.1)
sns.set_palette('colorblind')
```

## Common Plot Types

**Statistical comparisons:**
```python
fig, ax = plt.subplots(figsize=(3.5, 3))
sns.boxplot(data=df, x='treatment', y='response',
            order=['Control', 'Low', 'High'], palette='Set2', ax=ax)
sns.stripplot(data=df, x='treatment', y='response',
              order=['Control', 'Low', 'High'],
              color='black', alpha=0.3, size=3, ax=ax)
ax.set_ylabel('Response (μM)')
sns.despine()
```

**Correlation matrices:**
```python
fig, ax = plt.subplots(figsize=(5, 4))
corr = df.corr()
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, fmt='.2f',
            cmap='RdBu_r', center=0, square=True,
            linewidths=1, cbar_kws={'shrink': 0.8}, ax=ax)
```

**Time series with confidence bands:**
```python
fig, ax = plt.subplots(figsize=(5, 3))
sns.lineplot(data=timeseries, x='time', y='measurement',
             hue='treatment', errorbar=('ci', 95),
             markers=True, ax=ax)
ax.set_xlabel('Time (hours)')
ax.set_ylabel('Measurement (AU)')
sns.despine()
```

## Best Practices for Seaborn

1. Always set publication theme first
2. Use colorblind-safe palettes (`colorblind`, `Set2`)
3. Remove unnecessary elements with `sns.despine()`
4. Show individual data points when possible
5. Include proper labels with units
6. Export at correct resolution

---

# Part 5: Troubleshooting

### Issue: "Figure too cluttered with many points"
**Solution**: Use transparency and smaller point sizes
```python
ax.scatter(x, y, s=5, alpha=0.3, edgecolors='none')
```

### Issue: "Legend overlaps with data"
**Solution**: Place legend outside the plot area
```python
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
```

### Issue: "Labels are cut off in saved figure"
**Solution**: Use `bbox_inches='tight'`
```python
plt.savefig('plot.png', dpi=300, bbox_inches='tight')
```

### Issue: "Colors don't match between plots"
**Solution**: Define color palette once and reuse
```python
PALETTE = {'Group A': '#E74C3C', 'Group B': '#3498DB'}
```

### Issue: "Heatmap text too small"
**Solution**: Adjust figure size or font size
```python
fig, ax = plt.subplots(figsize=(12, 10))
sns.heatmap(data, ax=ax, annot_kws={'fontsize': 8})
```

---

# Part 6: Resources

## Scripts
- **`figure_export.py`**: `save_publication_figure()`, `save_for_journal()`, `check_figure_size()`
- **`style_presets.py`**: `apply_publication_style()`, `configure_for_journal()`, `set_color_palette()`

## Assets

### International Journal Styles
- **`color_palettes.py`**: Importable color definitions
- **`publication.mplstyle`**: General publication style
- **`nature.mplstyle`**: Nature journal style
- **`presentation.mplstyle`**: Presentation/large-font style

### Chinese Journal Styles
- **`science_china.mplstyle`**: 《中国科学》/《科学通报》style (82/170 mm, Chinese font support)
- **`sci_bulletin.mplstyle`**: 《科学通报》style (same as Science China)
- **`acta_physica.mplstyle`**: 《物理学报》style (85/170 mm, smaller fonts)
- **`journal_computers.mplstyle`**: 《计算机学报》style (80/160 mm, B&W optimized)
- **`chinese_thesis.mplstyle`**: Chinese thesis/dissertation style (A4, larger fonts, serif body)

## References
- **`publication_guidelines.md`**: Comprehensive best practices
- **`color_palettes.md`**: Color usage and accessibility guide
- **`journal_requirements.md`**: Journal-specific specifications (Nature, Science, Cell, **中国科学, 科学通报, 计算机学报, 物理学报**)
- **`matplotlib_examples.md`**: Extended practical code examples

## Final Checklist

Before submitting figures, verify:

### Universal Quality Checklist
- [ ] **Overlapping labels**: Text does not visually collide on axes or legend
- [ ] **Clipped text**: No labels or titles cut off at figure edge (`tight_layout()` or `constrained_layout`)
- [ ] **Missing axes or legends**: All axes have labels with units; legends present for multi-series plots
- [ ] **Empty plot areas**: Data is actually rendered (check filtering, column names, plot args)
- [ ] **Overcrowded data**: Points do not merge into an unreadable mass (use `alpha`, hexbin, or density plots)
- [ ] Resolution meets journal requirements (300+ DPI)
- [ ] File format is correct (vector for plots, TIFF for images)
- [ ] Figure size matches journal specifications
- [ ] All text readable at final size (≥6 pt for English, ≥7-8 pt for Chinese)
- [ ] Colors are colorblind-friendly
- [ ] Figure works in grayscale
- [ ] All axes labeled with units
- [ ] Error bars present with definition in caption
- [ ] Panel labels present and consistent
- [ ] No chart junk or 3D effects
- [ ] Fonts consistent across all figures
- [ ] **Chinese fonts render correctly (no tofu/boxes)**
- [ ] **Chinese and English labels use appropriate fonts**
- [ ] Statistical significance clearly marked
- [ ] Legend is clear and complete

### Journal-Specific Figure Submission Guides

Detailed per-journal specifications (resolution tiers, format preferences, font requirements, panel label conventions, image integrity policies, Python validation scripts, and pre-submission checklists) are maintained in separate reference files:

| Journal | Key Distinction | Reference File |
|---------|----------------|----------------|
| **Nature** | Lowercase bold labels (a, b, c); RGB preferred; 300+ DPI; max 10 MB; Helvetica/Arial | `references/nature_figure_guide.md` |
| **Cell** | Uppercase bold labels (A, B, C); three-tier resolution (300/500/1000 DPI); Avenir preferred; strict no-clone-tool policy | `references/cell_figure_guide.md` |
| **Science** | Two-stage submission (150 DPI initial → 300+ revised); Myriad font; disclose nonlinear (gamma) adjustments in caption | `references/science_figure_guide.md` |
| **PNAS** | *Italicized* uppercase labels (*A*, *B*, *C*); **strict RGB-only** (CMYK rejected); automated image screening | `references/pnas_figure_guide.md` |
| **NEJM** | Line art 1200 DPI; editable vector preferred (AI/EPS/SVG); **do NOT submit medical illustrations** (in-house redraw); patient de-identification mandatory | `references/nejm_figure_guide.md` |
| **The Lancet** | **Times New Roman** (serif); editable formats preferred (PowerPoint/Word/SVG); submit at **120%** of publication size; in-house redraw | `references/lancet_figure_guide.md` |
| **eLife** | Striking image 1800×900 px (no text); figure supplement naming (`Figure X--Figure Supplement Y`); routine screening; selective enhancement = misconduct | `references/elife_figure_guide.md` |
| **Cancer Research** | Hierarchical labels (Ai, Aii, Bi); max 7 display items; legends must include technical + biological replicate counts | `references/cancer_research_figure_guide.md` |

For a quick cross-journal comparison table (widths, resolutions, formats), see `references/journal_requirements.md`.

**Universal image integrity rules (COPE-aligned across all journals):**
- Apply brightness/contrast adjustments **uniformly to the entire image** only
- Never selectively enhance specific regions (e.g., one gel lane) — this is data manipulation
- Keep scale bars on separate layers (not flattened into image)
- Do NOT outline text in vector files (must remain editable)
- Retain original unprocessed data for editor/reviewer requests

**Python validation template** (`scripts/validate_figure.py`):
```python
from PIL import Image
import os

def validate_figure(image_path, min_dpi=300, max_mb=10, required_mode='RGB'):
    """Generic figure validation — customize per-journal rules."""
    img = Image.open(image_path)
    issues = []
    dpi = img.info.get('dpi', (72, 72))
    if dpi[0] < min_dpi or dpi[1] < min_dpi:
        issues.append(f"Resolution {dpi[0]}x{dpi[1]} DPI below {min_dpi}")
    if required_mode and img.mode != required_mode:
        issues.append(f"Color mode {img.mode}; {required_mode} recommended")
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > max_mb:
        issues.append(f"File size {size_mb:.1f} MB exceeds {max_mb} MB")
    print(f"=== Validation: {os.path.basename(image_path)} ===")
    print(f"Dimensions: {img.size[0]} x {img.size[1]} px | DPI: {dpi[0]} x {dpi[1]} | Mode: {img.mode}")
    if issues:
        print(f"ISSUES ({len(issues)}):", *issues, sep="\n  - ")
    else:
        print("All checks PASSED")
    return len(issues) == 0
```

---

## Integration with Other Skills

This skill connects to the broader research workflow:

- **scientific-manuscript** — Figures created here are embedded into papers; follow journal-specific figure guidelines for resolution, format, and dimensions
- **scientific-illustration** — Data plots and conceptual diagrams complement each other in publications; use consistent color palettes across both
- **scientific-peer-review** — Apply figure quality standards (resolution, labeling, colorblind accessibility) when evaluating others' visualizations
- **scientific-communication** — Conference slides and posters reuse figures from manuscripts; adapt sizing and typography for each medium
