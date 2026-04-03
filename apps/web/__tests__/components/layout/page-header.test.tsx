import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { PageHeader } from "@/components/layout/page-header"

describe("PageHeader", () => {
  it("renders the title", () => {
    render(<PageHeader title="Members" />)
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Members",
    )
  })

  it("renders the description when provided", () => {
    render(
      <PageHeader title="Members" description="Manage your club members" />,
    )
    expect(screen.getByText("Manage your club members")).toBeInTheDocument()
  })

  it("does not render description when not provided", () => {
    const { container } = render(<PageHeader title="Members" />)
    expect(container.querySelector("p")).toBeNull()
  })

  it("renders children as action buttons", () => {
    render(
      <PageHeader title="Members">
        <button>Add Member</button>
      </PageHeader>,
    )
    expect(screen.getByText("Add Member")).toBeInTheDocument()
  })

  it("does not render action container when no children", () => {
    const { container } = render(<PageHeader title="Members" />)
    // Only one direct child div (the title area), no actions wrapper
    const wrapper = container.firstElementChild!
    expect(wrapper.children).toHaveLength(1)
  })
})
