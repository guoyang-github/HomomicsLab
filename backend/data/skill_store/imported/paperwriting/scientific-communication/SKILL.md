---
name: scientific-communication
description: "Create scientific presentations, conference posters, and research dissemination materials. Build slide decks (PDF/PowerPoint), design LaTeX research posters, and transform papers into interactive websites and presentation videos. Includes AI-powered visual generation, formatting templates, and publication-ready output workflows."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Communication

## Overview

Scientific communication transforms research into accessible, engaging formats for diverse audiences. This skill covers three core outputs:

1. **Presentation Slides** — Conference talks, seminars, thesis defenses, and grant pitches in PDF or PowerPoint formats
2. **Research Posters** — Professional LaTeX posters for conferences and symposiums
3. **Research Dissemination** — Interactive websites, videos, and promotional materials from existing papers

**Critical Design Philosophy**: All scientific communication should be visually engaging and research-backed. Avoid dry, text-heavy formats. Combine compelling visuals, minimal text, and clear narrative arcs.

## When to Use This Skill

This skill should be used when:
- Preparing conference presentations, seminars, or thesis defenses
- Designing research posters for conferences or poster sessions
- Creating grant pitch presentations
- Converting papers into websites, videos, or promotional materials
- Generating video abstracts or online talks
- Building explorable academic homepages for preprints or publications
- Preparing journal club or teaching presentations

---

# Part 1: Presentation Slides

## Design Principles

**Key Focus**: Oral presentations for conferences, seminars, defenses, and professional talks.

**CRITICAL DESIGN PHILOSOPHY**: Scientific presentations should be VISUALLY ENGAGING and RESEARCH-BACKED. Avoid dry, text-heavy slides at all costs. Great scientific presentations combine:
- **Compelling visuals**: High-quality figures, images, diagrams (not just bullet points)
- **Research context**: Proper citations establishing credibility
- **Minimal text**: Bullet points as prompts, YOU provide the explanation verbally
- **Professional design**: Modern color schemes, strong visual hierarchy, generous white space
- **Story-driven**: Clear narrative arc, not just data dumps

**Remember**: Boring presentations = forgotten science. Make your slides visually memorable while maintaining scientific rigor through proper citations.

## Execution Modes

The `generate_slide_image.py` script automatically selects the best available backend in this priority:

1. **External API** — If `config/ai_models.json` + API key are configured
2. **Local PPTX** — If `python-pptx` is installed (generates `.pptx` files)
3. **Spec Fallback** — If nothing is available, generates a task specification JSON

**As the calling LLM, follow this decision flow:**

```
Is external API configured (ai_models.json + env var)?
  YES → Run the script, it will use the API backend automatically
  NO  → Do you have image generation capabilities?
          YES → Use LLM Native mode (generate directly, see below)
          NO  → Run the script, it will use PPTX or Spec fallback
```

### Mode 1: External API (Requires Configuration)

The script auto-detects API configuration and uses the configured image generation model. This is the **recommended first choice** when available.

**Requirements:**
1. `scripts/config/ai_models.json` is configured with your provider
2. The corresponding API key environment variable is set

```bash
python scripts/generate_slide_image.py "slide description" -o output.png
```

### Mode 2: LLM Native (Zero Configuration)

**Use this mode only when no external API is configured AND you (the calling LLM) have image generation capabilities.**

Generate slides directly using your own image generation ability, then save images to the output path.

**Optimized Prompt Template:**
```
Create a professional presentation slide (16:9) with these requirements:

LAYOUT:
- Clean, modern design with clear visual hierarchy
- Title at top, content below
- Generous margins (at least 5% on all sides)
- Balanced composition with intentional white space

TYPOGRAPHY:
- LARGE, bold title text, easily readable from distance
- Clear, sans-serif fonts throughout
- High contrast text (dark on light or light on dark)
- Bullet points or key phrases, NOT paragraphs
- Maximum 5-6 lines of text content

VISUAL ELEMENTS:
- Use generic, simple images and icons
- Minimal extra elements, no decorative borders
- Consistent color scheme (2-3 main colors)

PROFESSIONAL MINIMALISM:
- Less is more: favor empty space
- No unnecessary decorations or gradients
- Clean lines and simple shapes

USER REQUEST: {your slide description}
```

