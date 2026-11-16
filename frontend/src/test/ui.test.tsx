import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import EvidenceViewer, { highlight } from "../components/EvidenceViewer";
import WeightsPanel from "../components/WeightsPanel";
import { ScoreBadge, Pager, MatchTag } from "../components/ui";
import { isAllowed } from "../pages/Upload";
import { scoreTone, weightsValid, fmt } from "../utils";
import { ReqResult } from "../types";
import { errMsg } from "../api";

const W = { technical_skills: 0.4, semantic_relevance: 0.25, relevant_experience: 0.2, education: 0.1, project_domain: 0.05 };
const req: ReqResult = { requirement_id: "r1", name: "Python", category: "Language", importance: "must", weight: 1, match_type: "exact", credit: 1, similarity: null,
  evidence_text: "Built Python services for payments", page: 2, section: "experience", verification: "verified", note: "Found with supporting context." , related_found: null };

describe("utils", () => {
  it("classifies score tones", () => { expect(scoreTone(80)).toBe("high"); expect(scoreTone(55)).toBe("mid"); expect(scoreTone(10)).toBe("low"); });
  it("validates weights sum to 1", () => { expect(weightsValid(W)).toBe(true); expect(weightsValid({ ...W, education: 0.2 })).toBe(false); });
  it("formats null as dash", () => { expect(fmt(null)).toBe("—"); expect(fmt(87.345, 1)).toBe("87.3"); });
  it("accepts only pdf/docx", () => { expect(isAllowed("a.PDF")).toBe(true); expect(isAllowed("a.docx")).toBe(true); expect(isAllowed("a.exe")).toBe(false); });
  it("maps backend errors to friendly messages", () => {
    expect(errMsg({ response: { data: { error: { message: "Bad weights" } } } })).toBe("Bad weights");
    expect(errMsg({ message: "Network Error" })).toMatch(/backend/);
  });
});

describe("components", () => {
  it("score badge shows range only when evidence is missing", () => {
    const { rerender } = render(<ScoreBadge score={70} low={70} high={70} />);
    expect(screen.getByText("70.0")).toBeInTheDocument(); expect(screen.queryByText(/–/)).toBeNull();
    rerender(<ScoreBadge score={60} low={60} high={72} />); expect(screen.getByText("–72")).toBeInTheDocument();
  });
  it("evidence viewer shows verbatim snippet, page and highlight", () => {
    const { container } = render(<EvidenceViewer req={req} />);
    expect(container.querySelector("mark")?.textContent).toBe("Python");
    expect(screen.getByText(/page 2, experience section/)).toBeInTheDocument();
  });
  it("evidence viewer states when there is no evidence", () => {
    render(<EvidenceViewer req={{ ...req, evidence_text: null, match_type: "none", credit: 0 }} />);
    expect(screen.getByText(/No supporting text/)).toBeInTheDocument(); expect(screen.getByText("No evidence")).toBeInTheDocument();
  });
  it("highlight escapes regex characters", () => { expect(() => highlight("C++ and C#", ["C++", "C#"])).not.toThrow(); });
  it("weights panel flags totals that are not 100%", () => {
    render(<WeightsPanel value={{ ...W, education: 0.3 }} onChange={() => {}} defaults={W} />);
    expect(screen.getByText(/must equal 100%/)).toBeInTheDocument();
  });
  it("weights panel emits changes and reset", () => {
    const fn = vi.fn(); render(<WeightsPanel value={W} onChange={fn} defaults={W} />);
    fireEvent.change(screen.getByLabelText("Education"), { target: { value: "25" } }); expect(fn).toHaveBeenCalledWith({ ...W, education: 0.25 });
    fireEvent.click(screen.getByText("Reset to default")); expect(fn).toHaveBeenLastCalledWith(W);
  });
  it("pager disables edges", () => {
    const fn = vi.fn(); render(<Pager page={1} pageSize={10} total={25} onPage={fn} />);
    expect(screen.getByText("Prev")).toBeDisabled(); fireEvent.click(screen.getByText("Next")); expect(fn).toHaveBeenCalledWith(2);
  });
  it("match tag label", () => { render(<MatchTag type="partial" />); expect(screen.getByText("Related (partial)")).toBeInTheDocument(); });
});
