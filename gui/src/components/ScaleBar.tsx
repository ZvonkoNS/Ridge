// A forensic-ruler style scale bar (alternating black and white millimetre segments). It is drawn
// at the CURRENT zoom, so it always shows true size on screen, and it states where its scale
// comes from and how uncertain it is.

export interface ScaleSource {
  /** Pixels of the shown image per millimetre on the finger. */
  pxPerMm: number;
  method: string;
  /** Relative uncertainty of `pxPerMm` in percent, or null when no uncertainty is known. */
  uncertaintyPct: number | null;
}

const LENGTHS_MM = [1, 2, 5, 10, 20, 50];

/** The longest round length that is between 48 and 220 screen pixels at this scale. */
export function barLength(screenPxPerMm: number): number {
  const fitting = LENGTHS_MM.filter((mm) => mm * screenPxPerMm <= 220);
  const chosen = fitting.reverse().find((mm) => mm * screenPxPerMm >= 48);
  return chosen ?? fitting[0] ?? 1;
}

const METHOD_NAMES: Record<string, string> = {
  ruler: "ruler",
  card: "card edge",
  "ridge-period": "ridge-period estimate",
  manual: "examiner value",
  file: "resolution in the file",
  examiner: "resolution typed by the examiner",
};

interface Props {
  source: ScaleSource;
  zoom: number;
}

export function ScaleBar({ source, zoom }: Props) {
  const screenPxPerMm = source.pxPerMm * zoom;
  if (!(screenPxPerMm > 0) || !Number.isFinite(screenPxPerMm)) {
    return null;
  }
  const mm = barLength(screenPxPerMm);
  const segments = mm <= 10 ? mm : mm / 5;
  const segment = (mm * screenPxPerMm) / segments;
  const width = Math.max(1, Math.round(mm * screenPxPerMm));
  const method = METHOD_NAMES[source.method] ?? source.method;
  const u = source.uncertaintyPct;
  const text = `${mm} mm, ${method}${u === null ? "" : `, ±${u.toFixed(u < 1 ? 2 : 0)} %`}`;
  return (
    <figure className="scalebar" aria-label={`Scale bar: ${text}`}>
      <svg width={width + 2} height={10} viewBox={`0 0 ${width + 2} 10`} aria-hidden="true" focusable="false">
        <rect x={0.5} y={0.5} width={width + 1} height={9} fill="#ffffff" stroke="#000000" />
        {Array.from({ length: segments }, (_, i) =>
          i % 2 === 0 ? (
            <rect key={i} x={1 + i * segment} y={1} width={segment} height={8} fill="#000000" />
          ) : null,
        )}
      </svg>
      <figcaption>{text}</figcaption>
    </figure>
  );
}
