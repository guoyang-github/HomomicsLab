---
name: scientific-manuscript
description: "Complete scientific manuscript preparation. Write and format research papers for international journals (Nature/Cell/Science/IEEE) and Chinese journals (中国科学/科学通报/计算机学报/物理学报) using IMRAD structure, proper citations (APA/AMA/Vancouver/Nature/GB-T-7714), figures/tables, and reporting guidelines (CONSORT/STROBE/PRISMA). Includes citation management tools, statistical reporting standards, journal-specific formatting, Chinese thesis/dissertation formatting, and a two-stage writing process from outline to polished prose."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Manuscript

## Overview

This is the core skill for scientific manuscript preparation—combining AI-driven research with well-formatted written outputs. Write manuscripts using IMRAD structure, apply study-specific reporting guidelines, manage citations systematically, and format for target journals from high-impact general science to specialty clinical publications.

**Critical Principle: Always write in full paragraphs with flowing prose. Never submit bullet points in the final manuscript.** Use a two-stage process: first create section outlines with key points, then convert those outlines into complete paragraphs.

## When to Use This Skill

This skill should be used when:
- Writing or revising any section of a scientific manuscript (abstract, introduction, methods, results, discussion)
- Structuring a research paper using IMRAD or other standard formats
- Formatting citations and references in specific styles (APA, AMA, Vancouver, Nature, Chicago, IEEE, **GB/T 7714**)
- Creating, formatting, or improving figures, tables, and data visualizations
- Applying study-specific reporting guidelines (CONSORT, STROBE, PRISMA, STARD, TRIPOD, ARRIVE)
- Preparing manuscripts for submission to specific journals (**Nature, Cell, Science, Blood, 中国科学, 科学通报, 计算机学报, 物理学报,  etc.**)
- **Writing Chinese master's or doctoral dissertations (学位论文) with proper formatting**
- Searching for papers (PubMed, arXiv), verifying citations, and generating BibTeX bibliographies
- Addressing reviewer comments and revising manuscripts

## Visual Enhancement with Scientific Illustration

**Recommended visual elements:** Scientific papers benefit from schematic diagrams to complement data figures. Before finalizing any document:
1. Generate at minimum ONE schematic or diagram
2. Prefer 2-3 figures for comprehensive papers (methods flowchart, results visualization, conceptual diagram)

**How to generate figures:**
- Use the **scientific-illustration** skill to generate AI-powered publication-quality diagrams
- Simply describe your diagram in natural language

---

# Part 1: Writing Process

## The Two-Stage Writing Process

**CRITICAL: Always write in full paragraphs, never submit bullet points in scientific papers.**

Scientific papers must be written in complete, flowing prose. Use this two-stage approach for effective writing:

### Stage 1: Create Section Outlines with Key Points

When starting a new section:
1. Gather relevant literature and data
2. Create a structured outline with bullet points marking:
   - Main arguments or findings to present
   - Key studies to cite
   - Data points and statistics to include
   - Logical flow and organization
3. These bullet points serve as scaffolding—they are NOT the final manuscript

### Stage 2: Convert Key Points to Full Paragraphs

Once the outline is complete, expand each bullet point into proper prose:

1. **Transform bullet points into complete sentences** with subjects, verbs, and objects
2. **Add transitions** between sentences and ideas (however, moreover, in contrast, subsequently)
3. **Integrate citations naturally** within sentences, not as lists
4. **Expand with context and explanation** that bullet points omit
5. **Ensure logical flow** from one sentence to the next within each paragraph
6. **Vary sentence structure** to maintain reader engagement

**Common Mistakes to Avoid:**
- Never leave bullet points in the final manuscript
- Never submit lists where paragraphs should be
- Don't use numbered or bulleted lists in Results or Discussion sections
- Do ensure every section flows as connected prose

**When Lists ARE Acceptable (Limited Cases):**
- **Methods**: Inclusion/exclusion criteria, materials and reagents, participant characteristics
- **Supplementary Materials**: Extended protocols, equipment lists, detailed parameters
- **Never in**: Abstract, Introduction, Results, Discussion, Conclusions

---

# Part 2: Manuscript Structure

## IMRAD Format

### Title
- Concise (<15 words for Nature, <20 for Blood)
- Include key finding and system/disease
- Avoid jargon and abbreviations

