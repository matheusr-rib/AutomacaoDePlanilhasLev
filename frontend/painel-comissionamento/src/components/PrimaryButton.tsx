interface PrimaryButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean
  label: string
}

export function PrimaryButton({ loading, label, ...props }: PrimaryButtonProps) {
  return (
    <button
      {...props}
      disabled={loading || props.disabled}
      className={[
        "w-full flex items-center justify-center gap-2",
        "rounded-lg px-5 py-3 font-medium",
        "bg-[#6D28D9] hover:bg-[#5B21B6]", // roxo sólido (Lev vibe)
        "disabled:opacity-60 disabled:cursor-not-allowed",
        "transition-colors",
      ].join(" ")}
    >
      {loading && (
        <span className="inline-block w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
      )}
      {label}
    </button>
  )
}
