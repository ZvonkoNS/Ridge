// Evidence viewer: zoom and pan by keyboard, buttons, wheel or drag; nearest-neighbour above the
// bitmap's own resolution so pixels are shown as computed; the zoom level and interpolation are
// always stated. Overlays (region, ruler) are drawn on top and never change pixels. The image is
// shown as soon as it loads: no fade, so the viewer never delays the first paint of evidence.
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { KeyboardEvent, PointerEvent, WheelEvent } from "react";

import {
  centre,
  clampZoom,
  fitZoom,
  interpolation,
  nextStep,
  spanRect,
  toSource,
  visibleRect,
  zoomAround,
  zoomLabel,
  type Point,
  type Rect,
  type Size,
} from "../lib/viewport";
import type { Marks } from "../lib/minutiae";
import { Button } from "./ui";

export type Tool = "pan" | "roi" | "ruler";

export interface Detail {
  url: string;
  rect: Rect;
}

interface Props {
  title: string;
  url: string | null;
  bitmap: Size | null;
  source: Size | null;
  tool?: Tool;
  roi?: Rect | null;
  ruler?: Point[];
  onRoi?: (rect: Rect) => void;
  onRulerPoint?: (point: Point) => void;
  loadDetail?: (rect: Rect) => Promise<Detail>;
  /** Minutiae overlay (unvalidated, orientation only), in the shown image's pixels. */
  marks?: Marks | null;
  /** Controlled zoom (screen pixels per image pixel), for viewers linked at equal scale. */
  zoom?: number | undefined;
  onZoom?: ((zoom: number) => void) | undefined;
  label: (zoom: number) => ReactNode;
}

const PAN_STEP = 48;

/** Whether a point (image pixels) lies on the image. */
export function insideImage(point: Point, image: Size): boolean {
  return point.x >= 0 && point.y >= 0 && point.x <= image.width && point.y <= image.height;
}

/** Whether rectangle `outer` contains rectangle `inner`. */
export function covers(outer: Rect, inner: Rect): boolean {
  return (
    outer.x <= inner.x &&
    outer.y <= inner.y &&
    outer.x + outer.width >= inner.x + inner.width &&
    outer.y + outer.height >= inner.y + inner.height
  );
}

/** One minutia: a circle (ending) or a square (bifurcation) with a tick in its direction. */
function MarkShape({ mark, size }: { mark: Marks["items"][number]; size: number }) {
  const angle = (mark.angle * Math.PI) / 180; // counter-clockwise from +x; image y grows downwards
  const x2 = mark.x + Math.cos(angle) * size * 2.2;
  const y2 = mark.y - Math.sin(angle) * size * 2.2;
  return (
    <g className={`ov-mark ov-${mark.kind}`}>
      {mark.kind === "ending" ? (
        <circle cx={mark.x} cy={mark.y} r={size} />
      ) : (
        <rect x={mark.x - size} y={mark.y - size} width={size * 2} height={size * 2} />
      )}
      <line x1={mark.x} y1={mark.y} x2={x2} y2={y2} />
    </g>
  );
}

