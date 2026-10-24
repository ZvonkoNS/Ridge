import { describe, expect, it } from "vitest";

import { DEFAULT_PARAMS, toOptions, type Params } from "../screens/ParametersForm";

const SHA = "a".repeat(64);

describe("job options", () => {
  it("sends every parameter explicitly", () => {
    expect(toOptions(SHA, DEFAULT_PARAMS)).toEqual({
      evidence: SHA,
      period: null,
      min_quality: 0.25,
      flip: false,
      crop: true,
      debug: false,
      export: true,
      mirror: true,
      ppi: 500,
      ruler: null,
      reference: "ruler",
      minutiae: false,
      roi: null,
      finger_position: 0,
      source_agency: null,
      options: { channel: "green", specular_mask: false },
    });
  });

  it("sends the method variants the examiner turned on", () => {
    const options = toOptions(SHA, { ...DEFAULT_PARAMS, channel: "auto", specularMask: true });
    expect(options).toMatchObject({ options: { channel: "auto", specular_mask: true } });
  });

  it("records the finger position and a trimmed source agency as stated", () => {
    const options = toOptions(SHA, { ...DEFAULT_PARAMS, fingerPosition: 7, sourceAgency: "  Lab A  " });
    expect(options).toMatchObject({ finger_position: 7, source_agency: "Lab A" });
    expect(toOptions(SHA, { ...DEFAULT_PARAMS, sourceAgency: "x".repeat(201) })).toMatch(/200 characters/);
  });

  it("sends the standard edge length for a card reference", () => {
    const options = toOptions(SHA, {
      ...DEFAULT_PARAMS,
      reference: "id1-long",
      rulerMm: "",
      ruler: [
        { x: 0, y: 0 },
        { x: 856, y: 0 },
      ],
    });
    expect(options).toMatchObject({ ruler: [0, 0, 856, 0, 85.6], reference: "id1-long" });
    expect(toOptions(SHA, { ...DEFAULT_PARAMS, reference: "id1-short", ruler: [{ x: 0, y: 0 }] })).toMatch(
      /both/,
    );
  });

  it("maps the region and the ruler to photo pixels", () => {
    const options = toOptions(SHA, {
      ...DEFAULT_PARAMS,
      period: "9.5",
      roi: { x: 10, y: 20, width: 300, height: 400 },
      ruler: [
        { x: 0, y: 0 },
        { x: 200, y: 0 },
      ],
      rulerMm: "10",
    });
    expect(options).toMatchObject({ period: 9.5, roi: [10, 20, 300, 400], ruler: [0, 0, 200, 0, 10] });
  });

  it("explains what to fix instead of sending a bad job", () => {
    const cases: Params[] = [
      { ...DEFAULT_PARAMS, period: "0.5" },
      { ...DEFAULT_PARAMS, ruler: [{ x: 1, y: 1 }] },
      {
        ...DEFAULT_PARAMS,
        ruler: [
          { x: 1, y: 1 },
          { x: 2, y: 1 },
        ],
      },
      {
        ...DEFAULT_PARAMS,
        ruler: [
          { x: 0, y: 0 },
          { x: 100, y: 0 },
        ],
        rulerMm: "0",
      },
      { ...DEFAULT_PARAMS, roi: { x: 0, y: 0, width: 10, height: 100 } },
    ];
    for (const params of cases) {
      expect(typeof toOptions(SHA, params)).toBe("string");
    }
  });

  it("refuses typed ruler points that are not on the photo", () => {
    const params = {
      ...DEFAULT_PARAMS,
      ruler: [
        { x: 10, y: 10 },
        { x: 5000, y: 10 },
      ],
    };
    expect(toOptions(SHA, params, { width: 4000, height: 3000 })).toMatch(/must lie on the photo/);
    expect(typeof toOptions(SHA, params, { width: 6000, height: 3000 })).toBe("object");
  });
});