### Mode 3: Local PPTX (Zero Configuration)

If no API is configured but `python-pptx` is installed, the script generates structured `.pptx` slides with multiple academic layouts, themes, chart embedding, and QA validation.

**Install:**
```bash
pip install python-pptx
```

**Supported Layouts:**

| Layout | Trigger | Description |
|--------|---------|-------------|
| `title` | `[LAYOUT: title]` or starts with "Title/Cover" | Title slide with subtitle, author, date |
| `content` | Default / `[LAYOUT: content]` | Title + bullet points (up to 6) |
| `two_column` | `[LAYOUT: two_column]` or "two column/compare" | Side-by-side comparison |
| `image_text` | `[LAYOUT: image_text]` or `IMAGE:` path | Image left + text right |
| `chart` | `[LAYOUT: chart]` or `DATA:` marker | Title + matplotlib chart from data |
| `table` | `[LAYOUT: table]` or `TABLE:` marker | Title + data table |
| `full_image` | `[LAYOUT: full_image]` | Full-slide image with caption |

**Supported Themes:**

| Theme | Trigger | Style |
|-------|---------|-------|
| `light` | Default | White background, dark text, blue accent (Okabe-Ito) |
| `dark` | `[THEME: dark]` or "dark background" | Deep blue background, white text, gold accent |
| `minimal` | `[THEME: minimal]` | Light gray, Helvetica/Arial, orange accent |

**Examples:**

```bash
# Title slide
python scripts/generate_slide_image.py "[LAYOUT: title] My Research\nSubtitle: A Review\nAuthor: Dr. Smith" -o title.pptx

# Content slide (auto-detected)
python scripts/generate_slide_image.py "Introduction\n- Background\n- Motivation" -o intro.pptx

# Chart slide with data
python scripts/generate_slide_image.py "[LAYOUT: chart] Accuracy Over Time\nDATA: x=[1,2,3,4,5], y=[0.82,0.88,0.91,0.93,0.95]" -o chart.pptx

# Table slide
python scripts/generate_slide_image.py "[LAYOUT: table] Comparison\nTABLE: Method | Acc | F1\nA | 0.95 | 0.92\nB | 0.91 | 0.88" -o table.pptx

# Image + text slide
python scripts/generate_slide_image.py "[LAYOUT: image_text] Methods\nIMAGE: figures/method.png\n- Data collection\n- Preprocessing" -o methods.pptx

# Dark theme
python scripts/generate_slide_image.py "[THEME: dark] Results\n- Finding 1\n- Finding 2" -o dark_slide.pptx
```

**Visual-only mode:**
```bash
# Generate a matplotlib chart directly
python scripts/generate_slide_image.py "DATA: x=[1,2,3], y=[4,5,6]" -o chart.png --visual-only

# Generate a diagram from keywords
python scripts/generate_slide_image.py "Neural network architecture diagram" -o diagram.png --visual-only
```

### Mode 4: Spec Fallback (No Dependencies)

If no backend is available, the script generates a `*_spec.json` file containing an optimized prompt and quality guidelines. You (the LLM) or the user can then use this spec to generate the image manually.

```bash
python scripts/generate_slide_image.py "slide description" -o output.png
# Generates output_spec.json with optimized prompt for manual generation
```

---

## Slide Generation Workflows

### Workflow 1: PDF Slides (Recommended)

Generate each slide as a complete image, then combine into a PDF. This produces the most visually stunning results.

**Step 1: Plan Each Slide**

Create a detailed plan for your presentation before generating:

```markdown
# Presentation Plan

## Slide 1: Title Slide
- Title: "Machine Learning: From Theory to Practice"
- Subtitle: "AI Conference 2025"
- Speaker: Author Name
- Visual: Modern abstract background

## Slide 2: Introduction
- Title: "Why Machine Learning Matters"
- Key points: Industry adoption, breakthrough applications
- Visual: Icons showing different applications

## Slide 3: Results
- Title: "Model Performance"
- Key findings: 95% accuracy, 12% improvement over baseline
- Visual: Attached accuracy chart from figures/
```

**Step 2: Generate Each Slide**

