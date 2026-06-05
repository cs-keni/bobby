import { useEffect, useRef, useState } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { BobbyWS } from './ws';
import type { BobbyState } from './types';
import './App.css';

const appWindow = getCurrentWindow();

const TOKEN = import.meta.env.VITE_BOBBY_TOKEN as string ?? '';
const WS_URL = `ws://localhost:8765/ws?token=${TOKEN}`;
const HIDE_DELAY = 1500;

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

function OrbIcon({ state }: { state: BobbyState }) {
  if (state === 'speaking') return <Waveform />;
  if (state === 'thinking') return <div className="thinking-ring" />;
  if (state === 'listening') return <div className="listening-ring" />;
  return null;
}

export default function App() {
  const [state, setState] = useState<BobbyState>('idle');
  const [text, setText] = useState('');
  const [visible, setVisible] = useState(false);
  const [fading, setFading] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<BobbyWS | null>(null);

  useEffect(() => {
    // Start click-through until the orb becomes visible for the first time
    appWindow.setIgnoreCursorEvents(true).catch(() => {});

    const ws = new BobbyWS(WS_URL);
    wsRef.current = ws;

    const unsub = ws.onEvent(event => {
      setState(event.state);
      if (event.text) setText(event.text);

      if (event.state !== 'idle') {
        if (hideTimer.current) {
          clearTimeout(hideTimer.current);
          hideTimer.current = null;
        }
        setFading(false);
        setVisible(true);
        // Let mouse events reach the orb while it's visible
        appWindow.setIgnoreCursorEvents(false).catch(() => {});
      } else {
        // Start gray fade immediately; slide out after HIDE_DELAY
        setFading(true);
        hideTimer.current = setTimeout(() => {
          setVisible(false);
          setText('');
          hideTimer.current = null;
          // Pass all mouse events through the window when orb is hidden
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

  return (
    <div className={`orb-wrapper${visible ? ' visible' : ''}${fading ? ' fading' : ''}`}>
      <div className={`orb-glow-ring orb-glow-ring--${state}`}>
        <SparkleField />
        <div className={`orb orb--${state}`}>
          <OrbIcon state={state} />
        </div>
      </div>
      {text && state === 'speaking' && (
        <p className="orb-text">{text}</p>
      )}
    </div>
  );
}
