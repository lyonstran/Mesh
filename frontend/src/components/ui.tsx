import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'accent' | 'quiet' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-ink hover:bg-emerald-400',
  accent: 'bg-brand text-ink hover:bg-emerald-400',
  quiet: 'border border-line bg-surface text-ink hover:border-ink-soft',
  danger: 'border border-alert/40 bg-surface text-alert hover:border-alert',
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-12 items-center justify-center cursor-pointer rounded-lg px-5 font-semibold transition duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    />
  )
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : 'Something went wrong'
  return (
    <p role="alert" className="mt-3 text-alert">
      {message}
    </p>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <p className="py-10 text-center text-ink-soft">{label}…</p>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="font-semibold">{label}</span>
      {hint && <span className="mt-0.5 block text-sm text-ink-soft">{hint}</span>}
      <span className="mt-2 block">{children}</span>
    </label>
  )
}

export const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-3 text-ink placeholder:text-ink-soft/70 focus:border-emerald-600 focus:outline-none'
