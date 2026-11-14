import React, { useEffect, useState } from 'react'
import { CameraOff } from 'lucide-react'
import { SeverityTag } from './Common'
import { friendly, plainTitle, timeAgo } from '../config'

// Camera slot. Set in frontend/.env:
//   VITE_CAMERA_URL   address of the node's stream (MJPEG) or a snapshot image URL
//   VITE_CAMERA_MODE  "stream" (default) or "snapshot" (re-fetched every 2 s)
//   VITE_CAMERA_LABEL display name, e.g. "UNO Q node 1"
const RAW = import.meta.env.VITE_CAMERA_URL || ''
const URL_OK = /^https?:\/\//i.test(RAW) ? RAW : ''
const MODE = import.meta.env.VITE_CAMERA_MODE || 'stream'
const LABEL = import.meta.env.VITE_CAMERA_LABEL || 'Camera node 1'

export function CameraFeed({ latest, now }) {
  const [tick, setTick] = useState(0)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!URL_OK || MODE !== 'snapshot') return
    const t = setInterval(() => setTick((x) => x + 1), 2000)
    return () => clearInterval(t)
  }, [])
  const src = !URL_OK ? '' : MODE === 'snapshot' ? URL_OK + (URL_OK.includes('?') ? '&' : '?') + 't=' + tick : URL_OK
  const connected = Boolean(URL_OK) && !failed
  const recent = latest && now - latest.ts < 60000

  return (
    <div className="camera">
      <div className="camera-frame">
        {URL_OK && <img src={src} alt={LABEL + ' live view'} onLoad={() => setFailed(false)} onError={() => setFailed(true)} style={failed ? { display: 'none' } : undefined} />}
        {!connected && (
          <div className="camera-empty">
            <CameraOff size={34} />
            <b>{URL_OK ? 'Feed unreachable' : 'No camera connected'}</b>
            <span>{URL_OK
              ? 'The camera address did not respond. Check the node is running and on the same network.'
              : 'Set VITE_CAMERA_URL in frontend/.env to the stream address of the camera node, then restart the dev server.'}</span>
          </div>
        )}
        <div className="hud" aria-hidden="true">
          <i className="c tl" /><i className="c tr" /><i className="c bl" /><i className="c br" />
          <span className={'hud-state ' + (connected ? 'rec' : 'standby')}>{connected ? 'LIVE' : 'STANDBY'}</span>
          <span className="hud-time">{new Date(now).toLocaleTimeString()}</span>
        </div>
        <div className="camera-badges">
          <span className="cam-label">{LABEL}</span>
          <span className={'cam-state ' + (connected ? 'live' : 'off')}>{connected ? 'Feed connected' : 'No feed'}</span>
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
        <dd>Runs on the camera node. Incidents appear here once the node reports them.</dd>
      </dl>
    </div>
  )
}
