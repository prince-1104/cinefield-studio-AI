import { useState, useEffect, type FC } from "react";
import { ProjectSummary } from "../types";
import { listProjects } from "../api/client";
import { X, FolderOpen, Clock, Film } from "lucide-react";

interface RecentProjectsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectProject: (projectId: string) => void;
  currentProjectId?: string;
}

export const RecentProjectsModal: FC<RecentProjectsModalProps> = ({
  isOpen,
  onClose,
  onSelectProject,
  currentProjectId,
}) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setError(null);
      listProjects()
        .then((data) => {
          setProjects(data);
        })
        .catch((err) => {
          console.error("Failed to load projects:", err);
          setError("Failed to load recent projects.");
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const formatDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <FolderOpen size={18} style={{ color: "#8b5cf6" }} />
            <h3 className="modal-title">Recent Campaigns & Projects</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {loading && (
            <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
              Loading projects...
            </div>
          )}

          {error && (
            <div className="studio-alert-error" style={{ margin: "1rem 0" }}>
              <span>{error}</span>
            </div>
          )}

          {!loading && projects.length === 0 && (
            <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
              <Film size={32} style={{ marginBottom: "0.5rem", opacity: 0.5 }} />
              <p>No campaigns found yet. Create your first ad film!</p>
            </div>
          )}

          {!loading &&
            projects.map((p) => {
              const isCurrent = p.id === currentProjectId;
              return (
                <div key={p.id} className="project-list-row">
                  <div className="project-list-meta">
                    <span className="project-list-name">
                      {p.product_name}
                      {isCurrent && (
                        <span
                          style={{
                            marginLeft: "0.5rem",
                            fontSize: "0.68rem",
                            color: "#8b5cf6",
                            background: "rgba(124, 58, 237, 0.15)",
                            padding: "0.1rem 0.4rem",
                            borderRadius: "4px",
                          }}
                        >
                          Active
                        </span>
                      )}
                    </span>
                    <span className="project-list-date">
                      <Clock size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
                      Created: {formatDate(p.created_at)} · Stage: {p.stage}
                    </span>
                  </div>

                  <button
                    className="btn-secondary-studio"
                    style={{ padding: "0.4rem 0.75rem", fontSize: "0.78rem" }}
                    onClick={() => {
                      onSelectProject(p.id);
                      onClose();
                    }}
                  >
                    Open Studio
                  </button>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};

