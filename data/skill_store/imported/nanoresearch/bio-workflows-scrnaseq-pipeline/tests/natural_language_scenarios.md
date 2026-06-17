# Natural Language Interaction Test Scenarios

These scenarios test how the skill behaves when invoked through natural language prompts. Each scenario simulates a realistic user-agent conversation.

**Test Data**: `samplesheet_2patients.csv` (PA08 + PA12, PDAC scRNA-seq)

---

## Scenario 1: "Analyze my single-cell data"

### User Prompt
> "I have two PDAC single-cell samples in a SampleSheet. Please run the full scRNA-seq pipeline on them."

### Expected Agent Behavior

1. **Format Detection**: Agent recognizes `.csv` as SampleSheet
2. **Path Setup**: Agent sources pipeline scripts and sets `data_path` to the SampleSheet
3. **Mode Selection**: Agent defaults to `interactive` mode (user wants control)
4. **Tissue Hint**: Agent asks user for tissue type, or infers from context (PDAC = Pancreas)

```python
# Agent executes
from run_pipeline import run_pipeline

result = run_pipeline(
    data_path="tests/samplesheet_2patients.csv",
    output_dir="results_PDAC",
    mode="interactive",
    batch_col="sample_id",
    tissue="Pancreas",
    use_llm=True,
)
```

### Step-by-Step Interaction

#### Step 1: Load Data
```
Agent: Loaded 2 samples from SampleSheet:
  - PA08: 25,524 cells (High_NI)
  - PA12: 14,990 cells (Low_NI)
  Total: 40,514 cells x 29,057 genes
```

#### Step 2: QC Filtering (D2 — Critical Decision Point)
```
Agent: ┌─────────────── QC Proposal ──────────────┐
Agent: │ n_genes_by_counts: 200 - 7284              │
Agent: │ total_counts_min: 500                      │
Agent: │ pct_counts_mt_max: 15.0%                   │
Agent: │                                           │
Agent: │ Justification: MT% median = 6.2% (low,    │
Agent: │ likely clean sample). Stringent threshold  │
Agent: │ OK.                                       │
Agent: │                                           │
Agent: │ Estimated removal: ~8.5% cells            │
Agent: └───────────────────────────────────────┘

[LLM Diagnostic Card] Step 2: QC Filtering
Data Snapshot: 40,514 cells, MT% median 6.2%, 95th pct 12.8%
...
LLM Analysis: The MT% distribution is consistent with pancreatic tissue.
Removal rate of 8.5% is reasonable. No red flags detected.

Agent: Does this look good? (Type 'yes' to proceed, or suggest changes)
```

#### User Response Variations

**A. User confirms**
> "Looks good, proceed"

**B. User wants to adjust**
> "Make MT% threshold 20% instead"

Agent: Updating MT% threshold to 20.0%...

**C. User asks for justification**
> "Why is the MT% threshold 15%?"

Agent: The MT% median across both samples is 6.2%, which is relatively low. 
The 95th percentile is 12.8%. A 15% threshold captures >95% of cells while 
removing clear outliers. For pancreatic tissue (which can have high stress 
during dissociation), 15-20% is typical.

#### Step 3-4: Doublet + Normalization
```
Agent: Doublet Detection: ~3.2% doublets detected (1,297 cells removed)
Agent: Normalization: Log1p normalization complete. 2,000 HVGs selected.
```

#### Step 5: Integration Decision (D3 — Critical Decision Point)
```
Agent: ┌─────────── Integration Decision ───────────┐
Agent: │ Batches detected: 2 (PA08, PA12)              │
Agent: │ Batch mixing score: 0.68 (strong effect)      │
Agent: │ Recommendation: INTEGRATE with harmony        │
Agent: │ Justification: Strong batch effect detected.  │
Agent: │ Integration strongly recommended.             │
Agent: └───────────────────────────────────────┘

[LLM Diagnostic Card] Step 5: Batch Integration Decision [CRITICAL]
...
LLM Analysis Task: The batch mixing score of 0.68 indicates strong batch 
effects. Harmony is appropriate for 2 batches and ~37k cells. Integration 
should be applied to avoid biology-batch confounding.

Agent: Should I integrate with Harmony, or would you prefer a different method?
```

#### Step 6-8: Clustering, Markers, Annotation
```
Agent: Clustering: 14 clusters at resolution 0.8 (default)
Agent: Markers: 342 markers detected (avg 24.4 per cluster)
Agent: Annotation: CellTypist complete. 8 cell types assigned (91.2%)
```

