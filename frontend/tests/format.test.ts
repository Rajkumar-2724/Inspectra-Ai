import { describe, expect, it } from "vitest";
import { errMsg } from "../src/services/api";
import { fmtScore, pct, title } from "../src/utils/format";

describe("format helpers", () => {
  it("formats values and handles nulls", () => {
    expect(fmtScore(0.12345)).toBe("0.123");
    expect(fmtScore(null)).toBe("—");
    expect(pct(0.256)).toBe("25.6%");
    expect(title("missing_component")).toBe("Missing component");
    expect(title(null)).toBe("—");
  });
  it("turns API errors into readable messages", () => {
    expect(errMsg({ response: { status: 409, data: { detail: { message: "Real AI mode is unavailable", reasons: ["no model"] } } } })).toContain("no model");
    expect(errMsg({ response: { status: 422, data: { detail: "Validation failed", errors: [{ field: "x", message: "bad" }] } } })).toBe("Validation failed");
    expect(errMsg({ code: "ERR_NETWORK" })).toContain("Cannot reach the backend");
  });
});
