import { type FC } from "react";
import {
  Undo2,
  Redo2,
  Save,
  Download,
  ArrowLeft,
  History,
  Sparkles,
} from "lucide-react";
import { TimelineEditSummary } from "../../types";

interface EditorTopBarProps {
  projectName: string;
  version: number;
  isDirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onSave: () => void;
  onExport: () => void;
  isSaving: boolean;
  isExporting: boolean;
  downloadUrl?: string | null;
  hasRenderedVideo: boolean;
  history: TimelineEditSummary[];
  onSelectVersion: (verId: string) => void;
  onBackToProduction: () => void;
}

export const EditorTopBar: FC<EditorTopBarProps> = ({
  projectName,
  version,
  isDirty,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onSave,
  onExport,
  isSaving,
  isExporting,
  downloadUrl,
  hasRenderedVideo,
  history,
  onSelectVersion,
  onBackToProduction,
}) => {
  return (
    <div className="editor-topbar">
      {/* Left: Back & Project Title */}
      <div className="editor-topbar-left">
        <button
          className="btn-secondary-studio"
          onClick={onBackToProduction}
          title="Back to Production Monitor"
          style={{ padding: "0.4rem 0.75rem", fontSize: "0.8rem" }}
        >
          <ArrowLeft size={14} />
          <span>Pipeline</span>
        </button>

        <div className="editor-project-info">
          <span className="editor-project-name">{projectName}</span>
          <span className="editor-version-tag">Version {version}</span>
          <div
            className={`save-status-indicator ${isDirty ? "unsaved" : "saved"}`}
            title={isDirty ? "Unsaved timeline modifications" : "All changes persisted to database"}
          >
            <span className="save-status-dot" />
            <span>{isDirty ? "Unsaved Changes" : "Saved"}</span>
          </div>
        </div>
      </div>

      {/* Center: Undo, Redo, Version Switcher */}
      <div className="editor-topbar-center">
        <div className="editor-history-controls">
          <button
            className="editor-icon-btn"
            onClick={onUndo}
            disabled={!canUndo}
            title="Undo (Ctrl+Z)"
          >
            <Undo2 size={16} />
          </button>
          <button
            className="editor-icon-btn"
            onClick={onRedo}
            disabled={!canRedo}
            title="Redo (Ctrl+Y)"
          >
            <Redo2 size={16} />
          </button>

          {history.length > 1 && (
            <div className="version-selector-wrap">
              <History size={14} style={{ color: "#94a3b8" }} />
              <select
                className="version-dropdown"
                value={history.find((h) => h.version === version)?.id || ""}
                onChange={(e) => onSelectVersion(e.target.value)}
                title="Switch timeline revision"
              >
                {history.map((h) => (
                  <option key={h.id} value={h.id}>
                    v{h.version} ({h.clip_count} clips · {h.duration}s){h.has_rendered_video ? " ✓" : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Right: Save, Export Video & Download */}
      <div className="editor-topbar-right">
        <button
          className="btn-secondary-studio"
          onClick={onSave}
          disabled={!isDirty || isSaving}
          style={{ padding: "0.45rem 0.85rem", fontSize: "0.82rem" }}
        >
          {isSaving ? (
            <>
              <div className="pulse-spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Save size={14} />
              <span>Save Version</span>
            </>
          )}
        </button>

        <button
          className="btn-primary-studio"
          onClick={onExport}
          disabled={isExporting}
          style={{ padding: "0.45rem 1rem", fontSize: "0.82rem" }}
        >
          {isExporting ? (
            <>
              <div className="pulse-spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
              <span>Compiling Video...</span>
            </>
          ) : (
            <>
              <Sparkles size={14} />
              <span>Export Video</span>
            </>
          )}
        </button>

        {hasRenderedVideo && downloadUrl && !isExporting && (
          <a
            href={downloadUrl}
            className="btn-primary-studio"
            style={{
              padding: "0.45rem 0.9rem",
              fontSize: "0.82rem",
              background: "linear-gradient(135deg, #059669 0%, #10b981 100%)",
              borderColor: "rgba(16, 185, 129, 0.4)",
              textDecoration: "none",
            }}
            download
            title="Download verified cinema master MP4"
          >
            <Download size={14} />
            <span>Download MP4</span>
          </a>
        )}
      </div>
    </div>
  );
};
