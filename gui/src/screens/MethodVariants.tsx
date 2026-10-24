import { Check } from "../components/Check";
import type { Channel } from "../ipc/types";
import type { Params } from "./ParametersForm";

export const CHANNELS: Record<Channel, string> = {
  green: "green (default)",
  red: "red",
  blue: "blue",
  luma: "luminance",
  auto: "auto: the plane with the strongest ridge signal",
};

export const VARIANTS_NOTE =
  "Method variants change the output pixels and are not covered by the validation (ADR-014). Off by default; every report records them.";

/** The research-mode switch's explanation (ADR-015). */
export const RESEARCH_NOTE =
  "Shows the unvalidated method variants (ADR-014). Switching it off puts every variant back to its default. For research and the validation study, not for casework; every report records the variants a job used.";

type VariantParams = Pick<Params, "channel" | "specularMask" | "upright" | "localFrequency" | "rectify">;

/** The opt-in method variants of ADR-014: off by default, recorded in every report. */
export function MethodVariants({
  value: p,
  onChange: set,
}: {
  value: VariantParams;
  onChange: (patch: Partial<VariantParams>) => void;
}) {
  return (
    <fieldset className="subset">
      <legend>Method variants (unvalidated, off by default)</legend>
      <p className="muted">{VARIANTS_NOTE}</p>
      <label className="field">
        <span>Colour plane</span>
        <select
          value={p.channel}
          onChange={(e) => {
            const value = e.target.value;
            if (value in CHANNELS) {
              set({ channel: value as Channel });
            }
          }}
        >
          {(Object.keys(CHANNELS) as Channel[]).map((c) => (
            <option key={c} value={c}>
              {CHANNELS[c]}
            </option>
          ))}
        </select>
      </label>
      <Check
        label="Specular-highlight mask"
        checked={p.specularMask}
        onChange={(v) => {
          set({ specularMask: v });
        }}
        hint="exclude glare from the finger area"
      />
      <Check
        label="Rotate to upright"
        checked={p.upright}
        onChange={(v) => {
          set({ upright: v });
        }}
        hint="finger axis vertical, tip up, before extraction"
      />
      <Check
        label="Local ridge frequency"
        checked={p.localFrequency}
        onChange={(v) => {
          set({ localFrequency: v });
        }}
        hint="a Gabor bank tuned to the local spacing, not one global spacing; slower"
      />
      <Check
        label="Rectify pad curvature"
        checked={p.rectify}
        onChange={(v) => {
          set({ rectify: v });
        }}
        hint="unroll the pad so the side ridges keep their spacing; rotates upright first"
      />
    </fieldset>
  );
}
