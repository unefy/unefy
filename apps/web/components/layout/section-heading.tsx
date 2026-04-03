interface SectionHeadingProps {
  title: string
  description: string
}

export function SectionHeading({ title, description }: SectionHeadingProps) {
  return (
    <div className="mb-5">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-muted-foreground mt-0.5 text-sm">{description}</p>
    </div>
  )
}