### Abstract (100-250 words)

**Structured (for Blood/Clinical Journals):**
```markdown
**Background:** One sentence on knowledge gap.
**Methods:** Key approaches, patient cohort size, techniques.
**Results:** Primary findings with statistics (P values, CIs).
**Conclusions:** Clinical/translational significance.
```

**Unstructured:** Single coherent paragraph covering purpose, methods, results, and conclusions.

### Introduction (~500-800 words)
1. **Paragraph 1**: Broad context, disease burden, clinical relevance
2. **Paragraph 2**: Current knowledge, key mechanisms
3. **Paragraph 3**: Knowledge gap, unanswered questions
4. **Paragraph 4**: Study aims, hypothesis, approach overview

### Methods (Detailed, Reproducible)

Document all elements needed for reproducibility:

```markdown
**Patient Cohort and Samples**
- IRB approval number, consent process
- Inclusion/exclusion criteria
- Sample processing, storage conditions

**Experimental Procedures**
- Reagent details, equipment models
- Protocol steps with critical parameters
- Quality control measures

**Computational Analysis**
- Software versions (e.g., Scanpy 1.9.x, scvi-tools 0.20.x)
- QC thresholds and parameters
- Statistical methods with justification
- Code availability statement

**Statistical Analysis**
- Software (R 4.3.x, Python 3.11)
- Tests used with justification
- Multiple testing correction method
- Power analysis if applicable
```

### Results (~2000-3000 words)
- Lead each paragraph with key finding
- Reference figures in order (Figure 1A-C...)
- Report exact P values (P = 0.003, not P < 0.05)
- Include confidence intervals where relevant
- Avoid interpretation; save for Discussion

### Discussion (~1500-2000 words)

```markdown
**Paragraph 1**: Summarize key findings, relate to hypothesis

**Paragraph 2-4**: Compare to existing literature
- "Consistent with [Author et al.], we found..."
- "In contrast to [Study], our analysis revealed..."
- Mechanistic interpretation

**Paragraph 5**: Translational/Clinical implications
- Therapeutic targets
- Biomarkers
- Patient stratification

**Paragraph 6**: Limitations and Evidence Quality Assessment
- Sample size, cohort characteristics
- Technical limitations
- Generalizability
- **Critical appraisal of evidence quality** (apply these standards):
  - **Study design hierarchy**: Is the design appropriate for the claim? RCTs for intervention effectiveness, cohort studies for prognosis, case-control for rare outcomes. Flag mismatches.
  - **Effect size vs. statistical significance**: Report effect sizes (OR, RR, Cohen's d, ARR, NNT) with 95% CI, not just p-values. A p < 0.05 with trivial effect size is clinically irrelevant.
  - **Bias assessment**: Acknowledge potential selection bias, information bias (recall, observer), confounding, and reporting bias. State what was done to mitigate each.
  - **Confounding**: List major unmeasured or residual confounders that could explain the observed association.
  - **GRADE certainty**: Classify overall evidence certainty (High / Moderate / Low / Very Low). Downgrade for risk of bias, inconsistency, indirectness, imprecision, publication bias. Upgrade only for large effect (OR > 5), dose-response, or all plausible confounders would reduce the effect.
  - **Statistical vs. clinical significance**: With large samples, even trivial effects become significant. Ask: "If this effect is real, would it matter to a patient or system?"

**Paragraph 7**: Future directions and conclusion
```

---

# Part 3: Journal-Specific Formatting

## High-Impact Journal Guidelines

### Nature
- Word limit: ~3000 (Article)
- Main text figures: 6-8
- Methods: no limit, separate section
- Extended Data for supplementary figures
- Citation style: Author-Year

### Cell
- Word limit: 7000 (Article)
- STAR Methods format
- Graphical abstract required

### Blood (ASH)
- Word limit: 4000 (full article)
- Figures: 7 max
- References: 60 max
- Structured abstract: 250 words
- Citation style: Numbered (Vancouver)

## Chinese Journal Guidelines

### 《中国科学》系列 (Science China)
- Language: Chinese text + English abstract (中文刊); Full English (英文刊)
- Abstract: Chinese 300-500字, English 200-300 words
- Keywords: 3-8 (both languages)
- References: GB/T 7714 format, 20-40 recommended
- Figures: High resolution (≥300 DPI), color figures free

