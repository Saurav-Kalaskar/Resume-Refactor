interface StoredKey {
  key: string
  expiresAt: number
}

const STORAGE_KEY = 'ats_nvidia_api_key'
const EXPIRY_MS = 24 * 60 * 60 * 1000 // 24 hours

export function saveApiKey(key: string): void {
  const data: StoredKey = {
    key,
    expiresAt: Date.now() + EXPIRY_MS,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export function getApiKey(): string | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null

  try {
    const data: StoredKey = JSON.parse(raw)
    if (Date.now() > data.expiresAt) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return data.key
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY)
}
