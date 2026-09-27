import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { transcribeAudio, useVoiceStatus } from '../api/hooks'
import { toWav16kMono } from '../lib/wav'
import { Button } from './ui'

// First type the browser supports (PLAN.md §12). Chrome/Android record WebM, Safari/iOS MP4; wav.ts converts either.
const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
const MAX_SECONDS = 60

/** Microphone access needs HTTPS (localhost is exempt) and MediaRecorder support. */
function canRecord(): boolean {
  return window.isSecureContext && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function errorMessage(err: unknown): string {
  if (err instanceof DOMException && err.name === 'NotAllowedError')
    return 'Microphone permission is blocked. Allow it in your browser settings, or type instead.'
  if (err instanceof ApiError) return err.message
  return "Voice input didn't work this time. Try again or type instead."
}

/**
 * Tap to record, tap to stop. The words land in the request box, where the requester can fix them before continuing.
 * Renders nothing when the server has no transcription key or the browser can't record.
 */
export default function VoiceRecorder({ onText, disabled }: { onText: (text: string) => void; disabled?: boolean }) {
  const status = useVoiceStatus()
  const [state, setState] = useState<'idle' | 'recording' | 'working'>('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const discard = useRef(false)

  // Leaving the page mid-recording releases the microphone and drops the clip. Reset on mount: React's StrictMode
  // runs this cleanup once in development before mounting again, and a flag left true would drop every recording.
  useEffect(() => {
    discard.current = false
    return () => {
      discard.current = true
      window.clearInterval(timer.current)
      if (recorder.current?.state === 'recording') recorder.current.stop()
    }
  }, [])

  if (!status.data?.transcribe || !canRecord()) return null

  const finish = async (clip: Blob) => {
    setState('working')
    try {
      const { text } = await transcribeAudio(await toWav16kMono(clip))
      if (text) onText(text)
      else setError("We didn't catch any words. Try again a little closer to the microphone.")
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setState('idle')
    }
  }

  const stop = () => {
    window.clearInterval(timer.current)
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }

  const start = async () => {
    setError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err) {
      setError(errorMessage(err))
      return
    }
    const mimeType = MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t))
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    rec.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data)
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      if (!discard.current) void finish(new Blob(chunks, { type: rec.mimeType }))
    }
    recorder.current = rec
    rec.start()
    setSeconds(0)
    setState('recording')
    let elapsed = 0
    timer.current = window.setInterval(() => {
      elapsed += 1
      setSeconds(elapsed)
      if (elapsed >= MAX_SECONDS) stop()
    }, 1000)
  }

  return (
    <div className="mt-3">
      {state === 'recording' ? (
        <Button type="button" variant="danger" className="w-full" onClick={stop}>
          <span aria-hidden className="mr-2 inline-block h-3 w-3 animate-pulse rounded-full bg-alert" />
          Stop recording ({clock(seconds)} of {clock(MAX_SECONDS)})
        </Button>
      ) : (
        <Button type="button" variant="quiet" className="w-full" onClick={start} disabled={disabled || state === 'working'}>
          {state === 'working' ? 'Turning your words into text…' : 'Say it instead'}
        </Button>
      )}
      <p role="status" className="sr-only">
        {state === 'recording' ? 'Recording' : state === 'working' ? 'Transcribing' : ''}
      </p>
      {error && (
        <p role="alert" className="mt-2 text-sm text-alert">
          {error}
        </p>
      )}
    </div>
  )
}
