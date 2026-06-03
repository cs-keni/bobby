import { useRef, useState } from "react";

interface Props {
  onRecordingComplete: (blob: Blob) => void;
  disabled: boolean;
}

export function VoiceButton({ onRecordingComplete, disabled }: Props) {
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = async () => {
    if (disabled || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onRecordingComplete(blob);
      };
      recorder.start(100); // collect in 100ms chunks
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      alert("Microphone access denied. Please allow mic access and try again.");
    }
  };

  const stop = () => {
    if (!recording || !recorderRef.current) return;
    recorderRef.current.stop();
    recorderRef.current = null;
    setRecording(false);
  };

  const size = 80;
  const color = recording ? "#ef4444" : disabled ? "#333" : "#3b82f6";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
      <button
        onPointerDown={start}
        onPointerUp={stop}
        onPointerLeave={stop}
        disabled={disabled && !recording}
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          border: "none",
          background: color,
          cursor: disabled ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background 0.2s, transform 0.1s, box-shadow 0.2s",
          boxShadow: recording
            ? `0 0 0 0 ${color}40`
            : `0 4px 24px ${color}40`,
          transform: recording ? "scale(1.08)" : "scale(1)",
          animation: recording ? "pulse 1.2s ease-out infinite" : undefined,
          outline: "none",
          WebkitTapHighlightColor: "transparent",
          touchAction: "none",
        }}
        aria-label={recording ? "Release to send" : "Hold to talk"}
      >
        <MicIcon recording={recording} />
      </button>
      <span style={{ fontSize: 12, color: "#666", letterSpacing: "0.04em" }}>
        {recording ? "Release to send" : disabled ? "Processing..." : "Hold to talk"}
      </span>
    </div>
  );
}

function MicIcon({ recording }: { recording: boolean }) {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <rect x="9" y="2" width="6" height="12" rx="3" fill={recording ? "white" : "white"} />
      <path
        d="M5 10C5 14.4183 8.13401 18 12 18C15.866 18 19 14.4183 19 10"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line x1="12" y1="18" x2="12" y2="22" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <line x1="8" y1="22" x2="16" y2="22" stroke="white" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
