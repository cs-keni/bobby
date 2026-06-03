/**
 * Bobby API client.
 * Server URL and token are read from localStorage (set via the Settings modal).
 */

const DEFAULT_SERVER_URL = window.location.origin;

export function getServerUrl(): string {
  return localStorage.getItem("bobby_server_url") || DEFAULT_SERVER_URL;
}

export function getToken(): string {
  return localStorage.getItem("bobby_token") || "";
}

export function saveSettings(serverUrl: string, token: string): void {
  localStorage.setItem("bobby_server_url", serverUrl.replace(/\/$/, ""));
  localStorage.setItem("bobby_token", token);
}

function headers(): Record<string, string> {
  return {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  };
}

export interface CommandResult {
  ok: boolean;
  response: string;
  audio_b64: string | null;
  error?: string;
}

export interface VoiceResult {
  ok: boolean;
  transcription?: string;
  response: string;
  audio_b64: string | null;
  error?: string;
}

export async function sendCommand(text: string): Promise<CommandResult> {
  const res = await fetch(`${getServerUrl()}/api/command`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ text, return_audio: true }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export async function sendVoice(audioBlob: Blob): Promise<VoiceResult> {
  const form = new FormData();
  form.append("audio", audioBlob, "recording.webm");

  const res = await fetch(`${getServerUrl()}/api/voice`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${getServerUrl()}/api/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

export function playAudioB64(b64: string): void {
  try {
    const bytes = atob(b64);
    const buf = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
    const blob = new Blob([buf], { type: "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.play().catch(() => {
      // Autoplay blocked — audio will play on next user gesture
    });
  } catch {
    // Non-critical: text response is always shown
  }
}
