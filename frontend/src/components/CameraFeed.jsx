import React, { useEffect, useState } from 'react'
import { CameraOff, RotateCcw, Eye } from 'lucide-react'
import { SeverityTag } from './Common'
import { friendly, plainTitle, timeAgo } from '../config'
import { CAMERA_STREAM_URL, CAMERA_STATUS_URL } from '../hooks/useCameraStatus'

// Camera slot. Set in frontend/.env:
//   VITE_CAMERA_URL   address of the node's stream (MJPEG) or a snapshot image URL
//   VITE_CAMERA_MODE  "stream" (default) or "snapshot" (re-fetched every 2 s)
//   VITE_CAMERA_LABEL display name, e.g. "UNO Q node 1"
const URL_OK = CAMERA_STREAM_URL
const MODE = import.meta.env.VITE_CAMERA_MODE || 'stream'
const LABEL = import.meta.env.VITE_CAMERA_LABEL || 'Camera node 1'

export function CameraFeed({ latest, now, cameraStatus, cameraError }) {
  const [tick, setTick] = useState(0)
  const [failed, setFailed] = useState(false)
  const [boxBusy, setBoxBusy] = useState(false)
  const [boxMessage, setBoxMessage] = useState('')
  const [boxError, setBoxError] = useState('')

  async function setBoxes(action) {
    if (!CAMERA_STATUS_URL || !cameraStatus?.connected || boxBusy) return
    if (action === 'reset-boxes' && !window.confirm(
      'Reset all camera boxes? This permanently removes saved danger and road zones, ' +
      'stops manual object tracking, and hides visual boxes. Detection and incident history will continue.'
    )) return
    setBoxBusy(true)
    setBoxError('')
    setBoxMessage('')
    try {
      const endpoint = new URL('/controls/' + action, CAMERA_STATUS_URL)
      const response = await fetch(endpoint.href, {
        method: 'POST',
        headers: { 'X-SiteGuardian-Control': action },
      })
      if (!response.ok) throw new Error('Camera control rejected (HTTP ' + response.status + ')')
      const result = await response.json()
      if (!result.queued) throw new Error('Camera did not accept the command')
      setBoxMessage(action === 'reset-boxes'
        ? 'Reset requested. Saved zones and manual tracking will clear on the next camera frame; detections and alerts continue.'
        : 'Show-boxes request accepted. Live detection outlines will return on the next frame.')
    } catch (error) {
      setBoxError('Cannot control camera: ' + error.message)
    } finally {
      setBoxBusy(false)
    }
  }
  useEffect(() => {
    if (!URL_OK || MODE !== 'snapshot') return
    const t = setInterval(() => setTick((x) => x + 1), 2000)
    return () => clearInterval(t)
  }, [])
  const src = !URL_OK ? '' : URL_OK + (URL_OK.includes('?') ? '&' : '?') + 't=' + tick
  const statusConnected = Boolean(URL_OK && cameraStatus?.connected)
  // Retry if an MJPEG connection was interrupted, without claiming it is live
  // merely because a URL was configured.
  useEffect(() => {
    if (!failed || !statusConnected) return
    const timer = setTimeout(() => { setFailed(false); setTick((n) => n + 1) }, 3000)
    return () => clearTimeout(timer)
  }, [failed, statusConnected])
  const connected = statusConnected && !failed
  const recent = latest && now - latest.ts < 60000

  return (
    <div className="camera">
      <div className="camera-frame">
        {connected && <img src={src} alt={LABEL + ' live view'} onLoad={() => setFailed(false)} onError={() => setFailed(true)} />}
        {!connected && (
          <div className="camera-empty">
            <CameraOff size={34} />
            <b>{URL_OK ? 'Feed unreachable' : 'No camera connected'}</b>
            <span>{URL_OK
              ? (cameraError || 'Camera not publishing recent frames. Check the edge terminal and the stream URL.')
              : 'Set VITE_CAMERA_URL in frontend/.env to the local stream address (for example http://127.0.0.1:8765/stream.mjpg), then restart Vite.'}</span>
          </div>
        )}
        <div className="hud" aria-hidden="true">
          <i className="c tl" /><i className="c tr" /><i className="c bl" /><i className="c br" />
          <span className={'hud-state ' + (connected ? 'rec' : 'standby')}>{connected ? 'LIVE PREVIEW' : 'NO FRESH FRAME'}</span>
          <span className="hud-time">{new Date(now).toLocaleTimeString()}</span>
        </div>
        <div className="camera-badges">
          <span className="cam-label">{LABEL}</span>
          <span className={'cam-state ' + (connected ? 'live' : 'off')}>{connected ? 'Frames arriving' : 'Feed offline'}</span>
        </div>
        {recent && (
          <div className={'camera-alert a-' + latest.severity}>
            <SeverityTag severity={latest.severity} />
            <b>{plainTitle(latest)}</b>
            <span>{friendly(latest.zone_id)}, {timeAgo(latest.ts, now)}</span>
          </div>
        )}
      </div>
      <div className="actions" role="group" aria-label="Camera box controls">
        <button className="secondary" type="button"
          onClick={() => setBoxes('reset-boxes')} disabled={!statusConnected || boxBusy}>
          <RotateCcw size={16} /> Reset all boxes
        </button>
        {cameraStatus?.boxes_visible === false && (
          <button className="secondary" type="button"
            onClick={() => setBoxes('show-boxes')} disabled={!statusConnected || boxBusy}>
            <Eye size={16} /> Show detection boxes
          </button>
        )}
      </div>
      <p className="muted">Reset removes saved danger/road zones and active manual tracking, then hides camera outlines. AI detection and alerts continue; incident history and snapshots are kept.</p>
      {boxMessage && <p className="muted" role="status">{boxMessage}</p>}
      {boxError && <p className="error" role="alert">{boxError}</p>}
      <dl className="camera-facts">
        <dt>Latest incident</dt>
        <dd>{latest ? plainTitle(latest) + ', ' + friendly(latest.zone_id) + ', ' + timeAgo(latest.ts, now) : 'None recorded yet'}</dd>
        <dt>Detection</dt>
        <dd>Runs on the connected edge host. {cameraStatus?.connected ? 'Preview frames are arriving.' : 'No recent preview frame received.'} Incidents appear only when the edge process reports them to the API.</dd>
      </dl>
    </div>
  )
}
