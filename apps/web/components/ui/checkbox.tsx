"use client"

import * as React from "react"
import { Checkbox as CheckboxPrimitive } from "@base-ui/react/checkbox"
import { HugeiconsIcon } from "@hugeicons/react"
import { Tick02Icon, MinusSignIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

function Checkbox({
  className,
  ...props
}: CheckboxPrimitive.Root.Props) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "group inline-flex size-4 shrink-0 items-center justify-center rounded-[4px] border border-input bg-transparent outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 aria-invalid:border-destructive data-checked:border-primary data-checked:bg-primary data-checked:text-primary-foreground data-indeterminate:border-primary data-indeterminate:bg-primary data-indeterminate:text-primary-foreground data-disabled:cursor-not-allowed data-disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <HugeiconsIcon
        icon={Tick02Icon}
        size={12}
        strokeWidth={3}
        className="hidden group-data-checked:block"
      />
      <HugeiconsIcon
        icon={MinusSignIcon}
        size={12}
        strokeWidth={3}
        className="hidden group-data-indeterminate:block"
      />
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
