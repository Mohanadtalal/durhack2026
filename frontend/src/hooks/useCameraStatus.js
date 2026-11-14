import { useEffect, useState } from 'react'

// Local Nicla preview server; this is intentionally separate from the
// incident API. A stale frame must never be presented as an online camera.
const RAW = import.meta.env.VITE_CAMERA_URL || ''
export const CAMERA_STREAM_URL = /^https?:\/\//i.test(RAW) ? RAW : ''
export const CAMERA_STATUS_URL = (() => {
  if (!CAMERA_STREAM_URL) return ''
  try {
    const url = new URL(CAMERA_STREAM_URL)
    url.pathname = '/status.json'
    url.search = ''
    url.hash = ''
    return url.href
  } catch {
    return ''
  }
})()

export function useCameraStatus(intervalMs = 2500) {
  const [cameraStatus, setCameraStatus] = useState(null)
  const [cameraError, setCameraError] = useState(
    CAMERA_STREAM_URL ? 'Waiting for camera status' : 'Camera stream not configured'
  )

  useEffect(() => {
    if (!CAMERA_STATUS_URL) return
    let active = true
    async function refresh() {
      try {
        const response = await fetch(CAMERA_STATUS_URL, { cache: 'no-store' })
        if (!response.ok) throw new Error('Camera status HTTP ' + response.status)
        const result = await response.json()
        if (!result || typeof result.connected !== 'boolean' ||
            !Array.isArray(result.zones)) throw new Error('Invalid camera status')
        if (active) {
          setCameraStatus(result)
          setCameraError(result.connected ? '' : 'Camera has not sent a recent frame')
        }
      } catch (error) {
        if (active) {
          setCameraStatus(null)
          setCameraError(error.message)
        }
      }
    }
    refresh()
    const timer = setInterval(refresh, intervalMs)
    return () => { active = false; clearInterval(timer) }
  }, [intervalMs])

  return { cameraStatus, cameraError }
}