### 《科学通报》(Chinese Science Bulletin)
- Language: Chinese + English abstract
- Article types: Research, Reviews, Progress, Letters
- Abstract: Chinese 300-500字
- References: GB/T 7714 format

### 《计算机学报》(Journal of Computers)
- Language: Chinese + English abstract
- Word limit: ~8000 characters (excluding references)
- Abstract: Chinese 200-300字, English 150-250 words
- Keywords: 4-8 (both languages)
- References: GB/T 7714, 15-30 recommended
- Figures: Primarily black and white

### 《物理学报》(Acta Physica Sinica)
- Language: Chinese + English abstract or full English
- Abstract: Chinese 200-400字, English 200-300 words
- References: GB/T 7714 format
- Figures: High resolution, color free

### Common Requirements for Chinese Journals
- **Citation style**: GB/T 7714-2015 (mandatory)
- **Figures**: Must be readable in grayscale (many still print B&W)
- **Author format**: 3 or fewer authors listed fully; 4+ use "et al" / "等"
- **File formats**: PDF preferred; figures as separate high-res files

For detailed guidelines for each journal, see `references/chinese_journal_guidelines.md`.

## Chinese Dissertation/Thesis Formatting

### Structure
```
封面 (统一模板)
原创性声明 + 版权授权书 (签名)
中文摘要 (博士1000-1500字, 硕士500-800字)
英文摘要 (Abstract)
目录
正文 (第1章 绪论 → 研究内容 → 结论)
参考文献 (GB/T 7714)
附录 (如有)
致谢
攻读学位期间取得的研究成果
```

### Formatting Requirements
- **Font**: SimSun (宋体) for body text, SimHei (黑体) for headings
- **English/Numbers**: Times New Roman
- **Body text size**: 小四 (12pt)
- **Chapter headings**: 黑体三号 (16pt), centered
- **Section headings**: 黑体四号 (14pt)
- **Line spacing**: 1.5倍 or fixed 20-22pt
- **Margins**: Top 2.5cm, Bottom 2.2cm, Left 2.8-3.0cm, Right 2.2-2.5cm
- **Page numbers**: Arabic numerals from正文; Roman or none for front matter

### Chapter Numbering
```
第1章  ××××
  1.1  ××××
    1.1.1  ××××
```

### Figure/Table Numbering
- Format: `图1-1`, `表2-3` (chapter-sequence)
- Figure captions: below figure, centered
- Table captions: above table, centered

For complete thesis formatting guide, see `references/chinese_thesis_format.md`.

## Statistical Reporting Standards

### Continuous Variables
- Mean ± SD (normal) or Median [IQR] (non-normal)
- Report normality test used

### Categorical Variables
- N (%) with comparison test

### P Values
- Report exact values (P = 0.023)
- For very small: P < 0.0001
- Always report test used

### Sample Sizes
- "n = X patients" or "n = X cells"
- Report for each comparison group

## Figure Legends Template

```markdown
**Figure 1. Title describes main finding**
(A) Brief description of panel A. Statistical test, P value.
(B) Description including axis labels if not obvious.
(C-D) Can combine similar panels.
Scale bars: X μm. Error bars: mean ± SEM. *P < 0.05, **P < 0.01, ***P < 0.001.
n = X biological replicates from Y independent experiments.
```

## Writing Style

- Active voice preferred
- Past tense for results ("We found...")
- Present tense for established facts
- Avoid "interesting," "significant" (unless statistical)
- Be specific: "83.9-fold increase" not "marked increase"

---

# Part 4: Reporting Guidelines

Ensure completeness and transparency by following established reporting standards:

- **CONSORT**: Randomized controlled trials
- **STROBE**: Observational studies (cohort, case-control, cross-sectional)
- **PRISMA**: Systematic reviews and meta-analyses
- **STARD**: Diagnostic accuracy studies
- **TRIPOD**: Prediction model studies
- **ARRIVE**: Animal research
- **CARE**: Case reports
- **SQUIRE**: Quality improvement studies
- **SPIRIT**: Study protocols for clinical trials
- **CHEERS**: Economic evaluations

Each guideline provides checklists ensuring all critical methodological elements are reported. For comprehensive details, see `references/reporting_guidelines.md`.

