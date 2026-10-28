import { useState, type FC } from "react";
import { ProjectDetail } from "../types";
import { ShotCard } from "./ShotCard";
import { approveStoryboard } from "../api/client";
import {
  Clapperboard,
  ArrowLeft,
  CheckCircle,
  Film,
  Clock,
} from "lucide-react";

interface StoryboardStepProps {
  project: ProjectDetail;
  onApproved: (project: ProjectDetail) => void;
  onBackToBrief: () => void;
  onError: (msg: string) => void;
}

export const StoryboardStep: FC<StoryboardStepProps> = ({
  project,
  onApproved,
  onBackToBrief,
  onError,
}) => {
  const [approving, setApproving] = useState(false);

  const shotCount = project.shots ? project.shots.length : 0;
  const hasShots = shotCount > 0;
  const targetDur = project.target_duration || 60;

  const handleApprove = async () => {
    setApproving(true);
    try {
      await approveStoryboard(project.id);
      onApproved(project);
    } catch (err: any) {
      console.error("Failed to approve storyboard:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to approve storyboard"
      );
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="storyboard-workspace">
      {/* Workspace Heading */}
      <div className="workspace-header">
        <div className="workspace-title-row">
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h1 className="workspace-heading">Storyboard & Timeline Review</h1>
            <span className="status-pill pending" style={{ fontSize: "0.75rem" }}>
              <Clock size={12} />
              <span>{targetDur}s Planned · {shotCount} Shots</span>
            </span>
          </div>

          <button
            type="button"
            className="btn-secondary-studio"
            onClick={onBackToBrief}
            style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}
          >
            <ArrowLeft size={14} />
            <span>Edit Campaign Brief</span>
          </button>
        </div>
        <p className="workspace-subheading">
          Review the generated {shotCount}-shot narrative sequence for <strong>{project.product_name}</strong>.
          Upon approval, Gemini Omni Flash will synthesize all clips while OpenAI generates synchronized voiceover narration.
        </p>
      </div>

      {/* Script Narrative Arc Banner */}
      {project.script && (
        <div className="storyboard-narrative-card">
          <div className="narrative-icon-col">
            <Film size={18} />
          </div>
          <div className="narrative-content-col">
            <div className="narrative-label">Cohesive Script Narrative Arc</div>
            <p className="narrative-script-text">{project.script}</p>
          </div>
        </div>
      )}

      {/* Shots Grid or Waiting State */}
      {!hasShots ? (
        <div
          style={{
            textAlign: "center",
            padding: "4rem 2rem",
            backgroundColor: "var(--bg-surface)",
            borderRadius: "var(--radius-lg)",
            border: "1px dashed var(--border-default)",
          }}
        >
          <div className="pulse-spinner" style={{ margin: "0 auto 1.25rem auto" }} />
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            Architecting {targetDur}s Cinematic Arc...
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", maxWidth: "520px", margin: "0 auto" }}>
            Gemini AI is structuring scenes, camera movements, timeline windows, and narration lines tailored to your campaign brief.
            This screen updates automatically via live stream.
          </p>
        </div>
      ) : (
        <>
          <div className="shots-filmstrip-grid">
            {project.shots.map((shot) => (
              <ShotCard key={shot.id} shot={shot} />
            ))}
          </div>

          {/* Action Bar */}
          <div
            className="studio-panel"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "1.25rem 1.75rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--status-done)", fontSize: "0.85rem" }}>
              <CheckCircle size={16} />
              <span>
                {shotCount} sequential shots covering {targetDur}.0s timeline validated and ready for production synthesis
              </span>
            </div>

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={onBackToBrief}
              >
                Modify Parameters
              </button>
              <button
                type="button"
                className="btn-primary-studio"
                onClick={handleApprove}
                disabled={approving}
              >
                {approving ? (
                  <>
                    <div className="pulse-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                    <span>Queuing Synthesis Jobs...</span>
                  </>
                ) : (
                  <>
                    <Clapperboard size={16} />
                    <span>Approve Storyboard & Generate Video</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
