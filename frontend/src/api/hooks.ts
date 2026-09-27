import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AddRoleBody,
  DemoUser,
  GeocodeMatch,
  HelpRequest,
  LatLon,
  LiveLocation,
  NearbyVolunteer,
  MeResponse,
  Message,
  OnboardingBody,
  ProfileUpdate,
  RankedResponse,
  Role,
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

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ProfileUpdate) => api<MeResponse>('/api/me', { method: 'PATCH', json: body }),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      // The profile is re-embedded in the background; Muse Spark takes ~5-20 s. Refresh the ranking as it lands
      // (the ranked list also polls every 10 s on the volunteer page).
      if (data.rematching) {
        for (const delay of [10_000, 25_000]) setTimeout(() => qc.invalidateQueries({ queryKey: keys.ranked }), delay)
      }
    },
  })
}

/** Adds the second profile (volunteer or requester) to the signed-in account. */
export function useAddRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AddRoleBody) => post<MeResponse>('/api/me/roles', body),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      if (data.rematching) {
        for (const delay of [10_000, 25_000]) setTimeout(() => qc.invalidateQueries({ queryKey: keys.ranked }), delay)
      }
    },
  })
}

/** Switches the active mode (home page); the lists differ per mode, so drop their caches. */
export function useSwitchMode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (role: Role) => api<MeResponse>('/api/me', { method: 'PATCH', json: { role } }),
    onSuccess: (data) => {
      qc.setQueryData(keys.me, data)
      qc.invalidateQueries({ queryKey: keys.mine })
      qc.invalidateQueries({ queryKey: keys.ranked })
    },
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
    mutationFn: (body: { text: string; location?: LatLon }) =>
      post<{ request: HelpRequest; show_911: boolean }>('/api/requests', body),
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

/** Street-address search (US Census geocoder via the backend). It does not match place names. */
export function searchAddress(q: string) {
  return api<{ matches: GeocodeMatch[] }>(`/api/geocode?q=${encodeURIComponent(q)}`)
}

/** Approximate areas of volunteers around a point, for the requester's map. */
export function useNearbyVolunteers(center: LatLon | null) {
  return useQuery({
    queryKey: ['volunteers', 'nearby', center?.lat, center?.lon] as const,
    queryFn: () => api<{ volunteers: NearbyVolunteer[]; radius_km: number }>(`/api/volunteers/nearby?lat=${center?.lat}&lon=${center?.lon}`),
    enabled: center !== null,
    staleTime: 60_000,
  })
}

/** Live location sharing on a claimed request (polling; the backend only ever returns the other person's point). */
export function postLocation(requestId: string, body: LatLon & { accuracy?: number }) {
  return post<{ ok: boolean; throttled: boolean }>(`/api/requests/${requestId}/location`, body)
}

export function stopSharingLocation(requestId: string) {
  return api<{ ok: boolean }>(`/api/requests/${requestId}/location`, { method: 'DELETE' })
}

const POLL_LOCATION_MS = 5_000

export function useOtherLocation(requestId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['requests', requestId, 'location'] as const,
    queryFn: () => api<{ other: LiveLocation | null; simulated: boolean; stale_after_s: number }>(`/api/requests/${requestId}/location`),
    enabled,
    refetchInterval: POLL_LOCATION_MS,
    retry: false,
  })
}
