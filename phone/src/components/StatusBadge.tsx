interface Props {
  connected: boolean;
  checking: boolean;
}

export function StatusBadge({ connected, checking }: Props) {
  const color = checking ? "#f59e0b" : connected ? "#22c55e" : "#ef4444";
  const label = checking ? "Checking..." : connected ? "Online" : "Offline";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          boxShadow: connected && !checking ? `0 0 6px ${color}` : undefined,
          transition: "background 0.3s, box-shadow 0.3s",
        }}
      />
      <span style={{ fontSize: 13, color: "#888", fontWeight: 500 }}>{label}</span>
    </div>
  );
}
