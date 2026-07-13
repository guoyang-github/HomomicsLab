BEGIN{
  FS=","; OFS=",";
  m["Tem/Temra cytotoxic T cells"]="CD8T"; m["Tem/Trm cytotoxic T cells"]="CD8T";
  m["Tcm/Naive cytotoxic T cells"]="CD8T"; m["Tcm/Naive helper T cells"]="CD4T";
  m["Regulatory T cells"]="CD4T"; m["Type 1 helper T cells"]="CD4T";
  m["Type 17 helper T cells"]="CD4T"; m["Follicular helper T cells"]="CD4T";
  m["MAIT cells"]="CD8T"; m["Gamma-delta T cells"]="CD8T";
  m["CD16+ NK cells"]="NK"; m["CD16- NK cells"]="NK"; m["ILC3"]="NK"; m["ILC"]="NK";
  m["Naive B cells"]="B"; m["Memory B cells"]="B";
  m["Plasmablasts"]="Plasma"; m["Plasma cells"]="Plasma";
  m["Classical monocytes"]="Myeloid"; m["Non-classical monocytes"]="Myeloid";
  m["Intermediate monocytes"]="Myeloid"; m["Macrophages"]="Myeloid";
  m["DC1"]="Myeloid"; m["DC2"]="Myeloid"; m["Mast cells"]="Myeloid"; m["pDC"]="Myeloid";
  m["Endothelial cells"]="Endothelial"; m["Fibroblasts"]="CAF";
  m["Megakaryocytes/platelets"]="Platelet"; m["Epithelial cells"]="Ductal";
  # order refs
  reforder="CD8T CD4T NK B Myeloid Ductal Endothelial Stellate Platelet CAF Plasma Schwann Acinar Endocrine";
  split(reforder, RO, " ");
}
NR==1{next}
{
  ref=$2; pred=$4; conf=$5+0;
  coarse=(pred in m)?m[pred]:"OTHER";
  n++; refn[ref]++; predn[pred]++; refs[ref]=1; preds[pred]=1;
  conf_sum+=conf; conf_ref[ref]+=conf;
  fkey=ref"|"pred; fine[fkey]++;
  ckey=ref"|"coarse; coarse_cm[ckey]++; coarses[coarse]=1;
  if(coarse==ref){agree++; agree_ref[ref]++}
  # top predicted per ref
  if(fine[fkey]>topcnt[ref]){topcnt[ref]=fine[fkey]; toppred[ref]=pred}
}
END{
  # per-label csv
  print "all_celltype,n_cells,mean_conf,top_celltypist_label,coarse_recall" > "celltypist_vs_all_celltype_per_label.csv";
  for(i=1;i<=length(RO);i++){r=RO[i]; if(!(r in refs))continue;
    recall=(refn[r]>0)?agree_ref[r]/refn[r]:0;
    printf "%s,%d,%.4f,%s,%.4f\n", r, refn[r], conf_ref[r]/refn[r], toppred[r], recall >> "celltypist_vs_all_celltype_per_label.csv";
  }
  # fine confusion long
  print "all_celltype,celltypist_label,n_cells" > "celltypist_vs_all_celltype_confusion_fine.csv";
  for(k in fine){split(k,a,"|"); printf "%s,%s,%d\n", a[1], a[2], fine[k] >> "celltypist_vs_all_celltype_confusion_fine.csv";}
  # coarse confusion long
  print "all_celltype,celltypist_coarse,n_cells" > "celltypist_vs_all_celltype_confusion_coarse.csv";
  for(k in coarse_cm){split(k,a,"|"); printf "%s,%s,%d\n", a[1], a[2], coarse_cm[k] >> "celltypist_vs_all_celltype_confusion_coarse.csv";}
  # report
  rpt="comparison_report.txt";
  print "CellTypist vs all_celltype comparison (PA12_sc.h5ad)" > rpt;
  print "====================================================" >> rpt;
  print "Model: Immune_All_Low.pkl (majority voting, best match)" >> rpt;
  printf "Total cells: %d\n", n >> rpt;
  printf "Mean CellTypist confidence: %.4f\n", conf_sum/n >> rpt;
  printf "Coarse overall agreement (immune-class mapped): %.4f (%d/%d)\n", agree/n, agree, n >> rpt;
  print "" >> rpt;
  print "Per-reference-label summary:" >> rpt;
  for(i=1;i<=length(RO);i++){r=RO[i]; if(!(r in refs))continue;
    recall=(refn[r]>0)?agree_ref[r]/refn[r]:0;
    printf "  %-12s n=%-5d recall=%.3f  top_pred=%s\n", r, refn[r], recall, toppred[r] >> rpt;
  }
  print "" >> rpt;
  print "Coarse agreement = fraction of cells whose CellTypist fine label maps to the same broad class as all_celltype." >> rpt;
  print "Note: non-immune all_celltype classes (Acinar/Ductal/Endocrine/Schwann/Stellate/CAF) are outside the Immune_All_Low model scope and are expected to show low recall." >> rpt;
}