export function ImageViewer(props: Props) {
  const { title, url, bitmap, source, tool = "pan", roi, ruler = [], label } = props;
  const box = useRef<HTMLDivElement>(null);
  const [viewer, setViewer] = useState<Size>({ width: 800, height: 600 });
  // `manual` is null while the image is fitted to the viewer; zooming or panning fixes the view.
  const [manual, setManual] = useState<{ zoom: number; pan: Point } | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [shownUrl, setShownUrl] = useState(url);
  const [drag, setDrag] = useState<{ start: Point; origin: Point; moved: boolean } | null>(null);
  const [draft, setDraft] = useState<Rect | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);

  useLayoutEffect(() => {
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const observer = new ResizeObserver(([entry]) => {
      if (entry) {
        setViewer({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, []);

  if (url !== shownUrl) {
    // a new image starts fitted, without the previous image's full-resolution detail
    setShownUrl(url);
    setManual(null);
    setDetail(null);
  }
  const fitted = source ? fitZoom(source, viewer) : 1;
  // With `zoom`/`onZoom` the zoom is controlled by the parent (linked viewers at equal scale).
  const controlled = props.zoom !== undefined;
  const zoom = controlled ? clampZoom(props.zoom ?? fitted) : (manual?.zoom ?? fitted);
  const middle = { x: viewer.width / 2, y: viewer.height / 2 };
  const [seenZoom, setSeenZoom] = useState(zoom);
  if (zoom !== seenZoom) {
    // a zoom set from outside keeps the point in the middle of the viewer in place
    setSeenZoom(zoom);
    if (controlled && manual) {
      setManual({ zoom, pan: zoomAround(manual.pan, seenZoom, zoom, middle) });
    }
  }
  const pan = manual?.pan ?? (source ? centre(source, viewer, zoom) : { x: 0, y: 0 });
  const setPan = (next: Point) => {
    setManual({ zoom, pan: next });
  };
  const fit = () => {
    setManual(null);
    props.onZoom?.(fitted);
  };

  const zoomTo = (next: number, anchor: Point = middle) => {
    const z = clampZoom(next);
    setManual({ zoom: z, pan: zoomAround(pan, zoom, z, anchor) });
    setSeenZoom(z);
    props.onZoom?.(z);
  };

  const local = (event: { clientX: number; clientY: number }): Point => {
    const r = box.current?.getBoundingClientRect();
    return { x: event.clientX - (r?.left ?? 0), y: event.clientY - (r?.top ?? 0) };
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return; // Alt+digit switches case sections; Ctrl and Cmd belong to the system
    }
    const step = event.shiftKey ? PAN_STEP * 4 : PAN_STEP;
    const moves: Record<string, Point> = {
      ArrowLeft: { x: step, y: 0 },
      ArrowRight: { x: -step, y: 0 },
      ArrowUp: { x: 0, y: step },
      ArrowDown: { x: 0, y: -step },
    };
    const move = moves[event.key];
    if (move) {
      setPan({ x: pan.x + move.x, y: pan.y + move.y });
    } else if (event.key === "+" || event.key === "=") {
      zoomTo(nextStep(zoom, 1));
    } else if (event.key === "-") {
      zoomTo(nextStep(zoom, -1));
    } else if (event.key === "0") {
      fit();
    } else if (event.key === "1") {
      zoomTo(1);
    } else {
      return;
    }
    event.preventDefault();
  };

  const onWheel = (event: WheelEvent<HTMLDivElement>) => {
    zoomTo(event.deltaY < 0 ? nextStep(zoom, 1) : nextStep(zoom, -1), local(event));
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !source) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ start: local(event), origin: pan, moved: false });
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag || !source) {
      return;
    }
    const now = local(event);
    const moved = drag.moved || Math.hypot(now.x - drag.start.x, now.y - drag.start.y) > 3;
    if (tool === "pan") {
      setPan({ x: drag.origin.x + now.x - drag.start.x, y: drag.origin.y + now.y - drag.start.y });
    } else if (tool === "roi" && moved) {
      setDraft(spanRect(toSource(drag.start, pan, zoom), toSource(now, pan, zoom), source));
    }
    if (moved !== drag.moved) {
      setDrag({ ...drag, moved });
    }
  };

  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    if (drag && source) {
      const point = toSource(local(event), pan, zoom);
      if (tool === "roi" && draft) {
        props.onRoi?.(draft);
      } else if (tool === "ruler" && !drag.moved && insideImage(point, source)) {
        // a click on the grey margin is not a point of the photo: it would calibrate the export wrongly
        props.onRulerPoint?.({ x: Math.round(point.x * 10) / 10, y: Math.round(point.y * 10) / 10 });
      }
    }
    setDrag(null);
    setDraft(null);
  };

  const showDetail = async () => {
    if (!source || !props.loadDetail) {
      return;
    }
    const rect = visibleRect(source, viewer, pan, zoom, 2048);
    if (rect) {
      setDetailBusy(true);
      try {
        setDetail(await props.loadDetail(rect));
      } finally {
        setDetailBusy(false);
      }
    }
  };

  const shownWidth = (source?.width ?? 0) * zoom;
  const magnifiedPreview = bitmap !== null && interpolation(bitmap.width, shownWidth) === "nearest neighbour";
  // The fetched rectangle is drawn wherever it is; "full resolution" is claimed only while it covers
  // everything visible. After panning beyond it, the preview shows again and can be refetched.
  const detailOn = detail !== null && zoom >= (bitmap && source ? bitmap.width / source.width : 1);
  const visible = source ? visibleRect(source, viewer, pan, zoom, Number.MAX_SAFE_INTEGER) : null;
  const detailCovers = detailOn && visible !== null && covers(detail.rect, visible);
  const readout = detailCovers
    ? `full resolution here, ${zoom > 1 ? "nearest neighbour" : "smoothed"}`
    : `${bitmap && source && bitmap.width < source.width ? "preview, " : ""}${magnifiedPreview ? "nearest neighbour" : "smoothed"}`;
  const shown = roi && !draft ? roi : draft;

  return (
    <section className="viewer" aria-label={title}>
      <div
        ref={box}
        className={`viewer-table tool-${tool}`}
        tabIndex={0}
        role="application"
        aria-roledescription="image viewer"
        aria-label={`${title}. Arrow keys pan, plus and minus zoom, 0 fits, 1 shows actual size.`}
        onKeyDown={onKeyDown}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          setDrag(null);
          setDraft(null);
        }}
      >
        {url && source ? (
          <div
            className="viewer-stage"
            style={{
              width: shownWidth,
              height: source.height * zoom,
              transform: `translate(${pan.x}px, ${pan.y}px)`,
            }}
          >
            <img src={url} alt={title} draggable={false} className={magnifiedPreview ? "px" : undefined} />
            {detailOn ? (
              <img
                src={detail.url}
                alt=""
                draggable={false}
                className={`viewer-detail${zoom > 1 ? " px" : ""}`}
                style={{
                  left: detail.rect.x * zoom,
                  top: detail.rect.y * zoom,
                  width: detail.rect.width * zoom,
                  height: detail.rect.height * zoom,
                }}
              />
            ) : null}
            <svg
              className="viewer-overlay"
              viewBox={`0 0 ${source.width} ${source.height}`}
              aria-hidden="true"
            >
              {shown ? (
                <rect className="ov-roi" x={shown.x} y={shown.y} width={shown.width} height={shown.height} />
              ) : null}
              {ruler.length === 2 && ruler[0] && ruler[1] ? (
                <line className="ov-ruler" x1={ruler[0].x} y1={ruler[0].y} x2={ruler[1].x} y2={ruler[1].y} />
              ) : null}
              {props.marks?.items.map((m, i) => (
                <MarkShape key={i} mark={m} size={props.marks?.size ?? 4} />
              ))}
              {ruler.map((p, i) => (
                <circle key={i} className="ov-point" cx={p.x} cy={p.y} r={6 / zoom} />
              ))}
            </svg>
          </div>
        ) : (
          <p className="viewer-empty">{url === null ? "Loading the image..." : "No image"}</p>
        )}
      </div>
      <div className="viewer-bar">
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
          {props.loadDetail && magnifiedPreview && !detailCovers ? (
            <Button
              onClick={() => void showDetail()}
              busy={detailBusy}
              title="Each full-resolution view is a logged read"
            >
              Full resolution here
            </Button>
          ) : null}
        </div>
        {label(zoom)}
      </div>
    </section>
  );
}
