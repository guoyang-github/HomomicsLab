"""Core CodeAct skill: generate and execute code for a sub-task.

This is a rule-based implementation sufficient for the MVP CodeAct loop.
In production it is replaced by an LLM-backed code generator that receives
retrieved skill/tool/SOP context and emits executable code.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _generate_code(task: str, language: str, context: dict) -> str:
    """Generate a code snippet based on task keywords and available context."""
    task_lower = task.lower()

    # Resolve common context variables
    input_path = context.get("input_path") or context.get("adata_path") or "data/pbmc3k_raw.h5ad"
    output_path = context.get("output_path") or "output/result.h5ad"

    if language == "python":
        if any(k in task_lower for k in ("read", "load", "h5ad", "10x", "import")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
print(f"Loaded {{adata.n_obs}} cells x {{adata.n_vars}} genes")
"""
        if any(k in task_lower for k in ("qc", "filter", "quality", "mito")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
adata = adata[adata.obs.n_genes_by_counts > 200, :]
adata = adata[adata.obs.pct_counts_mt < 5, :]
adata.write("{output_path}")
print(f"QC done: {{adata.n_obs}} cells remain")
"""
        if any(k in task_lower for k in ("normalize", "normalization", "log1p")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.write("{output_path}")
print("Normalization done")
"""
        if any(k in task_lower for k in ("cluster", "clustering", "leiden", "umap", "pca")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.tl.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)
sc.tl.leiden(adata)
adata.write("{output_path}")
print("Clustering done")
"""
        if any(k in task_lower for k in ("plot", "visualize", "umap", "heatmap")):
            return f"""import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
adata = sc.read_h5ad("{input_path}")
fig, ax = plt.subplots(figsize=(6, 5))
sc.pl.umap(adata, color='leiden', ax=ax, show=False)
fig.savefig("{output_path.replace('.h5ad', '.png')}")
print("Plot saved")
"""
        # Generic fallback
        return f"""print('Executing generic task: {task.replace(chr(39), chr(92)+chr(39))}')
print('Context:', {context})
"""

    if language == "bash":
        return f"""echo "Executing shell task: {task}"
ls -la {Path(input_path).parent}
"""

    if language == "r":
        return f"""cat('Executing R task: {task}\n')
"""

    return f"print('Unsupported language: {language}')"


def _execute_code(code: str, language: str) -> dict:
    """Execute generated code in a subprocess and return results."""
    if language == "python":
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = [sys.executable, script_path]
    elif language == "bash":
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = ["bash", script_path]
    elif language == "r":
        with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = ["Rscript", script_path]
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language: {language}",
            "exit_code": -1,
        }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Code execution timed out",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
        }
    finally:
        try:
            Path(script_path).unlink()
        except Exception:
            pass


def main(skill_inputs: dict) -> dict:
    """Generate and execute a code action for the given task."""
    task = skill_inputs["task"]
    language = skill_inputs.get("language", "python")
    context = skill_inputs.get("context", {})

    code = _generate_code(task, language, context)
    execution = _execute_code(code, language)

    return {
        "code": code,
        "result": {
            "success": execution["success"],
            "language": language,
            "context_keys": list(context.keys()),
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
            "exit_code": execution["exit_code"],
        },
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
