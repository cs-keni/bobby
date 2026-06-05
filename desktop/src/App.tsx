import { useEffect, useRef, useState } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { BobbyWS } from './ws';
import type { BobbyState } from './types';
import './App.css';

const appWindow = getCurrentWindow();

const TOKEN = import.meta.env.VITE_BOBBY_TOKEN as string ?? '';
const WS_URL = `ws://localhost:8765/ws?token=${TOKEN}`;
const HIDE_DELAY = 500;

const BAR_MAX_H = [8, 14, 22, 30, 22, 14, 8];
const BAR_DURATION = [0.7, 0.75, 0.8, 0.9, 0.8, 0.75, 0.7];
const BAR_DELAY = [0, -0.12, -0.24, -0.36, -0.18, -0.06, 0.1];

// Each sparkle orbits in its own tilted plane (sx=X-tilt, sy=Y-tilt),
// at a given radius (sr), displayed at size (sw), with a hue offset (dh).
const SPARKLES = [
  { sx: '22deg',  sy: '0deg',   sr: '36px', sw: '3px',   dur: 3.2, delay: 0,    dh: 0   },
  { sx: '-42deg', sy: '0deg',   sr: '30px', sw: '2px',   dur: 4.5, delay: -1.5, dh: 25  },
  { sx: '56deg',  sy: '0deg',   sr: '38px', sw: '4px',   dur: 2.8, delay: -0.8, dh: -12 },
  { sx: '-28deg', sy: '35deg',  sr: '33px', sw: '2.5px', dur: 5.1, delay: -2.1, dh: 40  },
  { sx: '44deg',  sy: '0deg',   sr: '35px', sw: '3px',   dur: 3.8, delay: -1.2, dh: 18  },
  { sx: '-60deg', sy: '22deg',  sr: '29px', sw: '2px',   dur: 4.8, delay: -3.0, dh: -8  },
  { sx: '30deg',  sy: '-25deg', sr: '37px', sw: '3.5px', dur: 3.5, delay: -0.5, dh: 30  },
  { sx: '-50deg', sy: '10deg',  sr: '31px', sw: '2.5px', dur: 6.0, delay: -4.2, dh: -20 },
] as const;

// Three mini-orb satellites: different sizes, radii, speeds, and hue offsets so
// they never align — gives the spirit-cloud / Asha feel.
const ORBIT_BLOBS = [
  { br: '42px', bw: '14px', bdur: '5.0s', bdelay: '0s',    dh: 0,   bwdur: '2.4s' },
  { br: '34px', bw: '10px', bdur: '8.2s', bdelay: '-2.8s', dh: 20,  bwdur: '3.1s' },
  { br: '48px', bw: '9px',  bdur: '6.5s', bdelay: '-4.3s', dh: -15, bwdur: '2.8s' },
] as const;

function SparkleField() {
  return (
    <div className="sparkle-field">
      {SPARKLES.map((sp, i) => (
        <div
          key={i}
          className="sparkle"
          style={{
            '--sx': sp.sx,
            '--sy': sp.sy,
            '--sr': sp.sr,
            '--sw': sp.sw,
            '--sdur': `${sp.dur}s`,
            '--dh': String(sp.dh),
            // same delay applied to both orbit + depth animations
            animationDelay: `${sp.delay}s, ${sp.delay}s`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

function OrbitBlobs() {
  return (
    <>
      {ORBIT_BLOBS.map((blob, i) => (
        <div
          key={i}
          className="orbit-arm"
          style={{
            '--br': blob.br,
            '--bdur': blob.bdur,
            '--bwdur': blob.bwdur,
            animationDelay: blob.bdelay,
          } as React.CSSProperties}
        >
          <div
            className="orbit-blob"
            style={{
              '--bw': blob.bw,
              '--dh': String(blob.dh),
            } as React.CSSProperties}
          />
        </div>
      ))}
    </>
  );
}

function Waveform() {
  return (
    <div className="waveform">
      {BAR_MAX_H.map((maxH, i) => (
        <div
          key={i}
          className="waveform-bar"
          style={{
            '--max-h': `${maxH}px`,
            '--dur': `${BAR_DURATION[i]}s`,
            animationDelay: `${BAR_DELAY[i]}s`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

function ListeningDots() {
  return (
    <div className="listening-dots">
      <div className="listening-dot" />
      <div className="listening-dot" />
      <div className="listening-dot" />
    </div>
  );
}

function OrbIcon({ state }: { state: BobbyState }) {
  if (state === 'speaking') return <Waveform />;
  if (state === 'thinking' || state === 'listening') return <ListeningDots />;
  return null;
}

export default function App() {
  const [state, setState] = useState<BobbyState>('idle');
  const [visible, setVisible] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<BobbyWS | null>(null);
  // Preserves the last active state so the orb slides out with its real color,
  // not the gray idle style.
  const lastActiveRef = useRef<BobbyState>('listening');

  useEffect(() => {
    appWindow.setIgnoreCursorEvents(true).catch(() => {});

    const ws = new BobbyWS(WS_URL);
    wsRef.current = ws;

    const unsub = ws.onEvent(event => {
      setState(event.state);

      if (event.state !== 'idle') {
        lastActiveRef.current = event.state;
        if (hideTimer.current) {
          clearTimeout(hideTimer.current);
          hideTimer.current = null;
        }
        setVisible(true);
        appWindow.setIgnoreCursorEvents(false).catch(() => {});
      } else {
        hideTimer.current = setTimeout(() => {
          setVisible(false);
          hideTimer.current = null;
          appWindow.setIgnoreCursorEvents(true).catch(() => {});
        }, HIDE_DELAY);
      }
    });

    return () => {
      unsub();
      ws.disconnect();
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, []);

  // When idle, keep the last active state's CSS classes so the orb slides
  // out with its color rather than flashing gray.
  const displayState = state === 'idle' ? lastActiveRef.current : state;

  return (
    <div className={`orb-wrapper${visible ? ' visible' : ''}`}>
      <div className={`orb-glow-ring orb-glow-ring--${displayState}`}>
        <SparkleField />
        <OrbitBlobs />
        <div className={`orb orb--${displayState}`}>
          <OrbIcon state={state} />
        </div>
      </div>
    </div>
  );
}