Use the `generate_slide_image.py` script to create each slide. The script auto-detects the best available backend (API, PPTX, or Spec).

**CRITICAL: Formatting Consistency Protocol**

1. **Define a Formatting Goal** at the start and include it in EVERY prompt:
   - Color scheme (e.g., "dark blue background, white text, gold accents")
   - Typography style (e.g., "bold sans-serif titles, clean body text")
   - Visual style (e.g., "minimal, professional, generous margins")

2. **Include citations directly in the prompt** for slides that reference research

3. **Reference existing figures/data for results slides** (CRITICAL):
   - When creating results slides, ALWAYS check for existing figures in the working directory
   - Include figure descriptions directly in the prompt text (e.g., "Present the accuracy chart showing 95% accuracy")

**Example:**
```bash
# Title slide (first slide - establishes the style)
python scripts/generate_slide_image.py "Title slide: 'Machine Learning: From Theory to Practice'. Subtitle: 'AI Conference 2025'. Speaker: Author Name. FORMATTING GOAL: Dark blue background (#1a237e), white text, gold accents (#ffc107), minimal design, sans-serif fonts, generous margins." -o slides/01_title.png

# Content slide with citations
python scripts/generate_slide_image.py "Slide titled 'Why Machine Learning Matters'. Three key points with icons. CITATIONS: Include at bottom: (LeCun et al., 2015; Goodfellow et al., 2016). FORMATTING GOAL: Dark blue background, white text, gold accents." -o slides/02_intro.png

# Results slide - describe the figure in the prompt
python scripts/generate_slide_image.py "Slide titled 'Model Performance Results'. Present an accuracy chart showing 95% accuracy, outperforming baseline by 12%. FORMATTING GOAL: Dark blue background, white text, gold accents." -o slides/03_results.png
```

**Step 3: Combine to PDF**

```bash
python scripts/slides_to_pdf.py slides/*.png -o presentation.pdf
```

### Workflow 2: PowerPoint with Generated Visuals

When creating PowerPoint presentations, generate images and figures for each slide, then add text separately.

**How it works:**
1. **Plan the deck**: Create content plan for each slide
2. **Generate visuals**: Use `generate_slide_image.py --visual-only` to create images for slides
3. **Build PPTX**: Use PPTX creation tools to build slides with generated visuals and separate text

**Generate Visuals:**
```bash
# Generate a figure for the introduction slide
python scripts/generate_slide_image.py "Professional illustration showing machine learning applications. Modern flat design, colorful icons on white background." -o figures/ml_applications.png --visual-only

# Generate a diagram for the methods slide
python scripts/generate_slide_image.py "Neural network architecture diagram. Clean, technical style with node connections. Blue and gray color scheme." -o figures/neural_network.png --visual-only
```

## Presentation Structure Guidelines

**Conference Presentation (10-15 minutes):**
- Title slide
- 1-2 background/context slides
- 1 methods slide (high-level)
- 3-4 results slides (the core story)
- 1 discussion/implications slide
- 1 conclusion/future work slide
- Acknowledgments (optional)

**Seminar (45-60 minutes):**
- More background and motivation
- Detailed methods
- Comprehensive results
- Broader discussion and future directions
- Time for questions

**Thesis Defense:**
- Comprehensive background
- Detailed methods
- Full results
- Critical discussion of limitations
- Clear contributions and future work

---

# Part 2: Research Posters

## Overview

Research posters are a critical medium for scientific communication at conferences, symposia, and academic events. This section covers end-to-end poster creation: package selection, layout, typography, color schemes, figure integration, and quality control for print and digital display.

## When to Use Posters

- Creating research posters for conferences or poster sessions
- Designing academic posters for university events or thesis defenses
- Converting scientific papers into poster format
- Preparing visual summaries of research for public engagement

## AI-Powered Visual Element Generation

**STANDARD WORKFLOW: Generate ALL major visual elements using AI before creating the LaTeX poster.**

This is the recommended approach:
1. Plan all visual elements needed (title, intro, methods, results, conclusions)
2. Generate each element using scientific-illustration skill (auto-detects best backend)
3. Assemble generated images in the LaTeX template
4. Add text content around the visuals

**Target: 60-70% of poster area should be AI-generated visuals, 30-40% text.**

