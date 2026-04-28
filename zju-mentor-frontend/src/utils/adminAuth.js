const ADMIN_TOKEN_KEY = 'zju-mentor-admin-token'

export const getAdminToken = () => {
  if (typeof window === 'undefined') {
    return ''
  }

  return window.sessionStorage.getItem(ADMIN_TOKEN_KEY) || ''
}

export const setAdminToken = token => {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token)
}

export const clearAdminToken = () => {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.removeItem(ADMIN_TOKEN_KEY)
}

export const adminFetch = async (input, init = {}) => {
  const token = getAdminToken()
  const headers = new Headers(init.headers || {})
  if (token) {
    headers.set('X-Admin-Token', token)
  }

  return fetch(input, {
    ...init,
    headers
  })
}
