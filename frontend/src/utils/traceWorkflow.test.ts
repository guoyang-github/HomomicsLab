import { describe, it, expect } from 'vitest'
import { extractWorkflowFromTrace } from './traceWorkflow'

/**
 * Trace node shapes mirrored by the backend
 * (orchestrator_executors._trace_workflow_event):
 * - plan node:  node_type "plan",  name "workflow_skeleton:<domain>",
 *               metadata { event: "workflow_skeleton", domain, phases, task_id }
 * - phase node: node_type "phase", name "phase:<phase>:<status>",
 *               metadata { event: "phase", phase, status, params, task_id }
 */
function makeTraceNodes() {
  return [
    // Trace root: also node_type "plan" but carries no metadata.event.
    { node_id: 'root', node_type: 'plan', name: 'job', status: 'completed', metadata: {} },
    {
      node_id: 'skel_1',
      node_type: 'plan',
      name: 'workflow_skeleton:single-cell-transcriptomics',
      status: 'running',
      metadata: {
        event: 'workflow_skeleton',
        domain: 'single-cell-transcriptomics',
        phases: [
          { phase_type: 'qc', name: 'Quality Control', skipped: false },
          { phase_type: 'doublet', name: 'Doublet Detection', skipped: true },
          { phase_type: 'normalization', name: 'Normalization', skipped: false },
        ],
        task_id: 'task_1',
      },
    },
    // Per-task trace node: node_type "phase" with metadata.phase but no event.
    { node_id: 't1', node_type: 'phase', name: 'QC step', status: 'completed', metadata: { phase: 'qc', task_id: 'task_1' } },
    {
      node_id: 'p1',
      node_type: 'phase',
      name: 'phase:qc:start',
      status: 'running',
      metadata: { event: 'phase', phase: 'qc', status: 'start', params: null, task_id: 'task_1' },
    },
    {
      node_id: 'p2',
      node_type: 'phase',
      name: 'phase:qc:done',
      status: 'running',
      metadata: { event: 'phase', phase: 'qc', status: 'done', params: { min_genes: 200 }, task_id: 'task_1' },
    },
    {
      node_id: 'p3',
      node_type: 'phase',
      name: 'phase:normalization:failed',
      status: 'running',
      metadata: { event: 'phase', phase: 'normalization', status: 'failed', task_id: 'task_1' },
    },
  ]
}

describe('extractWorkflowFromTrace', () => {
  it('extracts the skeleton and phase markers from mirrored trace nodes', () => {
    const { skeleton, phaseEvents } = extractWorkflowFromTrace(makeTraceNodes())

    expect(skeleton).toEqual({
      domain: 'single-cell-transcriptomics',
      phases: [
        { phase_type: 'qc', name: 'Quality Control', skipped: false },
        { phase_type: 'doublet', name: 'Doublet Detection', skipped: true },
        { phase_type: 'normalization', name: 'Normalization', skipped: false },
      ],
    })
    expect(phaseEvents).toEqual([
      { phase: 'qc', status: 'start', params: undefined },
      { phase: 'qc', status: 'done', params: { min_genes: 200 } },
      { phase: 'normalization', status: 'failed', params: undefined },
    ])
  })

  it('returns nothing when the trace has no mirrored workflow nodes', () => {
    const nodes = [
      { node_id: 'root', node_type: 'plan', name: 'job', metadata: {} },
      { node_id: 't1', node_type: 'phase', name: 'QC step', metadata: { phase: 'qc', task_id: 'task_1' } },
      { node_id: 's1', node_type: 'skill', name: 'celltypist', metadata: {} },
    ]
    const { skeleton, phaseEvents } = extractWorkflowFromTrace(nodes)
    expect(skeleton).toBeNull()
    expect(phaseEvents).toEqual([])
  })

  it('tolerates non-array input and malformed entries', () => {
    expect(extractWorkflowFromTrace(undefined)).toEqual({ skeleton: null, phaseEvents: [] })
    expect(extractWorkflowFromTrace('nope')).toEqual({ skeleton: null, phaseEvents: [] })

    const { skeleton, phaseEvents } = extractWorkflowFromTrace([
      null,
      'garbage',
      { node_type: 'plan' }, // no metadata at all
      { node_type: 'plan', metadata: { event: 'workflow_skeleton', domain: '', phases: [] } },
      { node_type: 'plan', metadata: { event: 'workflow_skeleton', domain: 'spatial' } }, // no phases
      { node_type: 'phase', metadata: { event: 'phase', phase: 'qc' } }, // no status
      { node_type: 'phase', metadata: { event: 'phase', status: 'start' } }, // no phase
      { node_type: 'phase', metadata: { event: 'phase', phase: 42, status: 'start' } },
    ])
    expect(skeleton).toBeNull()
    expect(phaseEvents).toEqual([])
  })

  it('keeps only valid phases and defaults missing name/skipped', () => {
    const { skeleton } = extractWorkflowFromTrace([
      {
        node_type: 'plan',
        metadata: {
          event: 'workflow_skeleton',
          domain: 'spatial-transcriptomics',
          phases: [
            { phase_type: 'qc' }, // no name, no skipped
            { name: 'no phase_type' },
            'garbage',
            { phase_type: 'clustering', name: 'Clustering', skipped: false },
          ],
        },
      },
    ])
    expect(skeleton).toEqual({
      domain: 'spatial-transcriptomics',
      phases: [
        { phase_type: 'qc', name: 'qc', skipped: false },
        { phase_type: 'clustering', name: 'Clustering', skipped: false },
      ],
    })
  })

  it('lets the last skeleton win when a trace holds several mirrors', () => {
    const { skeleton } = extractWorkflowFromTrace([
      {
        node_type: 'plan',
        metadata: {
          event: 'workflow_skeleton',
          domain: 'genomics',
          phases: [{ phase_type: 'qc', name: 'QC', skipped: false }],
        },
      },
      {
        node_type: 'plan',
        metadata: {
          event: 'workflow_skeleton',
          domain: 'single-cell-transcriptomics',
          phases: [{ phase_type: 'umap', name: 'UMAP', skipped: false }],
        },
      },
    ])
    expect(skeleton?.domain).toBe('single-cell-transcriptomics')
  })
})
