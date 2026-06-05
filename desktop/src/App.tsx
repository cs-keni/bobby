import { useEffect, useRef, useState } from 'react';
import { BobbyWS } from './ws';
import type { BobbyState } from './types';
import './App.css';

const TOKEN = import.meta.env.VITE_BOBBY_TOKEN as string ?? '';
const WS_URL = `ws://localhost:8765/ws?token=${TOKEN}`;

// Delay before orb hides after returning to idle (ms)
const HIDE_DELAY = 1500;

// Heights peak in the center like Siri's waveform
const BAR_MAX_H = [8, 14, 22, 30, 22, 14, 8];
const BAR_DURATION = [0.7, 0.75, 0.8, 0.9, 0.8, 0.75, 0.7];
const BAR_DELAY = [0, -0.12, -0.24, -0.36, -0.18, -0.06, 0.1];

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
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<BobbyWS | null>(null);

  useEffect(() => {
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
        setVisible(true);
      } else {
        // Delay hide so the idle transition isn't jarring
        hideTimer.current = setTimeout(() => {
          setVisible(false);
          setText('');
          hideTimer.current = null;
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
    <div className={`orb-wrapper ${visible ? 'visible' : ''}`}>
      {/* glow-ring allows ::before flare to extend outside the orb without being clipped */}
      <div className={`orb-glow-ring orb-glow-ring--${state}`}>
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
