---
name: scientific-literature-review
description: "Comprehensive scientific literature review and research synthesis. Combines systematic review methodology, multi-database literature search (PubMed, arXiv, bioRxiv, medRxiv), autonomous deep research, knowledge synthesis, and multi-agent analysis. Produces structured reports with verified citations in multiple academic styles."
allowed-tools: [Read, Write, Edit, Bash]
---

# Scientific Literature Review

## Overview

Conduct comprehensive, systematic literature reviews following rigorous academic methodology. This skill integrates multiple research capabilities:

1. **Systematic Review Methodology** — PICO framing, PRISMA workflows, screening, quality assessment, and thematic synthesis
2. **Multi-Database Literature Search** — Simultaneous search across PubMed, arXiv, bioRxiv, medRxiv with semantic and Boolean search strategies
3. **Autonomous Deep Research** — Multi-step query decomposition, source evaluation, and structured report generation
4. **Knowledge Synthesis** — Cross-source deduplication, confidence scoring, and coherent narrative construction
5. **Multi-Agent Analysis** — Parallelized research swarm for exhaustive topic coverage (when needed)

Search multiple literature databases, synthesize findings thematically, verify all citations for accuracy, and generate professional output documents in markdown and PDF formats.

## When to Use This Skill

Use this skill when:
- Conducting a systematic literature review for research or publication
- Synthesizing current knowledge on a specific topic across multiple sources
- Performing meta-analysis or scoping reviews
- Writing the literature review section of a research paper or thesis
- Investigating the state of the art in a research domain
- Identifying research gaps and future directions
- Requiring verified citations and professional formatting
- Executing comprehensive research on medical, biological, or technical topics

## Visual Enhancement with Scientific Illustration

**Recommended visual elements:** Literature reviews benefit from clear visual summaries. Before finalizing any document:
1. Generate at minimum ONE schematic or diagram (e.g., PRISMA flow diagram for systematic reviews)
2. Prefer 2-3 figures for comprehensive reviews (search strategy flowchart, thematic synthesis diagram, conceptual framework)

**How to generate figures:**
- Use the **scientific-illustration** skill to generate AI-powered publication-quality diagrams
- Simply describe your diagram in natural language

**When to add illustrations:**
- PRISMA flow diagrams for systematic reviews
- Literature search strategy flowcharts
- Thematic synthesis diagrams
- Research gap visualization maps
- Citation network diagrams
- Conceptual framework illustrations

---

# Part 1: Core Review Methodology

## Phase 1: Planning and Scoping

1. **Define Research Question**: Use PICO framework (Population, Intervention, Comparison, Outcome) for clinical/biomedical reviews
   - Example: "What is the efficacy of CRISPR-Cas9 (I) for treating sickle cell disease (P) compared to standard care (C)?"

2. **Establish Scope and Objectives**:
   - Define clear, specific research questions
   - Determine review type (narrative, systematic, scoping, meta-analysis)
   - Set boundaries (time period, geographic scope, study types)

3. **Develop Search Strategy**:
   - Identify 2-4 main concepts from research question
   - List synonyms, abbreviations, and related terms for each concept
   - Plan Boolean operators (AND, OR, NOT) to combine terms
   - Select minimum 3 complementary databases

4. **Set Inclusion/Exclusion Criteria**:
   - Date range (e.g., last 10 years: 2015-2024)
   - Language (typically English, or specify multilingual)
   - Publication types (peer-reviewed, preprints, reviews)
   - Study designs (RCTs, observational, in vitro, etc.)
   - Document all criteria clearly

## Phase 2: Systematic Literature Search

### Multi-Database Search Strategy

Select databases appropriate for the domain:

**Biomedical & Life Sciences:**
- Use `gget` skill: `gget search pubmed "search terms"` for PubMed/PMC
- Use `gget` skill: `gget search biorxiv "search terms"` for preprints
- Use `bioservices` skill for ChEMBL, KEGG, UniProt, etc.

**General Scientific Literature:**
- Search arXiv via direct API (preprints in physics, math, CS, q-bio)
- Search Semantic Scholar via API (200M+ papers, cross-disciplinary)
- **Search OpenAlex** (250M+ works, all disciplines, free no-auth REST API):
  ```python
  import requests, time
  BASE = "https://api.openalex.org"
  MAILTO = "your@email.com"  # polite pool for priority processing

  def search_openalex(query, year_from, year_to, max_results=200):
      """Paginate OpenAlex results and return DataFrame."""
      all_results, cursor = [], "*"
      filters = f"publication_year:{year_from}-{year_to}"
      while len(all_results) < max_results:
          r = requests.get(f"{BASE}/works",
                           params={"search": query, "filter": filters,
                                   "per_page": 200, "cursor": cursor,
                                   "mailto": MAILTO,
                                   "select": "id,doi,title,publication_year,cited_by_count,open_access"})
          r.raise_for_status()
          data = r.json()
          all_results.extend(data["results"])
          cursor = data["meta"].get("next_cursor")
          if not cursor:
              break
          time.sleep(0.1)
      return all_results[:max_results]

  # Example: drug repurposing papers 2019-2024
  papers = search_openalex("drug repurposing machine learning", 2019, 2024, 200)
  print(f"Retrieved {len(papers)} papers")
  ```
  - OpenAlex provides citation counts, open-access URLs, author ORCIDs, and concept tags
  - Use for cross-disciplinary topics (AI + biology, physics + medicine) where PubMed coverage is limited
  - Retrieve citation networks: `referenced_works` and `cited_by_count` for bibliometric analysis
  - Reconstruct abstracts from inverted index when available

