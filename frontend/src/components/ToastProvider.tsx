import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastInput } from '../lib/toast'

interface Toast extends ToastInput {
  id: number
}

const DURATION_MS = { success: 4000, error: 7000 } as const

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), DURATION_MS[toast.kind])
    return () => clearTimeout(timer)
  }, [toast, onDismiss])

  const success = toast.kind === 'success'
  return (
    <div
      role={success ? 'status' : 'alert'}
      className={`toast-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl px-4 py-3 text-white shadow-lg ${
        success ? 'bg-ok' : 'bg-alert'
      }`}
    >
      <span aria-hidden className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-white/20 text-sm font-extrabold">
        {success ? '✓' : '!'}
      </span>
      <p className="flex-1 font-semibold">{toast.message}</p>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(toast.id)}
        className="-my-1 -mr-2 flex size-8 shrink-0 items-center justify-center rounded-full text-lg leading-none text-white/80 hover:bg-white/15 hover:text-white"
      >
        ×
      </button>
    </div>
  )
}

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), [])
  const show = useCallback((t: ToastInput) => {
    const id = nextId.current++
    setToasts((all) => [...all.slice(-2), { ...t, id }]) // keep at most 3 on screen
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-20 z-50 flex flex-col items-center gap-2 px-4">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