---

## Scenario 2: "Compare high vs low neural invasion"

### User Prompt
> "I have PDAC samples with and without neural invasion. Can you analyze them 
> separately first, then together with batch correction? I want to see if there 
> are cell-type differences between High_NI and Low_NI."

### Expected Agent Behavior

Agent runs the pipeline with `condition` column preserved, then suggests 
differential abundance analysis after annotation.

```python
result = run_pipeline(
    data_path="tests/samplesheet_2patients.csv",
    output_dir="results_PDAC_NI",
    mode="interactive",
    batch_col="sample_id",
    tissue="Pancreas",
    use_llm=True,
)

# After pipeline: suggest downstream analysis
# "Would you like to compare cell-type proportions between High_NI and Low_NI?"
```

---

## Scenario 3: User interrupts with questions

### Step 2: QC
> "Wait, I know PDAC samples often have high MT%. Are you sure 15% is enough?"

Agent: Good point. Pancreatic tissue does have high mitochondrial content 
due to dissociation stress. Let me check the distribution more carefully...

Agent: MT% distribution:
  - PA08: median 5.8%, q95 = 14.2%
  - PA12: median 6.5%, q95 = 13.1%
  - Combined: median 6.2%, q95 = 12.8%

Agent: For PDAC, 15% is conservative. If you're concerned about losing 
stressed but viable cells, I can raise to 20%. Would you like me to do that?

> "Yes, raise to 20%"

Agent: Updated threshold: MT% < 20%. Estimated removal: ~5.2% cells.

---

## Scenario 4: Auto mode with natural language

### User Prompt
> "Just run everything with defaults. I trust the pipeline."

### Expected Agent Behavior

Agent switches to `mode="auto"`, runs full pipeline, then presents summary.

```python
result = run_pipeline(
    data_path="tests/samplesheet_2patients.csv",
    output_dir="results_PDAC_auto",
    mode="auto",
    batch_col="sample_id",
    tissue="Pancreas",
    use_llm=True,  # Still generates diagnostic cards for review
)
```

```
Agent: Pipeline complete! Here's the summary:

┌─────────────── Pipeline Summary ──────────────┐
│ Input:  40,514 cells (2 samples)                     │
│ QC:     37,124 cells retained (8.4% removed) PASS    │
│ Doublet: 1,189 removed (3.2%) PASS                   │
│ Normalize: Log1p, 2,000 HVGs PASS                    │
│ Integrate: Harmony (2 batches) PASS                  │
│ Cluster: 14 clusters at res=0.8 PASS                 │
│ Markers: 342 total (24.4 avg/cluster) PASS           │
│ Annotate: 8 cell types, 91.2% assigned PASS          │
└───────────────────────────────────────┘

Results saved to: results_PDAC_auto/
LLM diagnostic cards saved to: results_PDAC_auto/llm_reports/

Would you like me to:
1. Show the top markers per cluster?
2. Compare cell types between High_NI and Low_NI?
3. Generate QC plots?
```

---

## Scenario 5: Error recovery

### User Prompt
> "Run the pipeline but skip annotation — I want to do that manually later."

### Expected Agent Behavior

Agent runs steps 1-7, then stops. Or runs full pipeline but notes the skip.

```python
# Option A: Run steps individually
adata = load_data("tests/samplesheet_2patients.csv")
adata = run_qc_step(adata, auto=True)["obj"]
adata = run_doublet_step(adata, auto=True)["obj"]
adata = run_normalization_step(adata, auto=True)["obj"]
adata = run_integration_step(adata, batch_col="sample_id", auto=True)["obj"]
adata = run_clustering_step(adata, auto=True)["obj"]
adata = run_marker_step(adata, auto=True)["obj"]

# Save intermediate result for manual annotation
adata.write("results_PDAC_no_annot/adata_clustered_marked.h5ad")

Agent: Stopped after marker detection. Object saved with clusters and markers.
You can annotate manually and then run:
  result = resume_pipeline(adata, from_step=8)
```

---

## Test Execution

To run these scenarios programmatically (non-blocking):

```bash
cd tests
python test_natural_language_interaction.py
```

This script simulates the interactive flow with `auto=False` but without 
blocking for user input, printing all proposals and diagnostic cards.
