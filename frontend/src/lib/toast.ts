import { createContext, useContext } from 'react'

export type ToastKind = 'success' | 'error'

export interface ToastInput {
  kind: ToastKind
  message: string
}

export const ToastContext = createContext<((t: ToastInput) => void) | null>(null)

/** Show a toast: `toast({ kind: 'success', message: 'Profile saved.' })`. */
export function useToast(): (t: ToastInput) => void {
  const toast = useContext(ToastContext)
  if (!toast) throw new Error('useToast must be used inside <ToastProvider>')
  return toast
}
