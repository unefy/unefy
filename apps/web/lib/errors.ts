"use client"

import { useTranslations } from "next-intl"

import { ApiError } from "@/lib/api-client"

/**
 * Maps backend error codes (from the `{error:{code,message}}` envelope)
 * to i18n keys inside the `errors.*` namespace. Add a new entry here
 * whenever the backend introduces a new error code.
 */
const ERROR_CODE_TO_KEY: Record<string, string> = {
  NOT_FOUND: "notFound",
  FORBIDDEN: "forbidden",
  CONFLICT: "conflict",
  VALIDATION_ERROR: "validation",
  INTERNAL_ERROR: "internal",
  UNKNOWN: "unknown",
}

const FALLBACK_KEY = "unknown"

/** Resolve a backend error code to its i18n key in the `errors.*` namespace. */
export function errorCodeToKey(code: string): string {
  return ERROR_CODE_TO_KEY[code] ?? FALLBACK_KEY
}

/**
 * React hook that returns a function resolving any thrown error into a
 * user-facing, translated message. Raw backend messages are never shown
 * to the user — those may contain implementation details.
 */
export function useErrorMessage(): (error: unknown) => string {
  const t = useTranslations("errors")
  return (error: unknown): string => {
    if (error instanceof ApiError) {
      const key = ERROR_CODE_TO_KEY[error.code] ?? FALLBACK_KEY
      return t(key)
    }
    return t(FALLBACK_KEY)
  }
}
