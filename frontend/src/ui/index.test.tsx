import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Modal, Tabs } from ".";
describe("shared controls", () => {
  it("closes a modal with Escape", async () => { const user = userEvent.setup(); const close = vi.fn(); render(<Modal title="Edit" onClose={close} footer={<button>Save</button>}><input aria-label="Title" /></Modal>); await user.keyboard("{Escape}"); expect(close).toHaveBeenCalledOnce(); });
  it("moves tabs with arrow keys", async () => { const user = userEvent.setup(); const change = vi.fn(); render(<Tabs value="one" onChange={change} tabs={[{ value: "one", label: "One" }, { value: "two", label: "Two" }]} />); await user.click(screen.getByRole("tab", { name: "One" })); await user.keyboard("{ArrowRight}"); expect(change).toHaveBeenLastCalledWith("two"); });
});
