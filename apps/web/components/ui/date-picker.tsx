"use client"

import * as React from "react"
import { format, parse, isValid } from "date-fns"
import { de } from "date-fns/locale"
import { Calendar03Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface DatePickerProps {
  value?: string // ISO date string "YYYY-MM-DD"
  onChange?: (value: string) => void
  placeholder?: string
}

const INPUT_FORMAT = "dd.MM.yyyy"

function parseInput(input: string): Date | null {
  const formats = ["dd.MM.yyyy", "dd/MM/yyyy", "dd.MM.yy", "dd/MM/yy", "yyyy-MM-dd"]

  for (const fmt of formats) {
    const d = parse(input.trim(), fmt, new Date())
    if (isValid(d)) {
      // Fix two-digit years: 00-49 → 2000-2049, 50-99 → 1950-1999
      if (fmt.endsWith("yy") && !fmt.endsWith("yyyy")) {
        const year = d.getFullYear()
        if (year < 100) {
          d.setFullYear(year <= 49 ? 2000 + year : 1900 + year)
        }
      }
      return d
    }
  }
  return null
}

export function DatePicker({
  value,
  onChange,
  placeholder = "dd.mm.yyyy",
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)

  const date = value ? parse(value, "yyyy-MM-dd", new Date()) : undefined
  const validDate = date && isValid(date) ? date : undefined

  const [inputValue, setInputValue] = React.useState(
    validDate ? format(validDate, INPUT_FORMAT) : ""
  )

  // Sync input when value changes externally.
  // validDate is derived from value, so tracking value alone is sufficient.
  React.useEffect(() => {
    if (validDate) {
      setInputValue(format(validDate, INPUT_FORMAT))
    } else if (!value) {
      setInputValue("")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInputValue(e.target.value)
  }

  function handleInputBlur() {
    if (inputValue === "") {
      onChange?.("")
      return
    }

    // Only try to parse if input looks like a complete date (min 8 chars: dd.MM.yy)
    if (inputValue.length < 8) {
      setInputValue(validDate ? format(validDate, INPUT_FORMAT) : "")
      return
    }

    const parsed = parseInput(inputValue)
    if (parsed) {
      setInputValue(format(parsed, INPUT_FORMAT))
      onChange?.(format(parsed, "yyyy-MM-dd"))
    } else {
      setInputValue(validDate ? format(validDate, INPUT_FORMAT) : "")
    }
  }

  function handleCalendarSelect(day: Date | undefined) {
    if (day) {
      onChange?.(format(day, "yyyy-MM-dd"))
      setInputValue(format(day, INPUT_FORMAT))
    }
    setOpen(false)
  }

  return (
    <div className="relative max-w-56">
      <input
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        onBlur={handleInputBlur}
        placeholder={placeholder}
        className="h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 pr-10 text-sm transition-[color,box-shadow,background-color] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          tabIndex={-1}
          aria-label="Open calendar"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
        >
          <HugeiconsIcon icon={Calendar03Icon} size={16} />
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="end">
          <Calendar
            mode="single"
            captionLayout="dropdown"
            selected={validDate}
            onSelect={handleCalendarSelect}
            locale={de}
            defaultMonth={validDate}
            startMonth={new Date(1900, 0)}
            endMonth={new Date(2100, 11)}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}
