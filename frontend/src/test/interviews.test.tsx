import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InterviewNotes from "../components/InterviewNotes";
import { ToastProvider } from "../components/Toast";
import { api } from "../api";
import { cleanRatings, interviewLabel, interviewTitle, recommendationOf, roundLabel, tallyText, todayLocal } from "../utils";

vi.mock("../api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  errMsg: (e: unknown) => (e as Error)?.message ?? "error",
}));
const mocked = api as unknown as Record<"get" | "post" | "patch" | "delete", ReturnType<typeof vi.fn>>;

const note = (over = {}) => ({ id: 1, candidate_id: 7, job_id: 3, round: "technical", interviewer: "Asha", interviewed_on: "2026-11-10", recommendation: "yes",
  ratings: { technical: 4, communication: 5 }, rating_avg: 4.5, strengths: "Clear thinker", concerns: "Limited cloud", notes: "Good design chat.", created_at: "", updated_at: "", ...over });
const summary = { count: 1, avg_rating: 4.5, avg_by_criterion: { technical: 4, communication: 5, problem_solving: null, collaboration: null }, recommendations: { strong_yes: 0, yes: 1, no: 0, strong_no: 0, undecided: 0 } };

function setup(items: unknown[] = [], sum: unknown = { ...summary, count: items.length }) {
  mocked.get.mockImplementation((url: string) => Promise.resolve({ data: url.startsWith("/jobs") ? { items: [{ id: 3, title: "Python Backend Developer" }] } : { items, summary: sum } }));
  return render(<ToastProvider><InterviewNotes candidateId={7} activeJobId={3} /></ToastProvider>);
}

describe("interview helpers", () => {
  it("keeps only valid 1-5 whole ratings", () => {
    expect(cleanRatings({ technical: 4, communication: 0, problem_solving: 6, collaboration: undefined, x: 2.5 })).toEqual({ technical: 4 });
  });
  it("formats dates, tallies and labels", () => {
    expect(todayLocal(new Date(2026, 10, 5))).toBe("2026-11-05");
    expect(tallyText({ strong_yes: 1, yes: 2, no: 0, strong_no: 0, undecided: 0 })).toBe("1 strong yes · 2 yes");
    expect(tallyText({})).toBe("");
    expect(roundLabel("phone_screen")).toBe("Phone screen");
    expect(recommendationOf("nonsense").id).toBe("undecided");
  });
});

describe("pipeline card interview chip", () => {
  const rec = { strong_yes: 1, yes: 0, no: 1, strong_no: 0, undecided: 0 };
  it("pluralises the label", () => {
    expect(interviewLabel(1)).toBe("1 interview");
    expect(interviewLabel(3)).toBe("3 interviews");
  });
  it("describes count, average rating and what interviewers said", () => {
    expect(interviewTitle({ count: 2, avg_rating: 4.25, recommendations: rec })).toBe("2 interviews · average rating 4.3 / 5 · interviewers said: 1 strong yes · 1 no");
    expect(interviewTitle({ count: 1, avg_rating: null, recommendations: { undecided: 1 } })).toBe("1 interview · no ratings yet · interviewers said: 1 undecided");
    expect(interviewTitle({ count: 1, avg_rating: 5, recommendations: {} })).toBe("1 interview · average rating 5.0 / 5");
  });
});

