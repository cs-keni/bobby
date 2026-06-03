import { useEffect, useRef, useState } from "react";
import { StatusBadge } from "./components/StatusBadge";
import { VoiceButton } from "./components/VoiceButton";
import {
  checkHealth,
  getServerUrl,
  getToken,
  playAudioB64,
  saveSettings,
  sendCommand,
  sendVoice,
} from "./api";

interface Message {
  role: "user" | "bobby";
  text: string;
  id: number;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [typedText, setTypedText] = useState("");
  const [processing, setProcessing] = useState(false);
  const [connected, setConnected] = useState(false);
  const [checkingConn, setCheckingConn] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsUrl, setSettingsUrl] = useState(getServerUrl());
  const [settingsToken, setSettingsToken] = useState(getToken());
  const [error, setError] = useState<string | null>(null);
  const msgId = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Poll connection health
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      setCheckingConn(true);
      const ok = await checkHealth();
      if (!cancelled) {
        setConnected(ok);
        setCheckingConn(false);
      }
    };
    poll();
    const interval = setInterval(poll, 15_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const push = (role: "user" | "bobby", text: string) => {
    setMessages((prev) => [...prev, { role, text, id: msgId.current++ }]);
  };

  const handleVoice = async (blob: Blob) => {
    setError(null);
    setProcessing(true);
    try {
      const result = await sendVoice(blob);
      if (!result.ok) {
        setError(result.error ?? "Could not understand audio");
      } else {
        push("user", result.transcription ?? "…");
        push("bobby", result.response);
        if (result.audio_b64) playAudioB64(result.audio_b64);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setProcessing(false);
    }
  };

  const handleText = async () => {
    const text = typedText.trim();
    if (!text || processing) return;
    setTypedText("");
    setError(null);
    setProcessing(true);
    push("user", text);
    try {
      const result = await sendCommand(text);
      push("bobby", result.response);
      if (result.audio_b64) playAudioB64(result.audio_b64);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setProcessing(false);
    }
  };

  const saveAndClose = () => {
    saveSettings(settingsUrl, settingsToken);
    setShowSettings(false);
    setCheckingConn(true);
    checkHealth().then((ok) => {
      setConnected(ok);
      setCheckingConn(false);
    });
  };

  return (
    <div style={styles.root}>
      {/* Header */}
      <header style={styles.header}>
        <span style={styles.title}>Bobby</span>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <StatusBadge connected={connected} checking={checkingConn} />
          <button style={styles.iconBtn} onClick={() => setShowSettings(true)} aria-label="Settings">
            <GearIcon />
          </button>
        </div>
      </header>

      {/* Message feed */}
      <div style={styles.feed}>
        {messages.length === 0 && (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>🎙</div>
            <p style={styles.emptyText}>Hold the button and talk, or type below.</p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              ...styles.bubble,
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              background: msg.role === "user" ? "#1d4ed8" : "#1e1e1e",
              borderBottomRightRadius: msg.role === "user" ? 4 : 16,
              borderBottomLeftRadius: msg.role === "user" ? 16 : 4,
            }}
          >
            {msg.role === "bobby" && (
              <span style={styles.bubbleLabel}>Bobby</span>
            )}
            <p style={styles.bubbleText}>{msg.text}</p>
          </div>
        ))}
        {processing && (
          <div style={{ ...styles.bubble, alignSelf: "flex-start", background: "#1e1e1e" }}>
            <span style={styles.bubbleLabel}>Bobby</span>
            <ThinkingDots />
          </div>
        )}
        {error && (
          <div style={styles.errorBanner}>
            <span>⚠ {error}</span>
            <button style={styles.dismissBtn} onClick={() => setError(null)}>✕</button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Controls */}
      <div style={styles.controls}>
        <VoiceButton onRecordingComplete={handleVoice} disabled={processing} />

        <div style={styles.textRow}>
          <input
            ref={inputRef}
            style={styles.textInput}
            value={typedText}
            onChange={(e) => setTypedText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleText()}
            placeholder="Type a command…"
            disabled={processing}
          />
          <button
            style={{
              ...styles.sendBtn,
              opacity: typedText.trim() && !processing ? 1 : 0.4,
            }}
            onClick={handleText}
            disabled={!typedText.trim() || processing}
            aria-label="Send"
          >
            <SendIcon />
          </button>
        </div>
      </div>

      {/* Settings modal */}
      {showSettings && (
        <div style={styles.modalOverlay} onClick={() => setShowSettings(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Settings</h2>

            <label style={styles.label}>Server URL</label>
            <input
              style={styles.modalInput}
              value={settingsUrl}
              onChange={(e) => setSettingsUrl(e.target.value)}
              placeholder="http://192.168.1.x:8765"
              autoComplete="off"
              spellCheck={false}
            />

            <label style={styles.label}>Token</label>
            <input
              style={styles.modalInput}
              type="password"
              value={settingsToken}
              onChange={(e) => setSettingsToken(e.target.value)}
              placeholder="your-server-token"
              autoComplete="off"
            />

            <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
              <button style={styles.modalCancel} onClick={() => setShowSettings(false)}>
                Cancel
              </button>
              <button style={styles.modalSave} onClick={saveAndClose}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
          70%  { box-shadow: 0 0 0 18px rgba(239,68,68,0); }
          100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
        }
        @keyframes blink {
          0%, 80%, 100% { opacity: 0; }
          40% { opacity: 1; }
        }
        * { box-sizing: border-box; }
        body { margin: 0; background: #0a0a0a; }
        input:focus { outline: none; }
        button:focus { outline: none; }
        ::-webkit-scrollbar { width: 0; }
      `}</style>
    </div>
  );
}

function ThinkingDots() {
  return (
    <div style={{ display: "flex", gap: 5, padding: "4px 0" }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: "#666",
            animation: `blink 1.4s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function GearIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

const styles = {
  root: {
    display: "flex" as const,
    flexDirection: "column" as const,
    height: "100dvh",
    background: "#0a0a0a",
    color: "#f0f0f0",
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    maxWidth: 480,
    margin: "0 auto",
    position: "relative" as const,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 20px",
    paddingTop: "calc(16px + env(safe-area-inset-top))",
    borderBottom: "1px solid #1e1e1e",
    flexShrink: 0,
  },
  title: {
    fontSize: 20,
    fontWeight: 700,
    letterSpacing: "-0.02em",
    color: "#f0f0f0",
  },
  iconBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: 4,
    display: "flex",
    alignItems: "center",
  },
  feed: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "16px 16px 8px",
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
  },
  emptyState: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: 12,
    marginTop: 60,
  },
  emptyIcon: {
    fontSize: 48,
    opacity: 0.4,
  },
  emptyText: {
    color: "#555",
    fontSize: 15,
    textAlign: "center" as const,
    margin: 0,
  },
  bubble: {
    maxWidth: "80%",
    borderRadius: 16,
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column" as const,
    gap: 3,
  },
  bubbleLabel: {
    fontSize: 11,
    color: "#555",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
  },
  bubbleText: {
    margin: 0,
    fontSize: 15,
    lineHeight: 1.5,
    color: "#e5e5e5",
  },
  errorBanner: {
    background: "#2d1515",
    border: "1px solid #7f1d1d",
    borderRadius: 10,
    padding: "10px 14px",
    fontSize: 14,
    color: "#fca5a5",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dismissBtn: {
    background: "none",
    border: "none",
    color: "#fca5a5",
    cursor: "pointer",
    fontSize: 16,
    padding: "0 4px",
  },
  controls: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 20,
    padding: "20px 16px",
    paddingBottom: "calc(20px + env(safe-area-inset-bottom))",
    borderTop: "1px solid #1e1e1e",
    background: "#0a0a0a",
    flexShrink: 0,
  },
  textRow: {
    display: "flex",
    width: "100%",
    gap: 10,
    alignItems: "center",
  },
  textInput: {
    flex: 1,
    background: "#1a1a1a",
    border: "1px solid #2a2a2a",
    borderRadius: 12,
    padding: "12px 16px",
    color: "#f0f0f0",
    fontSize: 15,
    fontFamily: "inherit",
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: "50%",
    background: "#3b82f6",
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "white",
    flexShrink: 0,
    transition: "opacity 0.2s",
  },
  modalOverlay: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.7)",
    backdropFilter: "blur(4px)",
    display: "flex",
    alignItems: "flex-end",
    zIndex: 100,
  },
  modal: {
    background: "#141414",
    borderRadius: "20px 20px 0 0",
    padding: 24,
    width: "100%",
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
    paddingBottom: "calc(24px + env(safe-area-inset-bottom))",
  },
  modalTitle: {
    margin: "0 0 8px",
    fontSize: 18,
    fontWeight: 700,
    color: "#f0f0f0",
  },
  label: {
    fontSize: 12,
    color: "#888",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
    marginBottom: -4,
  },
  modalInput: {
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    borderRadius: 10,
    padding: "12px 14px",
    color: "#f0f0f0",
    fontSize: 15,
    fontFamily: "inherit",
    width: "100%",
  },
  modalCancel: {
    flex: 1,
    padding: "12px 0",
    borderRadius: 12,
    background: "#1e1e1e",
    border: "1px solid #2a2a2a",
    color: "#888",
    fontSize: 15,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  modalSave: {
    flex: 2,
    padding: "12px 0",
    borderRadius: 12,
    background: "#3b82f6",
    border: "none",
    color: "white",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  },
} as const;
