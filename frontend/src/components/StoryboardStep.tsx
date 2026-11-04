import { useState, useEffect, type FC } from "react";
import { ProjectDetail, VideoModelInfo } from "../types";
import { ShotCard } from "./ShotCard";
import { approveStoryboard, getVideoModels, selectProjectModel, cancelProjectGeneration } from "../api/client";
import {
  Clapperboard,
  ArrowLeft,
  CheckCircle,
  Film,
  Clock,
  Cpu,
  Square,
  AlertTriangle,
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
  const [models, setModels] = useState<VideoModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(
    project.selected_video_model || ""
  );
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    getVideoModels()
      .then((data) => {
        setModels(data);
        if (project.selected_video_model) {
          setSelectedModelId(project.selected_video_model);
        } else if (data.length > 0) {
          const defaultModel = data.find((m) => m.is_default) || data[0];
          if (defaultModel) {
            setSelectedModelId(defaultModel.id);
          }
        }
      })
      .catch((err) => console.warn("Failed to load video models in storyboard review:", err));
  }, [project.selected_video_model]);

  const shotCount = project.shots ? project.shots.length : 0;
  const hasShots = shotCount > 0;
  const targetDur = project.target_duration || 60;

  const handleModelSelect = async (newModelId: string) => {
    setSelectedModelId(newModelId);
    try {
      const found = models.find((m) => m.id === newModelId);
      await selectProjectModel(project.id, newModelId, found?.provider);
    } catch (err) {
      console.warn("Failed to persist model selection:", err);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      const found = models.find((m) => m.id === selectedModelId);
      await approveStoryboard(project.id, selectedModelId, found?.provider);
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

  const handleConfirmCancel = async () => {
    setIsCancelling(true);
    try {
      await cancelProjectGeneration(project.id);
      setShowCancelModal(false);
      onBackToBrief();
    } catch (err: any) {
      console.error("Failed to cancel storyboard generation:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to cancel storyboard generation"
      );
    } finally {
      setIsCancelling(false);
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
          Select your generative video model below to synthesize clips upon approval.
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
            padding: "3.5rem 2rem",
            backgroundColor: "var(--bg-surface)",
            borderRadius: "var(--radius-lg)",
            border: "1px dashed var(--border-default)",
          }}
        >
          <div className="pulse-spinner" style={{ margin: "0 auto 1.25rem auto" }} />
          <h3 style={{ fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            Architecting {targetDur}s Cinematic Arc...
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", maxWidth: "520px", margin: "0 auto 1.5rem auto", lineHeight: 1.5 }}>
            Structuring scenes, camera movements, timeline windows, and narration lines tailored to your campaign brief.
            This screen updates automatically via live stream.
          </p>

          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: "0.75rem",
                color: "#cbd5e1",
                background: "rgba(139, 92, 246, 0.15)",
                border: "1px solid rgba(139, 92, 246, 0.3)",
                padding: "0.3rem 0.75rem",
                borderRadius: "9999px",
              }}
            >
              Stage: {project.stage} · {project.progress_percent}% Progress
            </span>

            <button
              type="button"
              className="btn-secondary-studio"
              onClick={() => setShowCancelModal(true)}
              style={{
                borderColor: "rgba(239, 68, 68, 0.5)",
                backgroundColor: "rgba(239, 68, 68, 0.12)",
                color: "#f87171",
                fontSize: "0.82rem",
                padding: "0.45rem 1rem",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
              }}
            >
              <Square size={13} style={{ fill: "#f87171" }} />
              <span>Stop Generation</span>
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="shots-filmstrip-grid">
            {project.shots.map((shot) => (
              <ShotCard key={shot.id} shot={shot} />
            ))}
          </div>

          {/* Action Bar with Model Selector */}
          <div
            className="studio-panel"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "1.25rem 1.75rem",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--status-done)", fontSize: "0.85rem" }}>
                <CheckCircle size={16} />
                <span>
                  {shotCount} shots covering {targetDur}.0s timeline validated
                </span>
              </div>

              {/* Model Selector dropdown in Action Bar */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                <Cpu size={14} style={{ color: "#8b5cf6" }} />
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600 }}>
                  Synthesis Engine:
                </span>
                <select
                  value={selectedModelId}
                  onChange={(e) => handleModelSelect(e.target.value)}
                  style={{
                    background: "var(--bg-surface-elevated)",
                    border: "1px solid var(--border-default)",
                    color: "#ffffff",
                    padding: "0.4rem 0.85rem",
                    borderRadius: "6px",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    outline: "none",
                    cursor: "pointer",
                  }}
                >
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.provider_name})
                    </option>
                  ))}
                </select>
              </div>
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

      {/* Cancellation Confirmation Dialog */}
      {showCancelModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "1rem",
          }}
          onClick={() => !isCancelling && setShowCancelModal(false)}
        >
          <div
            style={{
              backgroundColor: "var(--bg-surface-elevated, #18181b)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              borderRadius: "12px",
              maxWidth: "480px",
              width: "100%",
              padding: "1.75rem",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "50%",
                  backgroundColor: "rgba(239, 68, 68, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#ef4444",
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
                  Stop Storyboard Generation?
                </h3>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                  Project: {project.product_name}
                </span>
              </div>
            </div>

            <p style={{ color: "#e2e8f0", fontSize: "0.85rem", lineHeight: 1.5, marginBottom: "1rem" }}>
              Are you sure you want to stop generating the storyboard?
            </p>

            <div
              style={{
                backgroundColor: "rgba(245, 158, 11, 0.08)",
                border: "1px solid rgba(245, 158, 11, 0.25)",
                borderRadius: "8px",
                padding: "0.75rem",
                marginBottom: "1.5rem",
                fontSize: "0.78rem",
                color: "#fcd34d",
                lineHeight: 1.45,
              }}
            >
              <strong>Important note:</strong> Any AI request already dispatched to the model provider (Claude or Gemini) may have incurred token charges. Stopping now discards the in-flight generation and returns you to the campaign brief editor so you can refine your prompt or adjust duration.
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={() => setShowCancelModal(false)}
                disabled={isCancelling}
                style={{ padding: "0.55rem 1rem", fontSize: "0.85rem" }}
              >
                Keep Generating
              </button>
              <button
                type="button"
                onClick={handleConfirmCancel}
                disabled={isCancelling}
                style={{
                  backgroundColor: "#dc2626",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "0.55rem 1.15rem",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  cursor: isCancelling ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.45rem",
                }}
              >
                {isCancelling ? (
                  <>
                    <div className="pulse-spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
                    <span>Stopping...</span>
                  </>
                ) : (
                  <>
                    <Square size={13} style={{ fill: "#ffffff" }} />
                    <span>Confirm & Stop Generation</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
