import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast } from "../components/Toast";
import { PIPELINE_STAGES, STATUSES, bestEntry, fuzzyScore, groupByStatus, groupChangesByPrevious, heatStyle, normStatus } from "../utils";

describe("bulk undo", () => {
  it("groups changes by previous status so each group restores in one request", () => {
    expect(groupChangesByPrevious([])).toEqual({});
    expect(groupChangesByPrevious([
      { candidate_id: 1, from: "new" }, { candidate_id: 2, from: "interview" }, { candidate_id: 3, from: "new" },
    ])).toEqual({ new: [1, 3], interview: [2] });
  });
});

describe("pipeline helpers", () => {
  it("every stage the board offers is a status the app knows", () => {
    expect(PIPELINE_STAGES.map((s) => s.id)).toEqual(STATUSES);
  });
  it("maps the legacy in_review status to reviewed", () => {
    expect(normStatus("in_review")).toBe("reviewed");
    expect(normStatus("shortlisted")).toBe("shortlisted");
  });
  it("groups candidates by stage, keeping empty stages and sending unknown values to New", () => {
    const g = groupByStatus([{ review_status: "new" }, { review_status: "in_review" }, { review_status: "interview" }, { review_status: "weird" }]);
    expect(Object.keys(g)).toEqual(STATUSES);
    expect(g.new).toHaveLength(2);
    expect(g.reviewed).toHaveLength(1);
    expect(g.interview).toHaveLength(1);
    expect(g.shortlisted).toHaveLength(0);
  });
});

describe("command palette search", () => {
  it("requires every word and ranks earlier matches higher", () => {
    expect(fuzzyScore("", "anything")).toBe(0);
    expect(fuzzyScore("zzz", "Lakshmi Narayan")).toBe(-1);
    expect(fuzzyScore("lak nar", "Lakshmi Narayan")).toBeGreaterThan(0);
    expect(fuzzyScore("lak xyz", "Lakshmi Narayan")).toBe(-1);
    expect(fuzzyScore("data", "Data Analyst")).toBeGreaterThan(fuzzyScore("data", "Senior Data Analyst"));
  });
});

describe("talent matrix helpers", () => {
  it("finds the best job and ignores missing scores", () => {
    expect(bestEntry({})).toBeNull();
    expect(bestEntry({ 3: 40, 4: 71.5, 5: null, 6: undefined })).toEqual([4, 71.5]);
  });
  it("colours missing scores grey and darkens with the score", () => {
    expect(heatStyle(null).backgroundColor).toBe("#f1f5f9");
    expect(heatStyle(10).color).toBe("#1e1b4b");
    expect(heatStyle(90).color).toBe("#ffffff");
    const alpha = (s: number) => Number(/, ([\d.]+)\)/.exec(heatStyle(s).backgroundColor)![1]);
    expect(alpha(90)).toBeGreaterThan(alpha(30));
  });
});

describe("toasts", () => {
  function Demo({ onUndo }: { onUndo: () => void }) {
    const { toast } = useToast();
    return <button onClick={() => toast("Moved to Interview", { action: { label: "Undo", onClick: onUndo } })}>go</button>;
  }
  it("shows a message with an undo action that runs and dismisses it", () => {
    const undo = vi.fn();
    render(<ToastProvider><Demo onUndo={undo} /></ToastProvider>);
    fireEvent.click(screen.getByText("go"));
    expect(screen.getByRole("status")).toHaveTextContent("Moved to Interview");
    act(() => { fireEvent.click(screen.getByText("Undo")); });
    expect(undo).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