## Critical: Preventing Content Overflow

**⚠️ POSTERS MUST NOT HAVE TEXT OR CONTENT CUT OFF AT EDGES.**

### Prevention Rules

**1. Limit Content Sections (MAXIMUM 5-6 sections for A0):**
- Title/Header
- Introduction/Problem
- Methods
- Results (1-2 key findings)
- Conclusions

**2. Set Safe Margins in LaTeX:**
```latex
% tikzposter - add generous margins
\documentclass[25pt, a0paper, portrait, margin=25mm]{tikzposter}

% baposter - ensure content doesn't touch edges
\begin{poster}{
  columns=3,
  colspacing=2em,
  headerheight=0.1\textheight
}
```

**3. Figure Sizing - Never 100% Width:**
```latex
\includegraphics[width=0.85\linewidth]{figure.png}  % NOT 1.0\linewidth
```

**4. Word Count Limits:**
- **A0 poster**: 300-800 words MAXIMUM
- **Per section**: 50-100 words maximum
- **If you have more content**: Cut it or make a handout

## Critical: Poster-Size Font Requirements

**⚠️ ALL text within AI-generated visualizations MUST be poster-readable.**

When generating graphics for posters, include font size specifications in EVERY prompt. Poster graphics are viewed from 4-6 feet away, so text must be LARGE.

**MANDATORY prompt requirements for EVERY poster graphic:**

```
POSTER FORMAT REQUIREMENTS (STRICTLY ENFORCE):
- ABSOLUTE MAXIMUM 3-4 elements per graphic (3 is ideal)
- ABSOLUTE MAXIMUM 10 words total in the entire graphic
- ALL text GIANT BOLD (80pt+ for labels, 120pt+ for key numbers)
- High contrast ONLY (dark on white OR white on dark)
- MANDATORY 50% white space minimum
- Thick lines only (5px+ minimum), large icons (200px+ minimum)
- ONE SINGLE MESSAGE per graphic
```

**Font size reference for poster prompts:**
| Element | Minimum Size | Prompt Keywords |
|---------|--------------|-----------------|
| Main numbers/metrics | 72pt+ | "huge", "giant", "poster-size" |
| Section titles | 60pt+ | "large bold", "prominent" |
| Labels/captions | 36pt+ | "readable from 6 feet" |
| Body text | 24pt+ | "poster-readable", "large text" |

---

## LaTeX Poster Deep Guide

For researchers creating posters with LaTeX, three major packages are available:

| Package | Architecture | Best For | Learning Curve |
|---------|-------------|----------|---------------|
| **beamerposter** | Beamer extension | Traditional academic posters, institutional branding | Low (if you know Beamer) |
| **tikzposter** | TikZ-based blocks | Modern colorful designs, custom graphics | Medium |
| **baposter** | Box-based grid | Multi-column layouts, consistent spacing | Low |

### Package Selection Decision Tree
```
Start: What is your design priority?
├── Institutional branding / existing Beamer theme?
│   └── YES → beamerposter
├── Modern, colorful, custom TikZ graphics?
│   └── YES → tikzposter
├── Structured multi-column grid with minimal setup?
│   └── YES → baposter
└── Not sure → tikzposter (most flexible default)
```

### Poster Dimensions and Orientation

| Standard | Size | Region |
|----------|------|--------|
| **A0** | 841 × 1189 mm | Europe (most common) |
| **A1** | 594 × 841 mm | Europe (smaller venues) |
| **36 × 48 in** | 914 × 1219 mm | North America (standard) |
| **42 × 56 in** | 1067 × 1422 mm | North America (large) |

Orientation: Portrait (vertical) is most common. Landscape works better for timelines or wide figures.

### Typography Rules for Posters

| Element | Size Range | Purpose |
|---------|-----------|---------|
| Title | 72–120 pt | Readable from 15+ feet |
| Section headers | 48–72 pt | Readable from 8–10 feet |
| Body text | 24–36 pt | Readable from 4–6 feet |
| Captions | 20–28 pt | Readable from 3 feet |

- Use **sans-serif** fonts (Helvetica, Calibri, Arial)
- Limit to **2–3 font families** maximum
- Avoid italics; use bold for emphasis

