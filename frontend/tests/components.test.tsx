import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DecisionBadge, Empty, Pagination, SimBanner } from "../src/components/ui";
import { ResultView } from "../src/components/ResultView";
import type { Inspection } from "../src/types";

vi.mock("../src/hooks/useAuthImage", () => ({ useAuthImage: () => ({ url: "blob:x", missing: false }) }));

const base: Inspection = {
  id: 7, uid: "u", product_id: 1, product_name: "PCB", product_category: "PCB", product_code: "SN1", batch_id: null, batch_code: "B", line_id: "L", mode: "demo", simulated: true, scenario: "subtle_defect",
  score: 0.55, decision: "REVIEW", defect_class: "scratch", confidence: 0.7, review_threshold: 0.4, fail_threshold: 0.7, model_version: "demo-simulator:1.0", latency_ms: 12.3, notes: "", image_sha256: "a".repeat(64),
  review_status: "PENDING", final_decision: null, explanation: { summary: "between thresholds", reference_patch: { available: false, unavailable_reason: "No reference image registered." } },
  defects: [{ id: 1, x: 1, y: 2, w: 3, h: 4, area: 12, peak_score: 0.6, label: "scratch", confidence: 0.7 }], reviews: [], images: ["original", "overlay"], created_at: "2026-01-01T00:00:00",
};
const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

describe("ui primitives", () => {
  it("renders decision badges and empty states", () => {
    render(<><DecisionBadge d="FAIL" /><Empty title="Nothing here" /></>);
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
  it("shows the simulated banner text", () => { render(<SimBanner />); expect(screen.getByRole("note")).toHaveTextContent(/simulated/i); });
  it("paginates", () => { render(<Pagination page={2} pageSize={10} total={35} onChange={() => {}} />); expect(screen.getByText("Page 2 of 4")).toBeInTheDocument(); });
});

describe("ResultView", () => {
  it("labels simulated results and shows an honest unavailable reference", () => {
    wrap(<ResultView insp={base} />);
    expect(screen.getAllByText(/simulated/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("decision")).toHaveTextContent("REVIEW");
    expect(screen.getByText(/Unavailable/)).toBeInTheDocument();
    expect(screen.getByText("0.550")).toBeInTheDocument();
  });
  it("does not show a simulated banner for real inspections", () => {
    wrap(<ResultView insp={{ ...base, mode: "real", simulated: false, model_version: "pc:1.0" }} />);
    expect(screen.queryByText(/SIMULATED RESULT/)).toBeNull();
    expect(screen.getByText("Real AI")).toBeInTheDocument();
  });
});