---

# Part 5: Citation and Reference Management

## Core Workflow

### Phase 1: Paper Discovery

**PubMed Search:**
```bash
python scripts/search_pubmed.py "Alzheimer's disease treatment" \
  --limit 100 --output alzheimers.json
```

### Phase 2: Metadata Extraction

**Quick DOI to BibTeX:**
```bash
python scripts/doi_to_bibtex.py 10.1038/s41586-021-03819-2
```

**Comprehensive extraction (supports DOI, PMID, arXiv ID, URL):**
```bash
python scripts/extract_metadata.py --doi 10.1038/s41586-021-03819-2
python scripts/extract_metadata.py --pmid 34265844
python scripts/extract_metadata.py --arxiv 2103.14030
```

**Batch extraction:**
```bash
python scripts/extract_metadata.py --input identifiers.txt --output citations.bib
```

### Phase 3: BibTeX Formatting

```bash
# Format and clean
python scripts/format_bibtex.py references.bib --output formatted.bib

# Remove duplicates
python scripts/format_bibtex.py references.bib --deduplicate --output clean.bib

# Sort by year (newest first)
python scripts/format_bibtex.py references.bib --sort year --descending
```

### Phase 4: Citation Validation

```bash
# Validate BibTeX file
python scripts/validate_citations.py references.bib

# Auto-fix common issues
python scripts/validate_citations.py references.bib \
  --auto-fix --output validated.bib

# Generate detailed report
python scripts/validate_citations.py references.bib \
  --report validation_report.json --verbose
```

**Validation checks:**
- DOI resolves correctly via doi.org
- Required fields present for entry type
- Duplicate detection
- Valid BibTeX syntax

## Reference Manager Selection

Choose a reference manager based on your workflow:

| Feature | Zotero | Mendeley | EndNote | Paperpile |
|---------|--------|----------|---------|-----------|
| Cost | Free (open-source) | Free / paid | ~$275 | $36/year |
| LaTeX | BibTeX auto-export | Manual export | BibTeX export | Overleaf sync |
| Word | Native plugin | Native plugin | Deep integration | Google Docs only |
| Best for | Academic / LaTeX users | Beginners | Institutional labs | Google Workspace |

**Recommendation**: Zotero + Better BibTeX plugin for LaTeX/Overleaf workflows (auto-syncing `.bib`, no vendor lock-in). Paperpile for teams writing primarily in Google Docs.

**Critical workflow rules:**
1. Capture metadata from publisher pages (not PDFs) — PDF parsing frequently garbles author names and truncates lists
2. Always verify DOI resolution after import — broken DOIs are a legitimate reason for post-publication corrections
3. Store PDFs inside the reference manager (not external links) to prevent broken links on directory restructuring
4. Set citation key template BEFORE importing (e.g., `[auth:lower][year][veryshorttitle]`) — changing mid-project orphans all `\cite{}` commands
5. Organize by topic, not by manuscript — enables reuse across projects and prevents duplicate accumulation
6. Run "Find Duplicates" before every submission — duplicate entries produce inconsistent formatting
7. Export a static archive (`.bib`, `.ris`) at submission — ensures reproducibility even if your live library changes during 6–18 month review periods

## Citation Style Families

The target journal dictates the style — the author does not choose independently.

| Style | In-text | Reference list | Abbreviate journals? | Typical discipline |
|-------|---------|---------------|----------------------|--------------------|
| **APA 7th** | (Author, Year) | Alphabetical | No | Psychology, social science |
| **Vancouver** | Superscript [1] | Citation order | Yes (ISO 4) | Medicine (NEJM, Lancet, BMJ) |
| **ACS** | Superscript or (1) | Citation order | Yes (CASSI) | Chemistry |
| **Nature** | Superscript¹ | Citation order | Yes (NLM) | Nature family |
| **IEEE** | Bracketed [1] | Citation order | Yes | Engineering, CS |
| **GB/T 7714** | [1] or (Author, Year) | Citation order or alphabetical | No | Chinese journals |

**Never abbreviate journal names manually** — reference managers handle this automatically via CSL files. Manual abbreviation is a major source of errors.

