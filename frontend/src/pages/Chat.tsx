import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { listMessages, sendMessage, useMe, useRequest, useRequestAction } from '../api/hooks'
import { homeFor } from '../auth/home'
import LiveTracking from '../components/LiveTracking'
import { RequestTags, RequestText } from '../components/RequestTags'
import { Button, ErrorText, Loading, inputClass } from '../components/ui'
import { STATUS_LABELS } from '../lib/labels'
import type { HelpRequest, Message, RequesterFlags } from '../lib/types'

const POLL_CHAT_MS = 3_000

const FLAG_TEXT: Record<keyof RequesterFlags, string> = {
  medical_device: 'Relies on a powered medical device',
  mobility: 'Limited mobility',
  lives_alone: 'Lives alone',
}

/** Polls for new messages using `after` so each poll only returns what's new. */
function useChatMessages(requestId: string, enabled: boolean) {
  const [messages, setMessages] = useState<Message[]>([])
  const [error, setError] = useState<unknown>(null)
  const lastTs = useRef<string | undefined>(undefined)

  const add = useCallback((incoming: Message[]) => {
    if (incoming.length === 0) return
    setMessages((prev) => {
      const seen = new Set(prev.map((m) => m.id))
      return [...prev, ...incoming.filter((m) => !seen.has(m.id))]
    })
    lastTs.current = incoming[incoming.length - 1].ts
  }, [])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    const poll = () =>
      listMessages(requestId, lastTs.current)
        .then(({ messages: m }) => !cancelled && (setError(null), add(m)))
        .catch((e) => !cancelled && setError(e))
    poll()
    const timer = setInterval(poll, POLL_CHAT_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [requestId, enabled, add])

  return { messages, error, add }
}

function RequestSummary({ request }: { request: HelpRequest }) {
  const flags = request.requester?.requester_flags
  const activeFlags = flags ? (Object.keys(FLAG_TEXT) as (keyof RequesterFlags)[]).filter((k) => flags[k]) : []
  return (
    <details className="rounded-2xl border border-line bg-surface p-4" open>
      <summary className="cursor-pointer font-semibold">Request</summary>
      <div className="mt-3">
        <RequestTags request={request} showFlags />
      </div>
      <div className="mt-2">
        <RequestText request={request} size="base" />
      </div>
      {request.requester?.background && <p className="mt-2 text-sm text-ink-soft">About them: {request.requester.background}</p>}
      {activeFlags.length > 0 && !request.flags?.length && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {activeFlags.map((k) => (
            <li key={k} className="rounded-full bg-brand-soft px-3 py-1 text-sm font-semibold">
              {FLAG_TEXT[k]}
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}

export default function Chat() {
  const { requestId = '' } = useParams()
  const navigate = useNavigate()
  const req = useRequest(requestId)
  const home = homeFor(useMe().data?.user.role ?? null)
  const action = useRequestAction()
  const request = req.data?.request
  const chatOpen = request?.status === 'CLAIMED' || request?.status === 'RESOLVED'
  const { messages, error, add } = useChatMessages(requestId, !!chatOpen)
  const [draft, setDraft] = useState('')
  const [sendError, setSendError] = useState<unknown>(null)
  const [sending, setSending] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  // Block body on purpose: newer browsers return a Promise from scrollIntoView, and React would treat it as a cleanup.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length])

  if (req.isPending) return <Loading />
  if (req.error || !request) {
    const notFound = req.error instanceof ApiError && req.error.status === 404
    return (
      <div>
        <p className="text-alert">{notFound ? "This chat doesn't exist or isn't yours." : 'Could not load this chat.'}</p>
        <Link to={home} className="mt-4 inline-block font-semibold underline underline-offset-4">
          Back home
        </Link>
      </div>
    )
  }

  const isHelper = request.viewer_relation === 'assigned_helper'
  const other = isHelper ? request.requester?.name : request.helper?.name
  const canWrite = request.status === 'CLAIMED' && request.viewer_relation !== 'other'

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    setSending(true)
    try {
      const { message } = await sendMessage(requestId, text)
      add([message])
      setDraft('')
      setSendError(null)
    } catch (err) {
      setSendError(err)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to={home} className="inline-flex min-h-10 items-center gap-1 rounded-lg text-sm font-semibold text-ink-soft hover:text-ink">
          <span aria-hidden>←</span> Back
        </Link>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight">{other ? `Chat with ${other}` : 'Chat'}</h1>
        <p className="text-sm text-ink-soft">{STATUS_LABELS[request.status]}. Only the two of you can see this chat.</p>
      </div>

      {isHelper && <RequestSummary request={request} />}
      {!isHelper && (
        <p className="rounded-xl bg-surface p-4">
          <span className="font-semibold">Your request: </span>
          {request.text}
        </p>
      )}

      {request.status === 'CLAIMED' && request.viewer_relation !== 'other' && (
        <LiveTracking request={request} otherName={other ?? (isHelper ? 'the requester' : 'your volunteer')} />
      )}

      {!chatOpen && request.viewer_relation !== 'other' && (
        <p className="rounded-xl bg-surface p-4 text-ink-soft">The chat opens once a volunteer picks this request.</p>
      )}

      {chatOpen && (
        <section aria-label="Messages" className="flex min-h-64 flex-col gap-2 rounded-xl bg-surface p-3" aria-live="polite">
          {messages.length === 0 && (
            <p className="m-auto max-w-xs text-center text-ink-soft">
              {isHelper ? 'Say hello and ask what would help most.' : `${other ?? 'Your volunteer'} will message you here. You can start too.`}
            </p>
          )}
          {messages.map((m) => (
            <p
              key={m.id}
              className={`animate-fade-in max-w-[85%] rounded-2xl px-4 py-2 ${m.mine ? 'self-end rounded-br-sm bg-brand text-ink' : 'self-start rounded-bl-sm bg-ground'}`}
            >
              {m.text}
            </p>
          ))}
          <div ref={endRef} />
        </section>
      )}
      <ErrorText error={error} />

      {canWrite && (
        <form onSubmit={send} className="flex gap-2">
          <label htmlFor="chat-input" className="sr-only">
            Message
          </label>
          <input
            id="chat-input"
            className={inputClass}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write a message"
            maxLength={2000}
            autoComplete="off"
          />
          <Button type="submit" disabled={!draft.trim() || sending}>
            Send
          </Button>
        </form>
      )}
      <ErrorText error={sendError} />

      {request.status === 'CLAIMED' && (
        <div className="grid gap-3 pt-2 sm:grid-cols-2">
          <Button variant="quiet" disabled={action.isPending} onClick={() => action.mutate({ id: requestId, action: 'resolve' })}>
            Mark as resolved
          </Button>
          {isHelper && (
            <Button
              variant="danger"
              disabled={action.isPending}
              onClick={() => {
                if (window.confirm("Give this request back so another volunteer can pick it? You won't see this chat anymore."))
                  action.mutate({ id: requestId, action: 'release' }, { onSuccess: () => navigate('/h') })
              }}
            >
              I can't help after all
            </Button>
          )}
        </div>
      )}
      <ErrorText error={action.error} />
    </div>
  )
}
