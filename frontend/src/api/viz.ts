import { vizApi } from '@/sdk'
import type { PlotDataRequest, PlotDataResponse, PlotTypeInfo } from '@/types/api'

export type { PlotDataRequest, PlotDataResponse, PlotTypeInfo }

export async function fetchPlotData(request: PlotDataRequest): Promise<PlotDataResponse> {
  const res = await vizApi.plotData(request)
  return res.data
}

export async function listPlotTypes(): Promise<PlotTypeInfo[]> {
  const res = await vizApi.listPlotTypes()
  return res.data
}
