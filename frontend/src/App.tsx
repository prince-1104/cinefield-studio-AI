import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  service: string;
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthResponse>;
      })
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>🎬 AI Ad Film Studio</h1>
      <p>Phase P0 scaffold — frontend is running.</p>
      <h2>Backend Health</h2>
      {error && <p style={{ color: "red" }}>⚠ Connection failed: {error}</p>}
      {health && (
        <p style={{ color: "green" }}>
          ✅ {health.service} — {health.status}
        </p>
      )}
      {!health && !error && <p>Checking…</p>}
    </div>
  );
}

export default App;
