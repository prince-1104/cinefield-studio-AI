import { useState, type FC } from "react";
import { ProjectDetail } from "../types";
import { ShotCard } from "./ShotCard";
import { assembleVideo, retryShot } from "../api/client";

interface GenerationStepProps {
  project: ProjectDetail;
  onAssembled: (project: ProjectDetail) => void;
  onError: (msg: string) => void;
}

export const GenerationStep: FC<GenerationStepProps> = ({
  project,
  onAssembled,
  onError,
}) => {
  const [retryingShotId, setRetryingShotId] = useState<string | null>(null);
  const [assembling, setAssembling] = useState(false);

  const doneShotsCount = project.shots.filter((s) => s.status === "DONE").length;
  const allShotsDone = doneShotsCount === 3;
  const narrationReady = Boolean(project.narration_path);
  const isReadyToAssemble = allShotsDone && narrationReady;
  const isAssembled = project.stage === "ASSEMBLED" || Boolean(project.final_video_path);

  const handleRetryShot = async (shotId: string) => {
    setRetryingShotId(shotId);
    try {
      await retryShot(project.id, shotId);
    } catch (err: any) {
      console.error("Failed to retry shot:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to retry shot"
      );
    } finally {
      setRetryingShotId(null);
    }
  };

  const handleAssemble = async () => {
    setAssembling(true);
    try {
      await assembleVideo(project.id);
    } catch (err: any) {
      console.error("Failed to trigger assembly:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to trigger assembly"
      );
      setAssembling(false);
    }
  };

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div>
          <h2 className="card-title">3. Video Generation & Shot Assembly</h2>
          <p className="card-subtitle" style={{ marginBottom: 0 }}>
            Gemini Omni Flash is synthesizing 3 cinematic clips in parallel, while OpenAI synthesizes voiceover narration.
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#60a5fa" }}>
            {doneShotsCount}/3 Clips Ready
          </div>
          <div style={{ fontSize: "0.8rem", color: narrationReady ? "#10b981" : "#f59e0b" }}>
            {narrationReady ? "✓ Voiceover Synthesized" : "⚡ Synthesizing Narration..."}
          </div>
        </div>
      </div>

      {/* Shots Grid */}
      <div className="shots-grid">
        {project.shots.map((shot) => (
          <ShotCard
            key={shot.id}
            shot={shot}
            onRetry={handleRetryShot}
            isRetrying={retryingShotId === shot.id}
          />
        ))}
      </div>

      {/* Assembly Control Bar */}
      <div
        style={{
          marginTop: "1.5rem",
          paddingTop: "1.5rem",
          borderTop: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          {isAssembled ? (
            <span style={{ color: "#10b981", fontWeight: 600 }}>
              ✓ Final advertisement has been assembled!
            </span>
          ) : isReadyToAssemble ? (
            <span style={{ color: "#60a5fa", fontWeight: 600 }}>
              All 3 video clips & audio narration ready for FFmpeg assembly.
            </span>
          ) : (
            <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              Waiting for video generation and narration to complete...
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "1rem" }}>
          {isAssembled ? (
            <button
              className="btn btn-primary"
              onClick={() => onAssembled(project)}
            >
              View Finished Advertisement ➔
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={handleAssemble}
              disabled={!isReadyToAssemble || assembling}
            >
              {assembling ? "Assembling with FFmpeg..." : "Assemble Advertisement ➔"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
