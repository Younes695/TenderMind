import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Public pages must render: a missing useT() once blanked the whole landing page.
const PAGES = ["Home", "Pricing", "Solution", "Industries", "Security", "Login", "Signup"];

describe("public pages render without crashing", () => {
  for (const name of PAGES) {
    it(name, async () => {
      vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, headers: { get: () => "application/json" },
        json: async () => ({}), text: async () => "{}" })));
      const { default: Page } = await import(`../${name}.jsx`);
      const { container } = render(<MemoryRouter><Page /></MemoryRouter>);
      expect(container.textContent.length).toBeGreaterThan(20);
    });
  }
});
