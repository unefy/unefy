import {
  AwardIcon,
  CalendarIcon,
  CircleUserIcon,
  ClipboardCheckIcon,
  HouseIcon,
  ReceiptIcon,
  SettingsIcon,
  TargetIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react"

/**
 * Titles are i18n keys resolved in `nav-main`, not literal strings — all
 * UI text goes through next-intl.
 */
export type NavItem = {
  titleKey: string
  url: string
  icon?: LucideIcon
  badge?: string
  items?: { titleKey: string; url: string }[]
  /** Shown only when the club has this module active (see `Club.modules`). */
  module?: string
  /** Shown only to these roles. Backend authorization is the real boundary —
   * this merely keeps nav entries that would 404 out of sight. */
  roles?: string[]
}

export type NavGroup = {
  titleKey: string
  items: NavItem[]
}

export type SidebarData = {
  navGroups: NavGroup[]
}

export const sidebarData: SidebarData = {
  navGroups: [
    {
      titleKey: "groups.start",
      items: [
        {
          titleKey: "dashboard",
          url: "/",
          icon: HouseIcon,
        },
        {
          titleKey: "myArea",
          url: "/my",
          icon: CircleUserIcon,
        },
      ],
    },
    {
      titleKey: "groups.people",
      items: [
        {
          titleKey: "members",
          url: "/members",
          icon: UsersIcon,
        },
        {
          titleKey: "functionHolders",
          url: "/functions",
          icon: AwardIcon,
        },
      ],
    },
    {
      titleKey: "groups.clubLife",
      items: [
        {
          titleKey: "attendance",
          url: "/attendance",
          icon: ClipboardCheckIcon,
        },
        {
          titleKey: "events",
          url: "/events",
          icon: CalendarIcon,
        },
        // Wettkämpfe are built in the backend and in the Android app, but have
        // no web page yet — an entry here would only lead to a 404. It comes
        // back with its page (docs/plans/roadmap.md).
        {
          titleKey: "shooting",
          url: "/shooting",
          icon: TargetIcon,
          module: "shooting",
          // The whole module is board work — a member would only find 404s.
          roles: ["owner", "admin", "board"],
          items: [
            { titleKey: "shootingProof", url: "/shooting" },
            { titleKey: "shootingRules", url: "/shooting/rules" },
          ],
        },
      ],
    },
    {
      titleKey: "groups.finance",
      items: [
        {
          titleKey: "dues",
          url: "/dues",
          icon: ReceiptIcon,
          items: [
            { titleKey: "dues", url: "/dues" },
            { titleKey: "feeTypes", url: "/dues/fee-types" },
          ],
        },
      ],
    },
    {
      titleKey: "groups.other",
      items: [
        {
          titleKey: "settings",
          url: "/settings",
          icon: SettingsIcon,
          // Only pages that exist. The contact/defaults/fees/payment entries
          // were left over from the rebuild and led nowhere; they come back
          // with their pages.
          items: [
            { titleKey: "settingsGeneral", url: "/settings" },
            { titleKey: "settingsSports", url: "/settings/sports" },
            { titleKey: "settingsFunctions", url: "/settings/functions" },
            { titleKey: "settingsAccess", url: "/settings/access" },
          ],
        },
      ],
    },
  ],
}
