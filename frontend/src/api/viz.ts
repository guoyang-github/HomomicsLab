import axios from "axios";

const API_BASE = "/api/viz";

export interface PlotDataRequest {
  plot_type: "umap" | "heatmap" | "violin" | "bar" | "scatter" | "histogram";
  data: Record<string, unknown>;
  title?: string;
  width?: number;
  height?: number;
}

export interface PlotDataResponse {
  data: unknown[];
  layout: Record<string, unknown>;
  plot_type: string;
}

export interface PlotTypeInfo {
  type: string;
  description: string;
}

export async function fetchPlotData(request: PlotDataRequest): Promise<PlotDataResponse> {
  const res = await axios.post(`${API_BASE}/plot-data`, request);
  return res.data;
}

export async function listPlotTypes(): Promise<PlotTypeInfo[]> {
  const res = await axios.get(`${API_BASE}/plot/types`);
  return res.data;
}