### Layout Strategy by Content

| Poster Content | Columns | Strategy |
|---------------|---------|----------|
| Few key results, large figures | 2 | Wide figure panels, brief text |
| Balanced text and figures | 3 | Standard academic layout |
| Data-heavy with many small figures | 4 | Compact grid |
| Narrative flow / timeline | 2 landscape | Left-to-right story |

### Content vs Visual Balance

| Poster Type | Text % | Visual % | Word Count |
|-------------|--------|----------|------------|
| Experimental research | 40% | 60% | 400–600 |
| Computational/modeling | 50% | 50% | 500–700 |
| Review/survey | 55% | 45% | 600–800 |
| Method paper | 35% | 65% | 300–500 |

### Compilation and Quality Control

```bash
# Basic compilation
pdflatex poster.tex

# With bibliography
pdflatex poster.tex && bibtex poster && pdflatex poster.tex && pdflatex poster.tex

# Better font support
lualatex poster.tex
```

**Quality control commands:**
```bash
# Verify page dimensions (A0 should show ~2384 × 3370 points)
pdfinfo poster.pdf | grep "Page size"

# Check font embedding (all "yes" in "emb" column)
pdffonts poster.pdf

# Check image resolution (all ≥300 DPI)
pdfimages -list poster.pdf

# Compress for email (<10MB)
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 \
   -dPDFSETTINGS=/printer -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=poster_compressed.pdf poster.pdf
```

### LaTeX Poster Best Practices

1. **Every poster must include at least 2 figures.** Posters are primarily visual — text-heavy posters fail to communicate.
2. **Verify poster dimensions match conference requirements exactly.** Use `pdfinfo poster.pdf | grep "Page size"` after compilation.
3. **Follow the Z-pattern reading flow.** Place the most important content in the top-left quadrant.
4. **Use white space intentionally.** White space is not wasted space — it improves readability.
5. **Keep text scannable.** Use bullet points instead of paragraphs. Each section understandable in under 30 seconds.
6. **Anti-pattern**: Cramming the full paper into poster format. A poster is not a shrunken paper. Extract 1–3 key messages.
7. **Test readability at reduced scale.** Print at 25% scale on letter/A4. If the title isn't readable from 6 feet, revise.
8. **Embed all fonts.** Run `pdffonts poster.pdf` — every font should show "yes" in the "emb" column.
9. **Include QR codes** for supplementary materials (full paper DOI, GitHub, data). Minimum 2 × 2 cm for reliable scanning.

## Poster Best Practices (General)

1. **Clarity over complexity** — Simplify, remove unnecessary elements
2. **Consistent styling** — Use templates and style files
3. **Colorblind accessibility** — Use Okabe-Ito palette, redundant encoding
4. **Appropriate typography** — Sans-serif fonts, minimum 24pt body text
5. **Vector format** — Use PDF for output
6. **Test readability** — Print test page, verify text readability from 3-6 feet

---

# Part 3: Integration with Other Skills

This skill works synergistically with:
- **scientific-illustration** — Generate diagrams, schematics, and visual elements for slides and posters
- **scientific-visualization** — Create data figures and plots to include in presentations
- **scientific-manuscript** — Extract content, figures, and citations from written papers
- **scientific-grant-writing** — Adapt grant proposals into pitch presentations

---

# Part 4: Resources and References

### Slides
- `references/slide_design_principles.md` — Slide design principles and templates
- `references/presentation_structure.md` — Presentation structure guides
- `scripts/generate_slide_image.py` — Slide generation (auto-detects backend: API / PPTX / Spec)
- `scripts/slides_to_pdf.py` — Combine slides into PDF

### Posters
- `assets/beamerposter_template.tex` — LaTeX poster template
- `assets/baposter_template.tex` — baposter LaTeX template
- `assets/tikzposter_template.tex` — tikzposter LaTeX template
- `references/latex_poster_packages.md` — LaTeX poster packages guide
- `references/poster_design_principles.md` — Poster design best practices

### External Resources
- Nature Figure Guidelines: https://www.nature.com/nature/for-authors/final-submission
- Science Figure Guidelines: https://www.science.org/content/page/instructions-preparing-initial-manuscript
