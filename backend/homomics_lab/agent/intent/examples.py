"""Built-in natural-language examples for intent recognition.

These examples seed the embedding classifier when no domain registry is loaded
or when a domain intent has no explicit examples.
"""

from typing import Dict, List


BUILTIN_INTENT_EXAMPLES: Dict[str, List[str]] = {
    "qa": [
        "什么是 UMAP？",
        "how does PCA work",
        "解释单细胞测序",
        "what is differential expression",
        "什么是空间转录组",
        "how to interpret a volcano plot",
        "告诉我什么是 batch effect",
    ],
    "general_help": [
        "帮我写个 Python 脚本过滤 CSV",
        "generate code to rename sample files",
        "show me an example of parsing JSON",
        "写一段代码处理 TSV 文件",
        "怎么用 pandas 读取 h5ad",
        "给我个 shell 命令批量重命名",
        "filter rows with p-value less than 0.05",
    ],
    "single_cell_analysis": [
        "帮我分析这组单细胞数据",
        "run scRNA-seq QC and clustering",
        "做 PBMC 细胞分群",
        "画一下 UMAP",
        "做一下质控",
        "跑个 PCA",
        "找出差异表达基因",
        "annotate cell types",
        "10x genomics 数据分析",
    ],
    "spatial_analysis": [
        "分析空间转录组数据",
        "run spatial transcriptomics analysis",
        "处理 visium 数据",
        "画空间表达图",
        "xenium 细胞分割",
        "merfish 数据分析",
    ],
    "file_conversion": [
        "把 CSV 转成 h5ad",
        "convert 10x data to h5ad",
        "转成 seurat 对象",
        "文件格式转换",
        " mtx 转 h5ad",
    ],
    "metagenomics_analysis": [
        "做宏基因组分析",
        "run metagenomics profiling",
        "菌群多样性分析",
        "alpha diversity",
        "beta diversity",
        "taxonomic classification",
    ],
}


def get_builtin_examples(analysis_type: str) -> List[str]:
    """Return built-in examples for an analysis type."""
    return list(BUILTIN_INTENT_EXAMPLES.get(analysis_type, []))
