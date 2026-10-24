// Evidence viewer: zoom and pan by keyboard, buttons, wheel or drag; nearest-neighbour above the
// bitmap's own resolution so pixels are shown as computed; the zoom level and interpolation are
// always stated. Overlays (print area, region, ruler) are drawn on top and never change pixels.
// The image is shown as soon as it loads: no fade, so the viewer never delays the first paint of
// evidence.
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
  type Point,
  type Rect,
  type Size,
} from "../lib/viewport";
import type { Marks } from "../lib/minutiae";
import { ViewerOverlay } from "./ViewerOverlay";
import { ViewerZoomBar } from "./ViewerZoomBar";

export type Tool = "pan" | "roi" | "ruler" | "mark";

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
  /** Further overlay in the image's pixels (the job's print area), drawn under region and ruler. */
  overlay?: ReactNode;
  /** Controlled zoom (screen pixels per image pixel), for viewers linked at equal scale. */
  zoom?: number | undefined;
  onZoom?: ((zoom: number) => void) | undefined;
  /** The image pixel at the viewer's centre, set by the parent (linked viewers); with it the pan is controlled. */
  focus?: Point | undefined;
  onFocus?: ((focus: Point) => void) | undefined;
  /** With tool "mark": a click on the image, in whole image pixels. */
  onMark?: ((point: Point) => void) | undefined;
  /** The examiner's marks, drawn over the automatic ones. */
  examinerMarks?: Marks | null | undefined;
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
  // With `focus`/`onFocus` the pan is controlled too: the given image pixel sits at the viewer's centre.
  const focus = props.focus;
  const [seenZoom, setSeenZoom] = useState(zoom);
  if (zoom !== seenZoom) {
    // a zoom set from outside keeps the point in the middle of the viewer in place
    setSeenZoom(zoom);
    if (controlled && manual && focus === undefined) {
      setManual({ zoom, pan: zoomAround(manual.pan, seenZoom, zoom, middle) });
    }
  }
  const pan =
    focus !== undefined
      ? { x: middle.x - focus.x * zoom, y: middle.y - focus.y * zoom }
      : (manual?.pan ?? (source ? centre(source, viewer, zoom) : { x: 0, y: 0 }));
  const setPan = (next: Point) => {
    if (focus !== undefined) {
      props.onFocus?.(toSource(middle, next, zoom));
    } else {
      setManual({ zoom, pan: next });
    }
  };
  const fit = () => {
    setManual(null);
    props.onZoom?.(fitted);
    if (focus !== undefined && source) {
      props.onFocus?.({ x: source.width / 2, y: source.height / 2 });
    }
  };

  const zoomTo = (next: number, anchor: Point = middle) => {
    const z = clampZoom(next);
    const nextPan = zoomAround(pan, zoom, z, anchor);
    if (focus !== undefined) {
      props.onZoom?.(z);
      props.onFocus?.(toSource(middle, nextPan, z));
      return;
    }
    setManual({ zoom: z, pan: nextPan });
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
      } else if (tool === "mark" && !drag.moved && insideImage(point, source)) {
        // a mark names one pixel of the output image
        props.onMark?.({
          x: Math.min(source.width - 1, Math.floor(point.x)),
          y: Math.min(source.height - 1, Math.floor(point.y)),
        });
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
            <ViewerOverlay
              source={source}
              zoom={zoom}
              overlay={props.overlay}
              region={shown}
              ruler={ruler}
              marks={props.marks}
              examiner={props.examinerMarks}
            />
          </div>
        ) : (
          <p className="viewer-empty">{url === null ? "Loading the image..." : "No image"}</p>
        )}
      </div>
      <div className="viewer-bar">
        <ViewerZoomBar
          zoom={zoom}
          readout={readout}
          zoomTo={zoomTo}
          fit={fit}
          showDetail={props.loadDetail && magnifiedPreview && !detailCovers ? () => void showDetail() : null}
          detailBusy={detailBusy}
        />
        {label(zoom)}
      </div>
    </section>
  );
}
