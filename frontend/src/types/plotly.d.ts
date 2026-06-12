declare module "plotly.js-dist-min" {
  import { PlotlyHTMLElement } from "plotly.js";
  export function newPlot(
    root: HTMLElement,
    data: unknown,
    layout?: unknown,
    config?: unknown
  ): Promise<PlotlyHTMLElement>;
  export function purge(root: HTMLElement): void;
}
