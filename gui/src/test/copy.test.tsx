import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CopyButton } from "../components/CopyButton";

function clipboard(writeText: (text: string) => Promise<void>): void {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("copy button", () => {
  it("copies the full value and says so", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    clipboard(writeText);
    render(<CopyButton value={"a".repeat(64)} what="SHA-256 of finger.png" />);
    await userEvent.click(screen.getByRole("button", { name: "Copy SHA-256 of finger.png" }));
    expect(writeText).toHaveBeenCalledWith("a".repeat(64));
    expect(screen.getByRole("button")).toHaveTextContent("Copied");
    expect(screen.getByRole("status")).toHaveTextContent("SHA-256 of finger.png copied"); // announced
  });

  it("says when the copy failed", async () => {
    const writeText = vi.fn(() => Promise.reject(new Error("denied")));
    clipboard(writeText);
    render(<CopyButton value="0123456789abcdef" what="signing key id" />);
    await act(async () => {
      await userEvent.click(screen.getByRole("button"));
    });
    expect(screen.getByRole("button")).toHaveTextContent("Copy failed");
    expect(screen.getByRole("status")).toHaveTextContent("Copying the signing key id failed");
  });
});
