#!/usr/bin/env nextflow

nextflow.enable.dsl = 2

params {
}

process qc {
    input:
        val phase_input
    output:
        path 'result.json'
    script:
    """
    echo 'Placeholder process for phase: qc'
    python << 'PYEOF'
    import json
    result = {'phase': 'qc', 'status': 'ok'}
    with open('result.json', 'w') as f:
        json.dump(result, f)
    PYEOF
    """
}

workflow {
    inputs_ch = Channel.value(params.subMap([]))
    qc(inputs_ch)
}