describe("InterviewNotes", () => {
  beforeEach(() => { Object.values(mocked).forEach((f) => f.mockReset()); });

  it("shows an empty state and no summary when there are no interviews", async () => {
    setup([]);
    expect(await screen.findByText(/No interviews recorded yet/)).toBeInTheDocument();
    expect(screen.queryByText("Average rating")).toBeNull();
  });

  it("shows saved interviews with ratings, the tally and the linked job, without any combined verdict", async () => {
    setup([note()]);
    expect(await screen.findByText("Clear thinker")).toBeInTheDocument();
    expect(screen.getByText("Limited cloud")).toBeInTheDocument();
    expect(screen.getByText("1 yes")).toBeInTheDocument();
    expect(screen.getByText("Average rating")).toBeInTheDocument();
    expect(await screen.findByText("Python Backend Developer")).toBeInTheDocument();
    expect(screen.getByText(/never change the match score or rank/)).toBeInTheDocument();
    expect(screen.queryByText(/hire|reject/i)).toBeNull();
  });

  it("cannot save an empty scorecard, then posts a cleaned payload", async () => {
    mocked.post.mockResolvedValue({ data: note() });
    setup([]);
    fireEvent.click(await screen.findByText("Add interview"));
    const save = screen.getByText("Save interview") as HTMLButtonElement;
    expect(save).toBeDisabled();
    fireEvent.click(within4(screen.getByRole("radiogroup", { name: "Technical rating" })));
    fireEvent.click(screen.getByRole("radio", { name: "Strong yes" }));
    fireEvent.change(screen.getByLabelText("Interviewer"), { target: { value: "  Asha " } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Solid." } });
    expect(save).not.toBeDisabled();
    fireEvent.click(save);
    await waitFor(() => expect(mocked.post).toHaveBeenCalledTimes(1));
    const [url, body] = mocked.post.mock.calls[0];
    expect(url).toBe("/candidates/7/interviews");
    expect(body).toMatchObject({ round: "technical", recommendation: "strong_yes", ratings: { technical: 4 }, notes: "Solid.", job_id: 3, interviewer: "  Asha " });
    expect(Object.keys(body.ratings)).toEqual(["technical"]);
  });

  it("clicking the chosen star again clears that rating", async () => {
    setup([]);
    fireEvent.click(await screen.findByText("Add interview"));
    const group = screen.getByRole("radiogroup", { name: "Communication rating" });
    const star3 = group.querySelectorAll('[role="radio"]')[2] as HTMLElement;
    fireEvent.click(star3);
    expect(star3.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(star3);
    expect(star3.getAttribute("aria-checked")).toBe("false");
  });

  it("rapid clicks on different criteria keep every rating", async () => {
    mocked.post.mockResolvedValue({ data: note() });
    setup([]);
    fireEvent.click(await screen.findByText("Add interview"));
    const star = (group: string, n: number) => screen.getByRole("radiogroup", { name: group }).querySelectorAll('[role="radio"]')[n - 1] as HTMLElement;
    act(() => { star("Technical rating", 4).click(); star("Communication rating", 5).click(); star("Problem solving rating", 3).click(); });   // one tick, no re-render between
    fireEvent.click(screen.getByText("Save interview"));
    await waitFor(() => expect(mocked.post).toHaveBeenCalledTimes(1));
    expect(mocked.post.mock.calls[0][1].ratings).toEqual({ technical: 4, communication: 5, problem_solving: 3 });
  });

  it("edits an existing note with a PATCH and deletes only after confirmation", async () => {
    mocked.patch.mockResolvedValue({ data: note() });
    mocked.delete.mockResolvedValue({});
    setup([note()]);
    fireEvent.click(await screen.findByLabelText("Edit Technical interview note"));
    expect((screen.getByLabelText("Interviewer") as HTMLInputElement).value).toBe("Asha");
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Updated." } });
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => expect(mocked.patch).toHaveBeenCalledWith("/candidates/7/interviews/1", expect.objectContaining({ notes: "Updated." })));

    const confirmSpy = vi.spyOn(window, "confirm");
    confirmSpy.mockReturnValueOnce(false);
    fireEvent.click(await screen.findByLabelText("Delete Technical interview note"));
    expect(mocked.delete).not.toHaveBeenCalled();
    confirmSpy.mockReturnValueOnce(true);
    fireEvent.click(screen.getByLabelText("Delete Technical interview note"));
    await waitFor(() => expect(mocked.delete).toHaveBeenCalledWith("/candidates/7/interviews/1"));
    confirmSpy.mockRestore();
  });
});

function within4(group: HTMLElement) { return group.querySelectorAll('[role="radio"]')[3] as HTMLElement; }
