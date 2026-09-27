import { useEffect, useRef, useState } from 'react'
import { speakText, useVoiceStatus } from '../api/hooks'
import { encodeWav } from '../lib/wav'

/** Point the player at `src` and start it. Kept outside the component: it mutates a DOM element, not React state. */
function playFrom(player: HTMLAudioElement, src: string, onEnded?: () => void): Promise<void> {
  player.src = src
  player.onended = onEnded ?? null
  return player.play()
}

/**
 * "Tap to hear": reads `text` aloud with ElevenLabs. It's a button, not autoplay, because iOS blocks autoplay
 * (PLAN.md §12). Renders nothing when the server has no text-to-speech key.
 */
export default function SpeakButton({ text, language = 'en' }: { text: string; language?: string }) {
  const status = useVoiceStatus()
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const [failed, setFailed] = useState(false)
  const audio = useRef<HTMLAudioElement | null>(null)
  const clip = useRef<{ text: string; url: string } | null>(null)

  useEffect(
    () => () => {
      audio.current?.pause()
      if (clip.current) URL.revokeObjectURL(clip.current.url)
    },
    [],
  )

  if (!status.data?.speak) return null

  const toggle = async () => {
    if (state === 'playing') {
      audio.current?.pause()
      setState('idle')
      return
    }
    setFailed(false)
    // iOS only lets audio play from a tap. Start a silent clip now, while this is still the tap, so the element
    // stays allowed to play once the real audio arrives from the network.
    const player = audio.current ?? new Audio()
    audio.current = player
    const silence = URL.createObjectURL(encodeWav(new Float32Array(160), 16_000))
    void playFrom(player, silence).catch(() => {})
    setState('loading')
    try {
      if (clip.current?.text !== text) {
        if (clip.current) URL.revokeObjectURL(clip.current.url)
        clip.current = { text, url: URL.createObjectURL(await speakText(text, language)) }
      }
      await playFrom(player, clip.current.url, () => setState('idle'))
      setState('playing')
    } catch {
      setFailed(true)
      setState('idle')
    } finally {
      URL.revokeObjectURL(silence)
    }
  }

  const label = state === 'loading' ? 'Loading…' : state === 'playing' ? 'Stop' : 'Listen'
  return (
    <span className="inline-flex flex-col items-start">
      <button
        type="button"
        onClick={toggle}
        disabled={state === 'loading'}
        aria-label={state === 'idle' ? 'Listen: read this update aloud' : label}
        className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full bg-surface px-4 text-sm font-semibold ring-1 ring-line transition duration-150 hover:ring-brand-strong disabled:opacity-60"
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          {state === 'playing' ? (
            <rect x="7" y="7" width="10" height="10" rx="1.5" />
          ) : (
            <>
              <path d="M11 5L6 9H3v6h3l5 4z" />
              <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
            </>
          )}
        </svg>
        {label}
      </button>
      {failed && <span className="mt-1 text-sm text-alert">Couldn't play the audio. Try again.</span>}
    </span>
  )
}
