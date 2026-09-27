import type { CSSProperties } from 'react'

/** Style for an `animate-rise stagger` item: its position in the list sets the delay (see index.css). */
export function stagger(index: number): CSSProperties {
  return { '--i': index } as CSSProperties
}
