import {
  CalendarIcon,
  HouseIcon,
  ReceiptIcon,
  SettingsIcon,
  TrophyIcon,
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
      ],
    },
    {
      titleKey: "groups.clubLife",
      items: [
        {
          titleKey: "events",
          url: "/events",
          icon: CalendarIcon,
        },
        {
          titleKey: "competitions",
          url: "/competitions",
          icon: TrophyIcon,
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
            { titleKey: "settingsAccess", url: "/settings/access" },
          ],
        },
      ],
    },
  ],
}
