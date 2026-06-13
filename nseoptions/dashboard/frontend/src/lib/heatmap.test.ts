import { describe, expect, it } from "vitest";

import { HEAT, diverging, heatColor, normalize, textColorFor } from "./heatmap";

describe("heatColor reproduces the Excel template scale", () => {
  it("anchors exactly on the three stops", () => {
    expect(heatColor(0).toUpperCase()).toBe(HEAT.low); // #F8696B
    expect(heatColor(0.5).toUpperCase()).toBe(HEAT.mid); // #FFEB84
    expect(heatColor(1).toUpperCase()).toBe(HEAT.high); // #63BE7B
  });

  it("clamps values outside [0,1] to the end stops", () => {
    expect(heatColor(-1).toUpperCase()).toBe(HEAT.low);
    expect(heatColor(2).toUpperCase()).toBe(HEAT.high);
  });

  it("interpolates between the stops", () => {
    expect(heatColor(0.25)).not.toBe(heatColor(0));
    expect(heatColor(0.75)).not.toBe(heatColor(1));
  });
});

describe("scale helpers", () => {
  it("normalize maps into [0,1] and is safe on a zero range", () => {
    expect(normalize(5, 0, 10)).toBe(0.5);
    expect(normalize(5, 5, 5)).toBe(0.5);
  });

  it("diverging is symmetric around zero", () => {
    expect(diverging(0, 10)).toBe(0.5);
    expect(diverging(10, 10)).toBe(1);
    expect(diverging(-10, 10)).toBe(0);
  });

  it("textColorFor picks dark text on the light mid-stop", () => {
    expect(textColorFor(HEAT.mid)).toBe("#0b0b0c");
  });
});
