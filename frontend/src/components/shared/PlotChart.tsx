import { lazy, Suspense, useEffect, useState } from "react";
import { fetchPlotData, type PlotDataRequest } from "../../api/viz";

// Lazy-load Plotly to reduce initial bundle size
const Plot = lazy(() => import("react-plotly.js"));

interface PlotChartProps {
  request: PlotDataRequest;
  className?: string;
  onError?: (err: Error) => void;
}

export function PlotChart({ request, className, onError }: PlotChartProps) {
  const [figure, setFigure] = useState<{
    data: unknown[];
    layout: Record<string, unknown>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchPlotData(request)
      .then((res) => {
        if (!cancelled) {
          setFigure({ data: res.data, layout: res.layout });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err);
          setError(msg);
          onError?.(err instanceof Error ? err : new Error(msg));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [JSON.stringify(request)]);

  if (loading) {
    return (
      <div
        className={`flex items-center justify-center bg-gray-50 rounded-lg ${className ?? ""}`}
        style={{ width: request.width ?? 800, height: request.height ?? 600 }}
      >
        <div className="flex flex-col items-center gap-2">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-500">Loading plot…</span>
        </div>
      </div>
    );
  }

  if (error || !figure) {
    return (
      <div
        className={`flex items-center justify-center bg-red-50 rounded-lg ${className ?? ""}`}
        style={{ width: request.width ?? 800, height: request.height ?? 600 }}
      >
        <div className="text-center px-4">
          <p className="text-red-600 font-medium">Failed to load plot</p>
          <p className="text-red-400 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <Suspense
        fallback={
          <div
            className="flex items-center justify-center bg-gray-50 rounded-lg"
            style={{ width: request.width ?? 800, height: request.height ?? 600 }}
          >
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        }
      >
        <Plot
          data={figure.data as Plotly.Data[]}
          layout={{
            ...figure.layout,
            autosize: true,
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
          }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
        />
      </Suspense>
    </div>
  );
}
