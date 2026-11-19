import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import PoolBanner from "../components/PoolBanner";
import { Pool } from "../types";

const base: Pool = { files_received: 71, stored: 70, parsed: 68, failed: 2, duplicates_skipped: 1, ranked_in_run: 17, not_in_run: 51, run_is_stale: true };
const show = (pool: Pool) => render(<MemoryRouter><PoolBanner pool={pool} jobId={1} onRerun={vi.fn()} /></MemoryRouter>);

describe("PoolBanner", () => {
  it("accounts for every file and warns when the ranking is older than the resume pool", () => {
    show(base);
    expect(screen.getByRole("alert").textContent).toMatch(/51 parsed resumes were uploaded after this ranking/);
    expect(screen.getByTestId("pool-banner").textContent).toMatch(/71 files received.*68 parsed.*2 failed.*1 identical duplicate skipped.*17 of 68/);
    expect(screen.getByRole("button", { name: /Re-run matching/ })).toBeTruthy();
  });
  it("shows no warning when every parsed resume is ranked", () => {
    show({ ...base, ranked_in_run: 68, not_in_run: 0, run_is_stale: false });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