**Specialized Databases:**
- Use `gget alphafold` for protein structures
- Use `gget cosmic` for cancer genomics
- Use `datacommons-client` for demographic/statistical data

### Document Search Parameters

```markdown
## Search Strategy

### Database: PubMed
- **Date searched**: 2024-10-25
- **Date range**: 2015-01-01 to 2024-10-25
- **Search string**:
  ```
  ("CRISPR"[Title] OR "Cas9"[Title])
  AND ("sickle cell"[MeSH] OR "SCD"[Title/Abstract])
  AND 2015:2024[Publication Date]
  ```
- **Results**: 247 articles
```

Repeat for each database searched.

### Export and Aggregate Results

```bash
python scripts/search_databases.py combined_results.json \
  --deduplicate \
  --format markdown \
  --output aggregated_results.md
```

## Phase 3: Screening and Selection

1. **Deduplication**:
   ```bash
   python scripts/search_databases.py results.json --deduplicate --output unique_results.json
   ```
   - Removes duplicates by DOI (primary) or title (fallback)
   - Document number of duplicates removed

2. **Title Screening** → **Abstract Screening** → **Full-Text Screening**
   - Apply inclusion/exclusion criteria rigorously at each stage
   - Document reasons for exclusion

3. **Create PRISMA Flow Diagram**:
   ```
   Initial search: n = X
   ├─ After deduplication: n = Y
   ├─ After title screening: n = Z
   ├─ After abstract screening: n = A
   └─ Included in review: n = B
   ```

## Phase 4: Data Extraction and Quality Assessment

1. **Extract Key Data**: study metadata, design, sample size, key findings, limitations, funding
2. **Assess Study Quality**:
   - **RCTs**: Cochrane Risk of Bias tool
   - **Observational studies**: Newcastle-Ottawa Scale
   - **Systematic reviews**: AMSTAR 2
3. **Organize by Themes**: Identify 3-5 major themes across studies

## Phase 5: Synthesis and Analysis

1. **Create Review Document** from template:
   ```bash
   cp assets/review_template.md my_literature_review.md
   ```

2. **Write Thematic Synthesis** (NOT study-by-study):
   - Organize Results section by themes or research questions
   - Synthesize findings across multiple studies within each theme
   - Compare and contrast different approaches
   - Identify consensus and controversies

3. **Critical Analysis**:
   - Evaluate methodological strengths and limitations
   - Assess quality and consistency of evidence
   - Identify knowledge gaps
   - Propose future research directions

---

# Part 2: Deep Research and Synthesis

## Autonomous Deep Research Workflow

For topics requiring exhaustive investigation beyond standard systematic review:

### Step 1: Query Decomposition

Break the research question into 3–5 sub-questions covering:
- Core definition / mechanism
- Current evidence / state of the art
- Debates, limitations, or contradictions
- Clinical / practical implications (if medical)
- Recent developments (last 1–2 years)

### Step 2: Multi-Source Search

Run searches across complementary sources:

**Search order:**
1. PubMed (if medical/biomedical) — peer-reviewed evidence
2. Multi-search-engine (Bing, Google, DuckDuckGo) — guidelines, reviews, news
3. Wikipedia — background and structured overviews
4. Agent browser — full articles, PDFs, clinical guidelines

### Step 3: Source Evaluation

For each source note:
- Publication type (RCT, meta-analysis, guideline, review, news)
- Date (prefer sources within 5 years for medical topics)
- Authority (journal impact, organization credibility)
- Relevance to the specific sub-question

### Step 4: Cross-Source Synthesis

Transform raw results into a coherent narrative:

**Deduplication:**
- Merge same information from different sources
- Prefer: most complete version > most authoritative source > most recent version
- Keep separate when: different conclusions, different viewpoints, meaningful evolution

**Synthesis principles:**
- Identify points of consensus
- Surface contradictions or conflicting evidence explicitly
- Note knowledge gaps
- Distinguish strongest evidence from weak/preliminary evidence
- Lead with the answer, not the search process
- Group by topic, not by source

### Step 5: Structured Report

Produce a well-formatted Markdown report:

```markdown
# [Topic] — Literature Review Report

## Summary
2–3 sentence executive summary of key findings.

## Background
Core definitions, mechanisms, or context.

## Current Evidence
Organized by sub-question or theme.

## Key Debates / Open Questions
Where do experts disagree? What is still unknown?

## Clinical / Practical Implications
What should practitioners know?

## Recent Developments
Notable advances from the past 12–24 months.

## Sources
Numbered list of all sources with titles, URLs/DOIs, and dates.
```