**DOI format:**
- Always use `https://doi.org/10.XXXX/suffix` — bare DOI is not a clickable URL
- Do not use the old `http://dx.doi.org/` scheme
- Preprint DOIs (bioRxiv, medRxiv) are distinct from journal article DOIs — always check for peer-reviewed versions

## Citation Styles

**APA (7th Edition)**
- In-text: (Smith et al., 2023)
- Reference: Smith, J. D., Johnson, M. L., & Williams, K. R. (2023). Title. *Journal*, *22*(4), 301-318.

**AMA / Vancouver**
- In-text: Superscript numbers^1,2^
- Reference: Smith JD, Johnson ML, Williams KR. Title. *Nat Rev Drug Discov*. 2023;22(4):301-18.

**Nature**
- In-text: Superscript numbers^1,2^
- Reference: Smith, J. A., Jones, B. C. & Williams, K. R. Title. *Nature* **620**, 567–578 (2024).

**IEEE**
- In-text: [1], [2]
- Reference: [1] J. D. Smith et al., "Title," *IEEE Trans. Pattern Anal. Mach. Intell.*, vol. 45, no. 3, pp. 123–145, 2024.

**GB/T 7714-2015 (Chinese National Standard)**
- Two systems: 顺序编码制 (numeric [1]) and 著者-出版年制 (author-year)
- In-text (顺序编码制): [1], [2-4], [1,3,5-7]
- In-text (著者-出版年制): (张三等, 2020), (Li et al., 2022)
- Reference (journal): 张三, 李四, 王五. 题名[J]. 刊名, 2023, 81(5): 456-463.
- Reference (thesis): 赵六. 学位论文题名[D]. 北京: 清华大学, 2023.
- Reference (monograph): 黄昆, 韩汝琦. 固体物理学[M]. 北京: 高等教育出版社, 2020.
- Must include literature type identifier: [J], [M], [D], [C], [P], [S], etc.

For complete style guides, see `references/citation_styles.md` (Western styles) and `references/gbt7714_citation_style.md` (Chinese standard).

---

# Part 6: Figures and Tables

## When to Use Tables vs. Figures

- **Tables**: Precise numerical data, complex datasets, multiple variables requiring exact values
- **Figures**: Trends, patterns, relationships, comparisons best understood visually

## Design Principles

- Make each table/figure self-explanatory with complete captions
- Use consistent formatting and terminology across all display items
- Label all axes, columns, and rows with units
- Include sample sizes (n) and statistical annotations
- Follow the "one table/figure per 1000 words" guideline
- Avoid duplicating information between text, tables, and figures

## Common Figure Types

- Bar graphs: Comparing discrete categories
- Line graphs: Showing trends over time
- Scatterplots: Displaying correlations
- Box plots: Showing distributions and outliers
- Heatmaps: Visualizing matrices and patterns

For detailed best practices, see `references/figures_tables.md`.

---

# Part 7: Field-Specific Language and Terminology

## Biomedical and Clinical Sciences
- Use precise anatomical and clinical terminology
- Follow standardized disease nomenclature (ICD, DSM, SNOMED-CT)
- Specify drug names using generic names first
- Use "patients" for clinical studies, "participants" for community-based research
- Follow HGVS nomenclature for genetic variants
- Report lab values with SI units

## Molecular Biology and Genetics
- Use italics for gene symbols (*TP53*), regular font for proteins (p53)
- Follow species-specific gene nomenclature (human: *BRCA1*; mouse: *Brca1*)
- Specify organism names in full at first mention, then abbreviate (*Escherichia coli*, then *E. coli*)
- Use standard genetic notation (+/+, +/-, -/- for genotypes)

## Chemistry and Pharmaceutical Sciences
- Follow IUPAC nomenclature for chemical compounds
- Report concentrations with appropriate units (mM, μM, nM)
- Use terms like "bioavailability," "pharmacokinetics," "IC50" consistently

## General Principles
- Define abbreviations at first use: "messenger RNA (mRNA)"
- For specialized journals: Use field-specific terminology freely
- For broad-impact journals (*Nature*, *Science*): Define more technical terms
- Maintain consistency — use the same term for the same concept throughout

For comprehensive field-specific guidance, see `references/writing_principles.md`.

---

# Part 8: Workflow for Manuscript Development

