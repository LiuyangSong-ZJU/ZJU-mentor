const VOTER_ID_KEY = 'zju-mentor-voter-id'
const COMMENT_VOTES_KEY = 'zju-mentor-comment-votes'

const safeLocalStorage = () => {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

const randomToken = () => {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID()
  }

  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export const getVoterId = () => {
  const storage = safeLocalStorage()
  if (!storage) {
    return randomToken()
  }

  const existing = storage.getItem(VOTER_ID_KEY)
  if (existing) {
    return existing
  }

  const voterId = randomToken()
  storage.setItem(VOTER_ID_KEY, voterId)
  return voterId
}

export const loadCommentVotes = () => {
  const storage = safeLocalStorage()
  if (!storage) {
    return {}
  }

  try {
    return JSON.parse(storage.getItem(COMMENT_VOTES_KEY) || '{}') || {}
  } catch {
    return {}
  }
}

export const saveCommentVotes = votes => {
  const storage = safeLocalStorage()
  if (!storage) {
    return
  }

  storage.setItem(COMMENT_VOTES_KEY, JSON.stringify(votes))
}
