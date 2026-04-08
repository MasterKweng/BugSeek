const CACHE_PREFIX = 'field_mapping_task_'
const CACHE_EXPIRY = 60 * 60 * 1000

interface CacheData<T> {
  data: T
  timestamp: number
}

const getCacheKey = (key: string): string => `${CACHE_PREFIX}${key}`

export const saveToCache = <T>(key: string, data: T): void => {
  try {
    if (!key || key.trim() === '') {
      console.warn('[Cache] Invalid cache key')
      return
    }

    if (data === null || data === undefined) {
      console.warn('[Cache] Invalid cache payload')
      return
    }

    const cacheData: CacheData<T> = {
      data,
      timestamp: Date.now(),
    }

    localStorage.setItem(getCacheKey(key), JSON.stringify(cacheData))
  } catch (error) {
    console.error('[Cache] Failed to save cache:', error)
  }
}

export const getFromCache = <T>(key: string): T | null => {
  try {
    if (!key || key.trim() === '') {
      console.warn('[Cache] Invalid cache key')
      return null
    }

    const raw = localStorage.getItem(getCacheKey(key))
    if (!raw) {
      return null
    }

    const cacheData: CacheData<T> = JSON.parse(raw)
    if (Date.now() - cacheData.timestamp > CACHE_EXPIRY) {
      localStorage.removeItem(getCacheKey(key))
      return null
    }

    return cacheData.data
  } catch (error) {
    console.error('[Cache] Failed to read cache:', error)
    return null
  }
}

export const removeFromCache = (key: string): void => {
  try {
    if (!key || key.trim() === '') {
      console.warn('[Cache] Invalid cache key')
      return
    }
    localStorage.removeItem(getCacheKey(key))
  } catch (error) {
    console.error('[Cache] Failed to remove cache:', error)
  }
}

export const clearFieldMappingCache = (): void => {
  try {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i)
      if (key && key.startsWith(CACHE_PREFIX)) {
        keys.push(key)
      }
    }
    keys.forEach((key) => localStorage.removeItem(key))
  } catch (error) {
    console.error('[Cache] Failed to clear cache:', error)
  }
}