## Stage 1: Planning
1. Identify target journal and review author guidelines
2. Determine applicable reporting guideline
3. Outline manuscript structure
4. Plan figures and tables as the backbone of the paper

## Stage 2: Drafting
1. Start with figures and tables (the core data story)
2. For each section, follow the two-stage process (outline → prose)
3. Write Methods (often easiest to draft first)
4. Draft Results (describing figures/tables objectively)
5. Compose Discussion (interpreting findings)
6. Write Introduction (setting up the research question)
7. Craft Abstract (synthesizing the complete story)
8. Create Title (concise and descriptive)

## Stage 3: Revision
1. Check logical flow and "red thread" throughout
2. Verify consistency in terminology and notation
3. Ensure figures/tables are self-explanatory
4. Confirm adherence to reporting guidelines
5. Verify all citations are accurate and properly formatted
6. Check word counts for each section
7. Proofread for grammar, spelling, and clarity

## Stage 4: Final Preparation
1. Format according to journal requirements
2. Prepare supplementary materials
3. Write cover letter highlighting significance
4. Complete submission checklists

---

# Part 9: Compliance and Common Pitfalls

## HIPAA Compliance Reminders
- No patient identifiers in any form
- Use Specimen IDs, not patient names/MRNs
- Aggregate data for small groups (n < 5)
- IRB approval statement required
- Data availability statement required

## Top Rejection Reasons
1. Inappropriate, incomplete, or insufficiently described statistics
2. Over-interpretation of results or unsupported conclusions
3. Poorly described methods affecting reproducibility
4. Small, biased, or inappropriate samples
5. Poor writing quality or difficult-to-follow text
6. Inadequate literature review or context
7. Figures and tables that are unclear or poorly designed
8. Failure to follow reporting guidelines

## Common Pitfalls to Avoid
- Mixing tenses inappropriately (past tense for methods/results, present for established facts)
- Excessive jargon or undefined acronyms
- Missing transitions between sections
- Inconsistent notation or terminology
- Unverified citations or broken DOIs

---

# Part 10: Reference Materials

## Writing and Structure
- `references/imrad_structure.md`: Detailed IMRAD guide
- `references/citation_styles.md`: Complete citation style guides
- `references/figures_tables.md`: Best practices for visualizations
- `references/reporting_guidelines.md`: Study-specific reporting standards
- `references/writing_principles.md`: Core principles of scientific communication

## Citation Management
- `references/pubmed_search.md`: PubMed and E-utilities documentation
- `references/metadata_extraction.md`: Metadata sources and requirements
- `references/citation_validation.md`: Validation criteria and quality checks
- `references/bibtex_formatting.md`: BibTeX entry types and formatting rules

### Chinese Resources
- `references/gbt7714_citation_style.md`: GB/T 7714-2015 Chinese citation standard (complete guide with examples)
- `references/chinese_journal_guidelines.md`: Submission guidelines for major Chinese journals (中国科学, 科学通报, 计算机学报, 物理学报, etc.)
- `references/chinese_thesis_format.md`: Master's and doctoral dissertation formatting requirements (学位论文格式规范)

## Scripts and Tools
- `scripts/search_pubmed.py`: PubMed E-utilities client
- `scripts/extract_metadata.py`: Universal metadata extractor
- `scripts/validate_citations.py`: Citation validation and verification
- `scripts/format_bibtex.py`: BibTeX formatter and cleaner
- `scripts/doi_to_bibtex.py`: Quick DOI to BibTeX converter

## Templates and Checklists
- `assets/bibtex_template.bib`: Example BibTeX entries
- `assets/citation_checklist.md`: Quality assurance checklist

---

## Integration with Other Skills

This skill connects to the broader research workflow:

- **scientific-literature-review** — Provides the foundational literature base, citations, and gap analysis that shape the Introduction and Discussion
- **scientific-research-design** — The experimental design determines the Methods structure and the logical flow of Results
- **scientific-visualization** — Data figures and plots created here are embedded into the manuscript's Results section
- **scientific-illustration** — Conceptual diagrams and schematics clarify methodology and frameworks in the Methods and Introduction
- **scientific-peer-review** — Apply peer-review criteria to your own manuscript before submission; this skill's checklists are a self-review tool
- **scientific-communication** — Manuscript content can be adapted into conference presentations, posters, and slide decks
