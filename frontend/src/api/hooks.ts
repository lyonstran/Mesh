import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  DemoUser,
  HelpRequest,
  MeResponse,
  Message,
  OnboardingBody,
  RankedResponse,
} from '../lib/types'
import { api, post } from './client'

// Polling intervals from PLAN.md §0.1 (WebSocket realtime comes later).
const POLL_REQUESTER_MS = 5_000
const POLL_RANKED_MS = 10_000

export const keys = {
  me: ['me'] as const,
  mine: ['requests', 'mine'] as const,
  ranked: ['requests', 'ranked'] as const,
  request: (id: string) => ['requests', id] as const,
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api<MeResponse>('/api/me', { allow401: true }),
    retry: false,
    staleTime: 60_000,
  })
}

export function useDemoUsers(enabled: boolean) {
  return useQuery({
    queryKey: ['demo-users'],
    queryFn: () => api<{ users: DemoUser[] }>('/api/auth/demo-users'),
    enabled,
  })
}

/** After any login, cache the new user so guards route correctly. */
export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { kind: 'google'; credential: string } | { kind: 'demo'; userId: string }) =>
      args.kind === 'google'
        ? post<MeResponse>('/api/auth/google', { credential: args.credential })
        : post<MeResponse>('/api/auth/demo', { user_id: args.userId }),
    onSuccess: (data) => {
      qc.clear()
      qc.setQueryData(keys.me, data)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post('/api/auth/logout'),
    onSettled: () => {
      qc.clear()
      window.location.assign('/login')
    },
  })
}

export function useOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OnboardingBody) => post<MeResponse>('/api/onboarding', body),
    onSuccess: (data) => qc.setQueryData(keys.me, data),
  })
}

export function useMyRequests(pollMs = POLL_REQUESTER_MS) {
  return useQuery({
    queryKey: keys.mine,
    queryFn: () => api<{ requests: HelpRequest[] }>('/api/requests/mine'),
    refetchInterval: pollMs,
  })
}

export function useRanked() {
  return useQuery({
    queryKey: keys.ranked,
    queryFn: () => api<RankedResponse>('/api/requests/ranked'),
    refetchInterval: POLL_RANKED_MS,
  })
}

export function useRequest(id: string) {
  return useQuery({
    queryKey: keys.request(id),
    queryFn: () => api<{ request: HelpRequest }>(`/api/requests/${id}`),
    refetchInterval: POLL_REQUESTER_MS,
  })
}

export function useCheckEmergency() {
  return useMutation({ mutationFn: (text: string) => post<{ emergency: boolean }>('/api/requests/check', { text }) })
}

export function useCreateRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => post<{ request: HelpRequest; show_911: boolean }>('/api/requests', { text }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.mine }),
  })
}

export type RequestAction = 'claim' | 'release' | 'resolve' | 'cancel'

export function useRequestAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: RequestAction }) =>
      post<{ request: HelpRequest }>(`/api/requests/${id}/${action}`),
    onSuccess: ({ request }) => qc.setQueryData(keys.request(request.id), { request }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['requests'] }),
  })
}

export function listMessages(requestId: string, after?: string) {
  const qs = after ? `?after=${encodeURIComponent(after)}` : ''
  return api<{ messages: Message[] }>(`/api/requests/${requestId}/messages${qs}`)
}

export function sendMessage(requestId: string, text: string) {
  return post<{ message: Message }>(`/api/requests/${requestId}/messages`, { text })
}
