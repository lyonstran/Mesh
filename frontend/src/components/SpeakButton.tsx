import { useEffect, useRef, useState } from 'react'
import { speakText, useVoiceStatus } from '../api/hooks'
import { encodeWav } from '../lib/wav'
import { Button } from './ui'

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

  return (
    <span className="inline-flex flex-col items-start">
      <Button type="button" variant="quiet" className="min-h-10 px-4 text-sm" onClick={toggle} disabled={state === 'loading'}>
        {state === 'loading' ? 'Loading…' : state === 'playing' ? 'Stop' : 'Tap to hear'}
      </Button>
      {failed && <span className="mt-1 text-sm text-alert">Couldn't play the audio. Try again.</span>}
    </span>
  )
}
