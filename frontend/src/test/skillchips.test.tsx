import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SkillChips } from "../components/ui";
import { educationVerdict, experienceVerdict, warningText } from "../utils";

describe("SkillChips: exact, related and missing look different (table and detail page share this component)", () => {
  it("renders three distinct kinds with distinct icons", () => {
    const { container } = render(<SkillChips matched={["Python"]} related={["FastAPI or Django"]} missing={["Docker"]} />);
    const kinds = Array.from(container.querySelectorAll("[data-kind]")).map((e) => e.getAttribute("data-kind"));
    expect(kinds).toEqual(["matched", "related", "missing"]);
    expect(screen.getByText("✓ Python")).toBeInTheDocument();
    expect(screen.getByText("≈ FastAPI or Django")).toBeInTheDocument();
    expect(screen.getByText("✗ Docker")).toBeInTheDocument();
    const classes = Array.from(container.querySelectorAll("[data-kind]")).map((e) => e.className);
    expect(new Set(classes).size).toBe(3);
  });
  it("a related skill is never styled as matched", () => {
    const { container } = render(<SkillChips matched={[]} related={["PostgreSQL"]} missing={[]} />);
    expect(container.querySelector('[data-kind="matched"]')).toBeNull();
    expect(container.querySelector('[data-kind="related"]')?.className).toMatch(/dashed/);
  });
  it("caps each group and summarises the rest", () => {
    render(<SkillChips matched={["A", "B", "C", "D", "E"]} related={[]} missing={["X", "Y", "Z"]} max={{ matched: 3, related: 2, missing: 1 }} />);
    expect(screen.getByText("+2 matched")).toBeInTheDocument();
    expect(screen.getByText("+2 missing")).toBeInTheDocument();
  });
});

describe("verdicts", () => {
  const base = { status: "scored", required_min_years: 3, preferred_years: null, relevant_effective_years: 4.5 };
  it("experience: meets / slightly below / below / unverified / claimed / not stated", () => {
    expect(experienceVerdict(base).label).toBe("Meets the requirement");
    expect(experienceVerdict({ ...base, relevant_effective_years: 2.4 }).tone).toBe("amber");
    expect(experienceVerdict({ ...base, relevant_effective_years: 1 }).tone).toBe("red");
    expect(experienceVerdict({ ...base, preferred_years: 4, relevant_effective_years: 5 }).label).toBe("Exceeds the requirement");
    expect(experienceVerdict({ ...base, status: "unverified", relevant_effective_years: 0 }).label).toMatch(/Cannot verify/);
    expect(experienceVerdict({ ...base, claimed_years: 6 }).label).toMatch(/Claimed 6 y/);
    expect(experienceVerdict({ ...base, required_min_years: null }).tone).toBe("slate");
  });
  it("education verdict", () => {
    expect(educationVerdict(3, 4).tone).toBe("green");
    expect(educationVerdict(4, 3).tone).toBe("red");
    expect(educationVerdict(3, null).tone).toBe("amber");
    expect(educationVerdict(null, 3).tone).toBe("slate");
  });
  it("hides noise warnings, shows OCR warning in plain words", () => {
    expect(warningText("docx_has_no_page_numbers")).toBeNull();
    expect(warningText("ocr_used")).toMatch(/OCR/);
  });
});

import { rescaleNote } from "../utils";
describe("rescaleNote", () => {
  it("explains rescaled weights when Projects had no evidence", () => {
    const note = rescaleNote({
      technical_skills: { status: "scored", weight_configured: 0.4, weight_effective: 0.4211 },
      project_domain: { status: "unverified", weight_configured: 0.05, weight_effective: 0 },
    });
    expect(note).toMatch(/Projects & domain had no evidence/);
    expect(note).toMatch(/rescaled to add up to 100%/);
    expect(note).toMatch(/42\.1% instead of the configured 40%/);
  });
  it("stays silent when nothing was left out", () => {
    expect(rescaleNote({ technical_skills: { status: "scored", weight_configured: 0.4, weight_effective: 0.4 } })).toBeNull();
  });
});
