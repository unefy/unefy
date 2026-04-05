interface PageHeaderProps {
  title: React.ReactNode
  description?: string
  children?: React.ReactNode // Right-side actions (buttons etc.)
}

export function PageHeader({ title, description, children }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        {typeof title === "string" ? (
          <h1 className="truncate text-2xl font-bold tracking-tight">{title}</h1>
        ) : (
          title
        )}
        {description && (
          <p className="text-muted-foreground mt-3 text-sm">{description}</p>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
