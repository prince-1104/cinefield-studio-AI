import { type FC } from "react";
import {
  Clapperboard,
  Plus,
  Film,
  Layers,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNewProject: () => void;
  onOpenRecent: () => void;
  recentCount: number;
}

export const Sidebar: FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  onNewProject,
  onOpenRecent,
  recentCount,
}) => {
  return (
    <aside className={`studio-sidebar ${collapsed ? "collapsed" : ""}`}>
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-badge-row">
          <div className="brand-mark" title="Pexyl Studio">
            <Clapperboard size={18} />
          </div>
          {!collapsed && (
            <div className="brand-info">
              <span className="brand-name">
                Pexyl Studio
              </span>
              <span className="brand-tag">Omni Cinema Engine</span>
            </div>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          className="asset-remove-btn"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{ width: "26px", height: "26px" }}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* New Project CTA */}
      <div className="sidebar-action-wrap">
        <button
          className="btn-new-campaign"
          onClick={onNewProject}
          title="New Creation"
        >
          <Plus size={16} />
          {!collapsed && <span>New Creation</span>}
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {!collapsed && <div className="nav-section-title">Workspace</div>}

        <button className="sidebar-nav-item active" title="Creative Studio">
          <Film size={16} />
          {!collapsed && <span>Creative Studio</span>}
        </button>

        <button
          className="sidebar-nav-item"
          onClick={onOpenRecent}
          title="Recent Projects"
        >
          <Layers size={16} />
          {!collapsed && (
            <>
              <span>Recent Projects</span>
              {recentCount > 0 && <span className="nav-count">{recentCount}</span>}
            </>
          )}
        </button>
      </nav>

      {/* Engine Status Bottom Panel */}
      {!collapsed && (
        <div className="sidebar-footer">
          <div className="engine-status-pill">
            <div className="engine-dot" />
            <div className="engine-text">
              <strong>Gemini Omni Flash</strong>
              <span>1080p Cinema Master</span>
            </div>
            <Sparkles size={14} style={{ marginLeft: "auto", color: "#8b5cf6" }} />
          </div>
        </div>
      )}
    </aside>
  );
};

