import React, { useEffect, useState } from 'react'
import { CameraOff } from 'lucide-react'
import { SeverityTag } from './Common'
import { friendly, plainTitle, timeAgo } from '../config'
import { CAMERA_STREAM_URL } from '../hooks/useCameraStatus'

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
      <dl className="camera-facts">
        <dt>Latest incident</dt>
        <dd>{latest ? plainTitle(latest) + ', ' + friendly(latest.zone_id) + ', ' + timeAgo(latest.ts, now) : 'None recorded yet'}</dd>
        <dt>Detection</dt>
        <dd>Runs on the connected edge host. {cameraStatus?.connected ? 'Preview frames are arriving.' : 'No recent preview frame received.'} Incidents appear only when the edge process reports them to the API.</dd>
      </dl>
    </div>
  )
}