## Medical Research Guidelines

When researching medical topics:
- **Prioritize evidence hierarchy**: Systematic reviews > RCTs > Cohort studies > Case reports > Expert opinion
- **Include safety information**: Drug interactions, contraindications, adverse effects
- **Note population specifics**: Pediatric vs. adult, special populations, comorbidities
- **Flag regulatory status**: FDA/EMA approval status, off-label use
- **Cite clinical guidelines**: NICE, AHA, ACC, IDSA, WHO guidelines where relevant
- **Distinguish mechanistic from clinical evidence**: Lab/animal data ≠ human evidence

## Depth Levels

Adapt depth to user request:
- **Quick overview**: 3–5 sources, 1-page summary
- **Standard research** (default): 8–15 sources, full structured report
- **Comprehensive review**: 20+ sources, deep synthesis with evidence grading
- **Swarm research** (for exhaustive coverage): Deploy multi-agent parallel search for >50 citations

---

# Part 3: Citation Management and Output

## Phase 6: Citation Verification

**CRITICAL**: All citations must be verified for accuracy.

```bash
python scripts/verify_citations.py my_literature_review.md
```

This script:
- Extracts all DOIs from the document
- Verifies each DOI resolves correctly
- Retrieves metadata from CrossRef
- Generates verification report
- Outputs properly formatted citations

## Phase 7: Document Generation

**Generate PDF:**
```bash
python scripts/generate_pdf.py my_literature_review.md \
  --citation-style nature \
  --output my_review.pdf
```

Options:
- `--citation-style`: apa, nature, chicago, vancouver, ieee
- `--no-toc`: Disable table of contents
- `--no-numbers`: Disable section numbering

### Citation Style Quick Reference

**APA (7th Edition)**
- In-text: (Smith et al., 2023)
- Reference: Smith, J. D., Johnson, M. L., & Williams, K. R. (2023). Title. *Journal*, *22*(4), 301-318. https://doi.org/10.xxx/yyy

**Nature**
- In-text: Superscript numbers^1,2^
- Reference: Smith, J. D., Johnson, M. L. & Williams, K. R. Title. *Nat. Rev. Drug Discov.* **22**, 301-318 (2023).

**Vancouver**
- In-text: Superscript numbers^1,2^
- Reference: Smith JD, Johnson ML, Williams KR. Title. Nat Rev Drug Discov. 2023;22(4):301-18.

## Quality Checklist

- [ ] All DOIs verified with verify_citations.py
- [ ] Citations formatted consistently
- [ ] PRISMA flow diagram included (for systematic reviews)
- [ ] Search methodology fully documented
- [ ] Inclusion/exclusion criteria clearly stated
- [ ] Results organized thematically (not study-by-study)
- [ ] Quality assessment completed
- [ ] Limitations acknowledged
- [ ] References complete and accurate
- [ ] At least 1-2 AI-generated illustrations included
- [ ] PDF generates without errors

---

# Part 4: Best Practices and Integration

## Search Best Practices

1. **Use multiple databases** (minimum 3): Ensures comprehensive coverage
2. **Include preprint servers**: Captures latest unpublished findings
3. **Document everything**: Search strings, dates, result counts for reproducibility
4. **Test and refine**: Run pilot searches, review results, adjust search terms
5. **Citation chaining**: Use forward and backward citations to expand coverage

## Common Pitfalls to Avoid

1. **Single database search**: Misses relevant papers
2. **No search documentation**: Makes review irreproducible
3. **Study-by-study summary**: Lacks synthesis; organize thematically
4. **Unverified citations**: Leads to errors
5. **Too broad/too narrow search**: Balance specificity with coverage
6. **Ignoring preprints**: Misses latest findings
7. **No quality assessment**: Treats all evidence equally
8. **Publication bias**: Only positive results published; note potential bias

## Integration with Other Skills

- **scientific-ideation**: Identify research gaps and generate new hypotheses
- **scientific-research-design**: Translate findings into testable experiments
- **scientific-manuscript**: Embed literature review into paper sections
- **scientific-illustration**: Generate PRISMA diagrams and conceptual figures
- **scientific-visualization**: Create evidence summary plots and forest plots

## Resources

### Bundled Resources

**Scripts:**
- `scripts/verify_citations.py`: Verify DOIs and generate formatted citations
- `scripts/generate_pdf.py`: Convert markdown to professional PDF
- `scripts/search_databases.py`: Process, deduplicate, and format search results

**Assets:**
- `assets/review_template.md`: Complete literature review template

**References:**
- `references/citation_styles.md`: Detailed citation formatting guide
- `references/database_strategies.md`: Comprehensive database search strategies

### External Resources

- PRISMA (Systematic Reviews): http://www.prisma-statement.org/
- Cochrane Handbook: https://training.cochrane.org/handbook
- AMSTAR 2: https://amstar.ca/
- MeSH Browser: https://meshb.nlm.nih.gov/search

## Dependencies

```bash
pip install requests  # For citation verification
# pandoc and xelatex for PDF generation
```
