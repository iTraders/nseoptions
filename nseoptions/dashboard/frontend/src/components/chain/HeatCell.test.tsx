import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HeatCell } from "./HeatCell";

// jsdom (cssstyle) normalizes hex to rgb(); accept either serialization.
const RED = ["rgb(248, 105, 107)", "#f8696b"];
const GREEN = ["rgb(99, 190, 123)", "#63be7b"];

describe("HeatCell", () => {
  it("paints the low anchor red (#F8696B)", () => {
    const { container } = render(<HeatCell t={0}>1.0</HeatCell>);
    const span = container.querySelector("span")!;
    expect(RED).toContain(span.style.backgroundColor);
  });

  it("paints the high anchor green (#63BE7B)", () => {
    const { container } = render(<HeatCell t={1}>1.0</HeatCell>);
    const span = container.querySelector("span")!;
    expect(GREEN).toContain(span.style.backgroundColor);
  });

  it("suppresses the heat background when inactive", () => {
    const { container } = render(
      <HeatCell t={0} active={false}>
        –
      </HeatCell>,
    );
    expect(container.querySelector("span")!.style.backgroundColor).toBe("");
  });
});
