// The image viewer's zoom controls. The readout always states the zoom level and how the pixels
// are drawn (smoothed or nearest neighbour, preview or full resolution).
import { nextStep, zoomLabel } from "../lib/viewport";
import { Button } from "./ui";

interface Props {
  zoom: number;
  readout: string;
  zoomTo: (zoom: number) => void;
  fit: () => void;
  /** Fetch the visible area at full resolution; null hides the button. */
  showDetail: (() => void) | null;
  detailBusy: boolean;
}

export function ViewerZoomBar({ zoom, readout, zoomTo, fit, showDetail, detailBusy }: Props) {
  return (
    <div className="viewer-zoom" role="group" aria-label="Zoom">
      <Button
        onClick={() => {
          zoomTo(nextStep(zoom, -1));
        }}
        aria-label="Zoom out"
      >
        −
      </Button>
      <output className="viewer-readout" aria-live="polite">
        {zoomLabel(zoom)} · {readout}
      </output>
      <Button
        onClick={() => {
          zoomTo(nextStep(zoom, 1));
        }}
        aria-label="Zoom in"
      >
        +
      </Button>
      <Button onClick={fit}>Fit</Button>
      <Button
        onClick={() => {
          zoomTo(1);
        }}
      >
        100 %
      </Button>
      {showDetail ? (
        <Button onClick={showDetail} busy={detailBusy} title="Each full-resolution view is a logged read">
          Full resolution here
        </Button>
      ) : null}
    </div>
  );
}
