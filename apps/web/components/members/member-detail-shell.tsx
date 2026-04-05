"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"
import { SubNavLayout } from "@/components/layout/sub-nav-layout"
import { useMember, useUpdateMember, useDeleteMember } from "@/hooks/use-members"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { MemberSwitcher } from "@/components/members/member-switcher"
import { useErrorMessage } from "@/lib/errors"
import { toast } from "sonner"
import type { Member } from "@/lib/types/member"

interface MemberDetailContextValue {
  form: Record<string, string | null>
  handleChange: (name: string, value: string | null) => void
  member: Member
}

import { createContext, useContext } from "react"

const MemberDetailContext = createContext<MemberDetailContextValue | null>(null)

export function useMemberDetail() {
  const ctx = useContext(MemberDetailContext)
  if (!ctx) throw new Error("useMemberDetail must be used within MemberDetailShell")
  return ctx
}

interface MemberDetailShellProps {
  memberId: string
  children: React.ReactNode
}

export function MemberDetailShell({ memberId, children }: MemberDetailShellProps) {
  const t = useTranslations("members")
  const tc = useTranslations("common")
  const router = useRouter()
  const { data: member, isLoading } = useMember(memberId)
  const updateMember = useUpdateMember()
  const deleteMember = useDeleteMember()
  const [form, setForm] = useState<Record<string, string | null>>({})
  const [dirty, setDirty] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const getErrorMessage = useErrorMessage()

  useEffect(() => {
    if (member) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm({
        first_name: member.first_name,
        last_name: member.last_name,
        email: member.email,
        phone: member.phone,
        mobile: member.mobile,
        birthday: member.birthday,
        street: member.street,
        zip_code: member.zip_code,
        city: member.city,
        state: member.state,
        country: member.country,
        joined_at: member.joined_at,
        left_at: member.left_at,
        status: member.status,
        category: member.category,
        notes: member.notes,
      })
      setDirty(false)
    }
  }, [member])

  function handleChange(name: string, value: string | null) {
    setForm((prev) => ({ ...prev, [name]: value === "" ? null : value }))
    setDirty(true)
  }

  function handleSave() {
    updateMember.mutate(
      { id: memberId, data: form },
      {
        onSuccess: () => {
          toast.success(tc("saved"))
          setDirty(false)
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    )
  }

  function handleDelete() {
    deleteMember.mutate(memberId, {
      onSuccess: () => {
        toast.success(tc("saved"))
        setConfirmDelete(false)
        router.push("/members")
      },
      onError: (err) => toast.error(err.message),
    })
  }

  if (isLoading || !member) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      </div>
    )
  }

  const navItems = [
    { label: t("personalInfo"), href: `/members/${memberId}` },
    { label: t("membershipInfo"), href: `/members/${memberId}/membership` },
  ]

  return (
    <MemberDetailContext.Provider value={{ form, handleChange, member }}>
      <div className="space-y-6">
        <PageHeader
          title={
            <MemberSwitcher
              currentId={memberId}
              currentLabel={`${member.first_name} ${member.last_name}`}
            />
          }
          description={t("memberLabel", { number: member.member_number })}
        >
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => router.push("/members")}>
              ← {t("title")}
            </Button>
            {dirty && (
              <Button onClick={handleSave} disabled={updateMember.isPending}>
                {updateMember.isPending ? tc("saving") : tc("save")}
              </Button>
            )}
            <Button
              variant="destructive"
              onClick={() => setConfirmDelete(true)}
            >
              {t("deleteMember")}
            </Button>
          </div>
        </PageHeader>

        <SubNavLayout items={navItems}>{children}</SubNavLayout>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("deleteMember")}
        description={t("deleteConfirm")}
        destructive
        pending={deleteMember.isPending}
        onConfirm={handleDelete}
      />
    </MemberDetailContext.Provider>
  )
}
