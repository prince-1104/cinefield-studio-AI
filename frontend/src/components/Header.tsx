import type { FC } from "react";
import { ProjectStage } from "../types";

interface HeaderProps {
  stage?: ProjectStage;
  liveConnected?: boolean;
}

export const Header: FC<HeaderProps> = ({ stage, liveConnected }) => {
  return (
    <header className="app-header">
      <div className="brand-title">
        <span>🎬 AI Ad Film Studio</span>
        <span className="brand-badge">Omni Cinema Engine</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        {liveConnected && (
          <div className="live-indicator">
            <span className="live-dot" />
            Live Sync
          </div>
        )}
        {stage && (
          <span
            className="status-badge"
            style={{
              background: "rgba(59, 130, 246, 0.15)",
              color: "#93c5fd",
              border: "1px solid #3b82f6",
              padding: "0.3rem 0.75rem",
            }}
          >
            Stage: {stage}
          </span>
        )}
      </div>
    </header>
  );
};
