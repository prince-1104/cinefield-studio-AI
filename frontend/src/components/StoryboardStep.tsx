import { useState, type FC } from "react";
import { ProjectDetail } from "../types";
import { ShotCard } from "./ShotCard";
import { approveStoryboard } from "../api/client";

interface StoryboardStepProps {
  project: ProjectDetail;
  onApproved: (project: ProjectDetail) => void;
  onError: (msg: string) => void;
}

export const StoryboardStep: FC<StoryboardStepProps> = ({
  project,
  onApproved,
  onError,
}) => {
  const [approving, setApproving] = useState(false);

  const hasShots = project.shots && project.shots.length === 3;

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
    <div>
      <div className="card">
        <h2 className="card-title">2. Review & Approve Storyboard</h2>
        <p className="card-subtitle">
          The Gemini creative director has generated this 3-shot cinematic arc for{" "}
          <strong>{project.product_name}</strong>.
        </p>

        {project.script && (
          <div
            style={{
              background: "#0d141e",
              border: "1px solid var(--border-color)",
              borderRadius: "0.5rem",
              padding: "1rem",
              marginBottom: "1.5rem",
            }}
          >
            <div className="shot-field-title">Script Narrative Arc</div>
            <p style={{ color: "var(--text-primary)", fontSize: "0.95rem" }}>
              {project.script}
            </p>
          </div>
        )}

        {!hasShots ? (
          <div
            style={{
              textAlign: "center",
              padding: "3rem 1rem",
              background: "#0d141e",
              borderRadius: "0.5rem",
              border: "1px dashed var(--border-color)",
            }}
          >
            <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>⏳</div>
            <h3 style={{ fontSize: "1.1rem", marginBottom: "0.25rem" }}>
              Generating Storyboard & Shots...
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              Gemini is structuring your 3-shot campaign. This screen will update automatically.
            </p>
          </div>
        ) : (
          <>
            <div className="shots-grid">
              {project.shots.map((shot) => (
                <ShotCard key={shot.id} shot={shot} />
              ))}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginTop: "1.5rem",
                paddingTop: "1.5rem",
                borderTop: "1px solid var(--border-color)",
              }}
            >
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                ✓ Exactly 3 cinematic shots ready for generation
              </div>

              <button
                className="btn btn-primary"
                onClick={handleApprove}
                disabled={approving || !hasShots}
              >
                {approving
                  ? "Scheduling Video Generation..."
                  : "Approve Storyboard & Generate Videos ➔"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
