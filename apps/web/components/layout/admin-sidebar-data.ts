import {
  BuildingIcon,
  DumbbellIcon,
  GaugeIcon,
  ScrollTextIcon,
  TargetIcon,
  UsersIcon,
} from "lucide-react"

import type { SidebarData } from "@/components/layout/sidebar-data"

/**
 * Navigation for the platform admin area. Titles are i18n keys resolved
 * against the `adminNav` namespace, mirroring how the club app uses `nav`.
 */
export const adminSidebarData: SidebarData = {
  navGroups: [
    {
      titleKey: "groups.overview",
      items: [{ titleKey: "dashboard", url: "/admin", icon: GaugeIcon }],
    },
    {
      titleKey: "groups.platform",
      items: [
        { titleKey: "tenants", url: "/admin/tenants", icon: BuildingIcon },
        { titleKey: "users", url: "/admin/users", icon: UsersIcon },
      ],
    },
    {
      titleKey: "groups.masterData",
      items: [
        { titleKey: "sports", url: "/admin/sports", icon: TargetIcon },
        {
          titleKey: "disciplines",
          url: "/admin/disciplines",
          icon: DumbbellIcon,
        },
      ],
    },
    {
      titleKey: "groups.security",
      items: [
        { titleKey: "auditLog", url: "/admin/audit-log", icon: ScrollTextIcon },
      ],
    },
  ],
}
