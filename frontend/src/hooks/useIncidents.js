import { useCallback, useEffect, useRef, useState } from 'react'
import { getEvents, getHealth } from '../api'

// Polls the API. Calls onNew(incident[]) for incidents first seen after the initial load.
export function useIncidents(onNew, intervalMs = 2500) {
  const [events, setEvents] = useState([])
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [now, setNow] = useState(Date.now())
  const seen = useRef(null)
  const onNewRef = useRef(onNew)
  onNewRef.current = onNew

  const refresh = useCallback(async () => {
    try {
      const [e, h] = await Promise.all([getEvents(200), getHealth()])
      if (seen.current === null) {
        seen.current = new Set(e.map((x) => x.event_id))
      } else {
        const fresh = e.filter((x) => !seen.current.has(x.event_id))
        fresh.forEach((x) => seen.current.add(x.event_id))
        if (fresh.length) onNewRef.current?.(fresh)
      }
      setEvents(e)
      setHealth(h)
      setError('')
      setLastUpdated(Date.now())
    } catch (exc) {
      setHealth(null)
      setError(exc.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    const poll = setInterval(refresh, intervalMs)
    const tick = setInterval(() => setNow(Date.now()), 5000)
    return () => { clearInterval(poll); clearInterval(tick) }
  }, [refresh, intervalMs])

  return { events, health, error, lastUpdated, now, refresh }
}
