declare module "react-plotly.js" {
  import type { Component } from "react";
  import type Plotly from "plotly.js";

  interface PlotParams {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: Readonly<{
      data: Plotly.Data[];
      layout: Partial<Plotly.Layout>;
    }>, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: Readonly<{
      data: Plotly.Data[];
      layout: Partial<Plotly.Layout>;
    }>, graphDiv: HTMLElement) => void;
    onPurge?: (figure: Readonly<{
      data: Plotly.Data[];
      layout: Partial<Plotly.Layout>;
    }>, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
  }

  export default class Plot extends Component<PlotParams> {}
}

declare module "plotly.js-dist-min" {
  import type Plotly from "plotly.js";
  export = Plotly;
}
