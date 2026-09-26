// Mirrors backend pydantic models / response shapes. Keep in sync with backend/app.

export type LLMProviderName = 'mock' | 'muse'

export interface Health {
  ok: boolean
  db: 'ok' | 'error'
  llm_provider: LLMProviderName
  sim_active: boolean
}
