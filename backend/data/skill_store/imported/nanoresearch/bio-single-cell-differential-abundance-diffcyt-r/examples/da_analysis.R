# diffcyt Differential Abundance Analysis Example

library(diffcyt)
library(flowCore)

print("diffcyt Differential Abundance Analysis")
print(paste(rep("=", 40), collapse = ""))

print("\n1. Load flow cytometry data...")
# fs <- read.flowSet(path = "fcs_files/")

print("\n2. Create experiment info...")
# experiment_info <- data.frame(
#   sample_id = sampleNames(fs),
#   condition = c("control", "control", "treated", "treated"),
#   replicate = c(1, 2, 1, 2)
# )

print("\n3. Create marker info...")
# marker_info <- data.frame(
#   marker_name = colnames(fs),
#   marker_class = c(rep("state", 10), rep("type", 5))
# )

print("\n4. Prepare data...")
# d_se <- prepareData(fs, experiment_info, marker_info)

print("\n5. Generate clusters...")
# d_se <- generateClusters(d_se, xdim = 10, ydim = 10)
# table(cluster_ids(d_se))

print("\n6. Test differential abundance...")
# da_res <- testDA_GLMM(
#   d_se,
#   formula = ~ condition + (1 | replicate),
#   contrast = "conditiontreated"
# )
# rowData(da_res$res)

print("\n7. Test differential state...")
# ds_res <- testDS_limma(
#   d_se,
#   formula = ~ condition,
#   contrast = "conditiontreated"
# )

print("\n8. Visualize...")
# plotHeatmap(d_se, da_res)
# diffcyt::plotDA(da_res)

print("\nNote: This example requires FCS files")
