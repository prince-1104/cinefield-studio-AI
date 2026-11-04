import { useState, useEffect, type FC } from "react";
import {
  OverviewMetrics,
  ProviderMetric,
  ModelMetric,
  ProjectCostMetric,
  ProjectDetailMetrics,
  AIUsageRecord,
  AIUsageRecordDetail,
} from "../../types";
import {
  getAdminOverview,
  getAdminProviders,
  getAdminModels,
  getAdminProjects,
  getAdminProjectDetail,
  getAdminUsageLedger,
  downloadAdminUsageCsv,
  reconcileBilling,
  getAdminUsageDetail,
  getArtifactUrl,
} from "../../api/client";
import {
  DollarSign,
  TrendingUp,
  Cpu,
  Layers,
  Film,
  Download,
  Search,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Key,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Eye,
  Copy,
  Check,
  FileText,
  Volume2,
  ExternalLink,
  Sparkles,
} from "lucide-react";

interface AdminDashboardProps {
  onBackToStudio: () => void;
  onSelectProject?: (projectId: string) => void;
}

// Safe numeric and formatting helpers to guard against nulls, undefined, or string Decimal types
const num = (v: any, fallback = 0): number => {
  if (v === null || v === undefined) return fallback;
  const parsed = typeof v === "number" ? v : parseFloat(v);
  return isNaN(parsed) ? fallback : parsed;
};

const fmtCost = (v: any, decimals = 4): string => {
  return num(v).toFixed(decimals);
};

const fmtTokens = (v: any): string => {
  return (num(v) / 1000).toFixed(1);
};

export const AdminDashboard: FC<AdminDashboardProps> = ({ onBackToStudio, onSelectProject }) => {
  // Authentication State
  const [adminKey, setAdminKey] = useState<string>(
    localStorage.getItem("pexyl_admin_key") || "pexyl-admin-secret-2026"
  );
  const [authInput, setAuthInput] = useState<string>(adminKey);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Date & Origin Filter State
  const [rangePreset, setRangePreset] = useState<string>("30d");
  const [originFilter, setOriginFilter] = useState<string>("production");

  // Analytics Data States
  const [loading, setLoading] = useState<boolean>(true);
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [providers, setProviders] = useState<ProviderMetric[]>([]);
  const [models, setModels] = useState<ModelMetric[]>([]);
  const [projects, setProjects] = useState<ProjectCostMetric[]>([]);

  // Usage Ledger States
  const [ledgerItems, setLedgerItems] = useState<AIUsageRecord[]>([]);
  const [ledgerTotal, setLedgerTotal] = useState<number>(0);
  const [ledgerPage, setLedgerPage] = useState<number>(0);
  const [ledgerLimit] = useState<number>(25);
  const [ledgerProviderFilter, setLedgerProviderFilter] = useState<string>("");
  const [ledgerStatusFilter, setLedgerStatusFilter] = useState<string>("");
  const [ledgerSearch, setLedgerSearch] = useState<string>("");

  // Project Detail Modal
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectDetail, setProjectDetail] = useState<ProjectDetailMetrics | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);

  // AI Usage & Content Inspector State
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [recordDetail, setRecordDetail] = useState<AIUsageRecordDetail | null>(null);
  const [loadingRecordDetail, setLoadingRecordDetail] = useState<boolean>(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleInspectRecord = async (item: AIUsageRecord) => {
    setSelectedRecordId(item.id);
    setLoadingRecordDetail(true);
    setCopiedKey(null);
    try {
      const detail = await getAdminUsageDetail(item.id, adminKey);
      setRecordDetail(detail);
    } catch (err) {
      console.warn("Could not fetch detailed usage record from backend:", err);
      setRecordDetail({
        ...item,
        usage_origin: item.usage_origin || "production",
        media_url: item.video_path || null,
        media_type: (item.billing_unit === "video_seconds" || item.operation.includes("video")) ? "video" : null,
        content_title: item.shot_description
          ? `Shot #${item.shot_number || 1}: ${item.shot_description}`
          : `${item.provider.toUpperCase()} ${item.operation.replace(/_/g, " ")}`,
        content_prompt: item.visual_prompt || null,
        content_output: null,
      } as AIUsageRecordDetail);
    } finally {
      setLoadingRecordDetail(false);
    }
  };

  const handleCopy = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Reconciliation Modal
  const [reconcileModalOpen, setReconcileModalOpen] = useState<boolean>(false);
  const [reconcileTaskId, setReconcileTaskId] = useState<string>("");
  const [reconcileCost, setReconcileCost] = useState<string>("");
  const [reconcileMsg, setReconcileMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [reconciling, setReconciling] = useState<boolean>(false);

  const fetchDashboardData = async () => {
    setLoading(true);
    setAuthError(null);
    try {
      const [ov, provs, mdls, projs] = await Promise.all([
        getAdminOverview(rangePreset, undefined, undefined, adminKey, originFilter),
        getAdminProviders(rangePreset, undefined, undefined, adminKey, originFilter),
        getAdminModels(rangePreset, undefined, undefined, adminKey, originFilter),
        getAdminProjects(rangePreset, undefined, undefined, adminKey, originFilter),
      ]);
      setOverview(ov);
      setProviders(provs);
      setModels(mdls);
      setProjects(projs);
      setIsAuthenticated(true);
    } catch (err: any) {
      console.error("Failed to load admin metrics:", err);
      if (err.response?.status === 401) {
        setIsAuthenticated(false);
        setAuthError("Unauthorized: Invalid Admin Key. Please enter your secret key.");
      } else {
        setAuthError(err.response?.data?.detail || err.message || "Failed to load admin metrics");
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchLedger = async () => {
    try {
      const data = await getAdminUsageLedger(
        {
          provider: ledgerProviderFilter || undefined,
          requestStatus: ledgerStatusFilter || undefined,
          origin: originFilter,
          range: rangePreset,
          limit: ledgerLimit,
          offset: ledgerPage * ledgerLimit,
        },
        adminKey
      );
      setLedgerItems(data.items);
      setLedgerTotal(data.total);
    } catch (err) {
      console.warn("Could not fetch ledger items:", err);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    fetchLedger();
  }, [rangePreset, adminKey, originFilter]);

  useEffect(() => {
    fetchLedger();
  }, [ledgerPage, ledgerProviderFilter, ledgerStatusFilter]);

  const handleUpdateAdminKey = () => {
    const clean = authInput.trim();
    localStorage.setItem("pexyl_admin_key", clean);
    setAdminKey(clean);
  };

  const handleExportCsv = async () => {
    try {
      const blob = await downloadAdminUsageCsv(
        {
          provider: ledgerProviderFilter || undefined,
          origin: originFilter,
          range: rangePreset,
        },
        adminKey
      );
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pexyl_ai_usage_export_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert("Failed to export CSV: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleViewProjectDetail = async (projId: string) => {
    setSelectedProjectId(projId);
    setLoadingDetail(true);
    try {
      const detail = await getAdminProjectDetail(projId, adminKey);
      setProjectDetail(detail);
    } catch (err: any) {
      alert("Could not load project detail: " + (err.response?.data?.detail || err.message));
      setSelectedProjectId(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handlePerformReconciliation = async () => {
    if (!reconcileTaskId.trim() || !reconcileCost.trim()) {
      setReconcileMsg({ text: "Please enter both Task ID and Actual Cost", isError: true });
      return;
    }
    setReconciling(true);
    setReconcileMsg(null);
    try {
      const res = await reconcileBilling(reconcileTaskId.trim(), parseFloat(reconcileCost), adminKey);
      setReconcileMsg({ text: res.message, isError: false });
      setReconcileTaskId("");
      setReconcileCost("");
      fetchDashboardData();
      fetchLedger();
    } catch (err: any) {
      setReconcileMsg({
        text: err.response?.data?.detail || err.message || "Failed to reconcile task billing",
        isError: true,
      });
    } finally {
      setReconciling(false);
    }
  };

  return (
    <div className="admin-shell">
      {/* Admin Top Bar */}
      <div className="admin-header">
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <button
            type="button"
            className="btn-secondary-studio"
            onClick={onBackToStudio}
            style={{ padding: "0.45rem 0.85rem", fontSize: "0.8rem" }}
          >
            ← Back to Creative Studio
          </button>
          <div>
            <div className="admin-title">
              <TrendingUp size={20} style={{ color: "#38bdf8" }} />
              <span>Pexyl AI Usage & Cost Analytics</span>
              <span className="admin-badge">Admin Gateway</span>
            </div>
            <div className="admin-subtitle">
              Centralized financial ledger tracking Claude token consumption, Seedance video seconds, and multi-model expenses.
            </div>
          </div>
        </div>

        {/* Date & Origin Filters & CSV Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
          {/* Usage Origin Filter Pills */}
          <div className="date-filter-group" title="Filter AI Usage Origin">
            {[
              { id: "production", label: "Production (Live)" },
              { id: "test", label: "Test & QA" },
              { id: "all", label: "All Origins" },
            ].map((o) => (
              <button
                key={o.id}
                type="button"
                className={`date-pill ${originFilter === o.id ? "active" : ""}`}
                onClick={() => {
                  setOriginFilter(o.id);
                  setLedgerPage(0);
                }}
                style={{ fontSize: "0.74rem" }}
              >
                {o.label}
              </button>
            ))}
          </div>

          <div className="date-filter-group">
            {[
              { id: "today", label: "Today" },
              { id: "7d", label: "Last 7 Days" },
              { id: "30d", label: "Last 30 Days" },
              { id: "month", label: "This Month" },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                className={`date-pill ${rangePreset === p.id ? "active" : ""}`}
                onClick={() => setRangePreset(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn-secondary-studio"
            onClick={() => setReconcileModalOpen(true)}
            title="Reconcile estimated cost with actual provider invoice"
            style={{ padding: "0.5rem 0.85rem", fontSize: "0.8rem", gap: "0.4rem" }}
          >
            <CheckCircle2 size={13} style={{ color: "#10b981" }} />
            <span>Reconcile Invoice</span>
          </button>

          <button
            type="button"
            className="btn-primary-studio"
            onClick={handleExportCsv}
            title="Download complete ledger as CSV"
            style={{ padding: "0.5rem 0.95rem", fontSize: "0.8rem", gap: "0.4rem" }}
          >
            <Download size={14} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Admin Key Configuration Bar */}
      <div className="admin-auth-bar">
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <Key size={14} style={{ color: "#8b5cf6" }} />
          <span style={{ fontSize: "0.78rem", color: "#cbd5e1", fontWeight: 600 }}>Admin API Key:</span>
          <input
            type="password"
            className="form-input-custom"
            value={authInput}
            onChange={(e) => setAuthInput(e.target.value)}
            style={{ width: "240px", height: "30px", fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
            placeholder="pexyl-admin-secret-..."
          />
          <button
            type="button"
            className="btn-secondary-studio"
            onClick={handleUpdateAdminKey}
            style={{ padding: "0.3rem 0.65rem", fontSize: "0.75rem" }}
          >
            Apply Key
          </button>
        </div>

        {isAuthenticated ? (
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.75rem", color: "#34d399" }}>
            <CheckCircle2 size={13} />
            <span>Authorized Admin Session</span>
          </span>
        ) : (
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.75rem", color: "#f87171" }}>
            <ShieldAlert size={13} />
            <span>Authentication Required</span>
          </span>
        )}
      </div>

      {authError && (
        <div className="studio-alert-error" style={{ marginBottom: "1.5rem" }}>
          <AlertCircle size={16} />
          <span>{authError}</span>
        </div>
      )}

      {loading && !overview ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "5rem 0", gap: "0.75rem", color: "#94a3b8" }}>
          <div className="pulse-spinner" />
          <span>Aggregating financial data from AI ledger...</span>
        </div>
      ) : (
        <>
          {/* =====================================================================
              1. Overview KPI Cards
              ===================================================================== */}
          {overview && (
            <div className="admin-kpi-grid">
              {/* Total Spend */}
              <div className="admin-kpi-card highlight">
                <div className="kpi-header">
                  <span className="kpi-label">Total AI Spend</span>
                  <DollarSign size={16} style={{ color: "#38bdf8" }} />
                </div>
                <div className="kpi-value">${fmtCost(overview.total_spend)}</div>
                <div className="kpi-breakdown">
                  <span>Actual: <strong>${fmtCost(overview.actual_spend)}</strong></span>
                  <span>Est: <strong>${fmtCost(overview.estimated_spend)}</strong></span>
                  {num(overview.unknown_spend) > 0 && (
                    <span style={{ color: "#f59e0b" }}>Unreconciled: ${fmtCost(overview.unknown_spend)}</span>
                  )}
                </div>
              </div>

              {/* Claude Token Consumption */}
              <div className="admin-kpi-card">
                <div className="kpi-header">
                  <span className="kpi-label">Claude Token Consumption</span>
                  <Cpu size={16} style={{ color: "#d97706" }} />
                </div>
                <div className="kpi-value">
                  {fmtTokens(overview.total_tokens)}k
                </div>
                <div className="kpi-breakdown">
                  <span>In: <strong>{fmtTokens(overview.total_input_tokens)}k</strong></span>
                  <span>Out: <strong>{fmtTokens(overview.total_output_tokens)}k</strong></span>
                </div>
              </div>

              {/* Video Generations */}
              <div className="admin-kpi-card">
                <div className="kpi-header">
                  <span className="kpi-label">Seedance Video Generations</span>
                  <Film size={16} style={{ color: "#8b5cf6" }} />
                </div>
                <div className="kpi-value">{num(overview.total_video_generations)} Clips</div>
                <div className="kpi-breakdown">
                  <span style={{ color: "#34d399" }}>✓ {num(overview.successful_generations)} Done</span>
                  {num(overview.failed_generations) > 0 && (
                    <span style={{ color: "#f87171" }}>✕ {num(overview.failed_generations)} Failed</span>
                  )}
                  <span>{fmtCost(overview.total_video_seconds, 0)}s Total</span>
                </div>
              </div>

              {/* AI Projects */}
              <div className="admin-kpi-card">
                <div className="kpi-header">
                  <span className="kpi-label">Active AI Projects</span>
                  <Layers size={16} style={{ color: "#10b981" }} />
                </div>
                <div className="kpi-value">{num(overview.total_projects_using_ai)}</div>
                <div className="kpi-breakdown">
                  <span>{num(overview.total_requests)} Total API Calls Logged</span>
                </div>
              </div>
            </div>
          )}

          {/* Clean Production / Filter Empty State Notice */}
          {overview && overview.total_requests === 0 && (
            <div
              style={{
                padding: "2rem 1.5rem",
                background: "rgba(30, 41, 59, 0.4)",
                borderRadius: "12px",
                border: "1px dashed rgba(148, 163, 184, 0.25)",
                textAlign: "center",
                margin: "1.5rem 0",
              }}
            >
              <Layers size={32} style={{ color: "#64748b", margin: "0 auto 0.75rem" }} />
              <div style={{ fontSize: "1.05rem", fontWeight: 600, color: "#f8fafc", marginBottom: "0.35rem" }}>
                No AI usage recorded yet.
              </div>
              <div style={{ fontSize: "0.82rem", color: "#94a3b8", maxWidth: "520px", margin: "0 auto", lineHeight: 1.5 }}>
                {originFilter === "production"
                  ? "No production AI API calls have been logged yet. When you generate creative briefs with Claude or video clips with Seedance in active projects, verified token counts and video durations will appear here in real time."
                  : `No AI usage records found matching origin "${originFilter}". Synthetic test runs and unit tests do not pollute production cost metrics.`}
              </div>
            </div>
          )}

          {/* =====================================================================
              2. Provider Analytics Grid
              ===================================================================== */}
          <div className="admin-section">
            <h2 className="admin-section-heading">Provider Spend Breakdown</h2>
            <div className="admin-cards-grid">
              {(providers || []).map((p) => (
                <div key={p.provider} className="provider-summary-card">
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                    <span className="provider-title">{(p.provider || "").toUpperCase()}</span>
                    <span className="provider-cost-badge">${fmtCost(p.total_cost)}</span>
                  </div>
                  <div className="provider-metric-row">
                    <span>Total API Requests:</span>
                    <strong>{num(p.request_count)}</strong>
                  </div>
                  {p.provider === "claude" && (
                    <div className="provider-metric-row">
                      <span>Tokens Processed:</span>
                      <strong>{fmtTokens(num(p.input_tokens) + num(p.output_tokens))}k</strong>
                    </div>
                  )}
                  {p.provider === "seedance" && (
                    <div className="provider-metric-row">
                      <span>Videos Generated:</span>
                      <strong>{num(p.video_generation_count)} clips</strong>
                    </div>
                  )}
                  <div className="provider-metric-row">
                    <span>Failure Rate:</span>
                    <strong style={{ color: num(p.failure_rate) > 0 ? "#f87171" : "#34d399" }}>
                      {fmtCost(p.failure_rate, 1)}%
                    </strong>
                  </div>
                </div>
              ))}
              {(!providers || providers.length === 0) && (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "#64748b", padding: "1.75rem", background: "rgba(15, 23, 42, 0.4)", borderRadius: "8px", border: "1px dashed rgba(148, 163, 184, 0.15)", fontSize: "0.85rem" }}>
                  No AI usage recorded yet.
                </div>
              )}
            </div>
          </div>

          {/* =====================================================================
              3. Model Analytics Table
              ===================================================================== */}
          <div className="admin-section">
            <h2 className="admin-section-heading">Model Analytics & Unit Economics</h2>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Model Identifier</th>
                    <th>Requests</th>
                    <th>Tokens / Duration</th>
                    <th>Actual Spend</th>
                    <th>Estimated Spend</th>
                    <th>Total Spend</th>
                    <th>Avg / Request</th>
                    <th>Failure Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {(models || []).map((m) => (
                    <tr key={`${m.provider}-${m.model}`}>
                      <td>
                        <span className="table-provider-pill">{m.provider}</span>
                      </td>
                      <td style={{ fontWeight: 600, color: "#f8fafc" }}>{m.model}</td>
                      <td>{num(m.total_requests)}</td>
                      <td>
                        {num(m.video_generation_count) > 0
                          ? `${num(m.video_generation_count)} videos`
                          : `${fmtTokens(num(m.input_tokens) + num(m.output_tokens))}k tokens`}
                      </td>
                      <td style={{ color: "#34d399" }}>${fmtCost(m.actual_cost)}</td>
                      <td style={{ color: "#94a3b8" }}>${fmtCost(m.estimated_cost)}</td>
                      <td style={{ fontWeight: 700, color: "#38bdf8" }}>${fmtCost(m.total_cost)}</td>
                      <td>${fmtCost(m.avg_cost_per_request)}</td>
                      <td>
                        <span
                          className={`table-status-tag ${num(m.failure_rate) > 0 ? "failed" : "success"}`}
                        >
                          {fmtCost(m.failure_rate, 1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                  {(!models || models.length === 0) && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No AI usage recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* =====================================================================
              4. Project Cost Comparison Table
              ===================================================================== */}
          <div className="admin-section">
            <h2 className="admin-section-heading">Project Cost & Consumption Matrix</h2>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Project Name</th>
                    <th>Owner</th>
                    <th>API Calls</th>
                    <th>Claude Tokens</th>
                    <th>Seedance Videos</th>
                    <th>Actual Spend</th>
                    <th>Estimated Spend</th>
                    <th>Total Spend</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(projects || []).map((proj) => (
                    <tr key={proj.project_id}>
                      <td style={{ fontWeight: 600, color: "#f8fafc" }}>
                        <div>{proj.project_name}</div>
                        <span style={{ fontSize: "0.68rem", color: "#64748b", fontFamily: "monospace" }}>
                          {(proj.project_id || "").slice(0, 8)}...
                        </span>
                      </td>
                      <td>{proj.owner}</td>
                      <td>{num(proj.total_requests)}</td>
                      <td>
                        {fmtTokens(num(proj.claude_input_tokens) + num(proj.claude_output_tokens))}k
                      </td>
                      <td>
                        {num(proj.video_generation_count)} ({num(proj.successful_videos)} ok / {num(proj.failed_videos)} fail)
                      </td>
                      <td style={{ color: "#34d399" }}>${fmtCost(proj.actual_spend)}</td>
                      <td style={{ color: "#94a3b8" }}>${fmtCost(proj.estimated_spend)}</td>
                      <td style={{ fontWeight: 700, color: "#38bdf8" }}>${fmtCost(proj.total_spend)}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-secondary-studio"
                          style={{ padding: "0.25rem 0.6rem", fontSize: "0.72rem" }}
                          onClick={() => handleViewProjectDetail(proj.project_id)}
                        >
                          View Breakdown
                        </button>
                      </td>
                    </tr>
                  ))}
                  {(!projects || projects.length === 0) && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No AI usage recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* =====================================================================
              5. Searchable Usage Ledger
              ===================================================================== */}
          <div className="admin-section">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem", flexWrap: "wrap", gap: "1rem" }}>
              <h2 className="admin-section-heading" style={{ margin: 0 }}>
                Immutable AI Usage Ledger ({ledgerTotal} Records)
              </h2>

              {/* Filters */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                  <Search size={13} style={{ position: "absolute", left: "8px", color: "#64748b" }} />
                  <input
                    type="text"
                    className="form-input-custom"
                    placeholder="Search ledger..."
                    value={ledgerSearch}
                    onChange={(e) => setLedgerSearch(e.target.value)}
                    style={{ height: "32px", fontSize: "0.76rem", paddingLeft: "1.7rem", width: "160px" }}
                  />
                </div>

                <select
                  className="form-input-custom"
                  value={ledgerProviderFilter}
                  onChange={(e) => {
                    setLedgerProviderFilter(e.target.value);
                    setLedgerPage(0);
                  }}
                  style={{ height: "32px", fontSize: "0.76rem", padding: "0.2rem 0.6rem" }}
                >
                  <option value="">All Providers</option>
                  <option value="claude">Claude</option>
                  <option value="seedance">Seedance</option>
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>

                <select
                  className="form-input-custom"
                  value={ledgerStatusFilter}
                  onChange={(e) => {
                    setLedgerStatusFilter(e.target.value);
                    setLedgerPage(0);
                  }}
                  style={{ height: "32px", fontSize: "0.76rem", padding: "0.2rem 0.6rem" }}
                >
                  <option value="">All Statuses</option>
                  <option value="SUCCESS">Success</option>
                  <option value="FAILED">Failed</option>
                </select>

                <button
                  type="button"
                  className="btn-secondary-studio"
                  onClick={fetchLedger}
                  style={{ padding: "0.35rem 0.75rem", fontSize: "0.76rem", gap: "0.35rem" }}
                >
                  <RefreshCw size={12} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Origin</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Operation</th>
                    <th>Units Consumed</th>
                    <th>Status</th>
                    <th>Cost Type</th>
                    <th>Cost (USD)</th>
                    <th>Task / Request ID</th>
                    <th>Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {ledgerItems
                    .filter((item) => {
                      if (!ledgerSearch.trim()) return true;
                      const q = ledgerSearch.toLowerCase();
                      return (
                        item.provider.toLowerCase().includes(q) ||
                        item.model.toLowerCase().includes(q) ||
                        item.operation.toLowerCase().includes(q) ||
                        (item.provider_task_id && item.provider_task_id.toLowerCase().includes(q))
                      );
                    })
                    .map((item) => (
                    <tr
                      key={item.id}
                      className="clickable-ledger-row"
                      onClick={() => handleInspectRecord(item)}
                      title="Click to inspect generated video clip, prompt, or token breakdown"
                    >
                      <td style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: "0.68rem",
                            fontWeight: 600,
                            padding: "0.15rem 0.45rem",
                            borderRadius: "4px",
                            textTransform: "uppercase",
                            backgroundColor:
                              item.usage_origin === "production"
                                ? "rgba(16, 185, 129, 0.15)"
                                : "rgba(245, 158, 11, 0.15)",
                            color: item.usage_origin === "production" ? "#34d399" : "#fbbf24",
                            border: `1px solid ${
                              item.usage_origin === "production"
                                ? "rgba(16, 185, 129, 0.3)"
                                : "rgba(245, 158, 11, 0.3)"
                            }`,
                          }}
                        >
                          {item.usage_origin || "production"}
                        </span>
                      </td>
                      <td>
                        <span className="table-provider-pill">{item.provider}</span>
                      </td>
                      <td style={{ fontSize: "0.78rem", fontWeight: 600, color: "#f1f5f9" }}>
                        {item.model}
                      </td>
                      <td style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                          {item.billing_unit === "video_seconds" || item.operation.includes("video") ? (
                            <Film size={12} style={{ color: "#c084fc", flexShrink: 0 }} />
                          ) : item.operation.includes("brief") || item.provider === "claude" ? (
                            <FileText size={12} style={{ color: "#38bdf8", flexShrink: 0 }} />
                          ) : item.operation.includes("narration") ? (
                            <Volume2 size={12} style={{ color: "#34d399", flexShrink: 0 }} />
                          ) : null}
                          <span>{item.operation}</span>
                        </div>
                      </td>
                      <td>
                        {item.billing_unit === "video_seconds"
                          ? `${item.video_duration_seconds || item.unit_quantity}s video`
                          : `${item.unit_quantity} tokens`}
                      </td>
                      <td>
                        <span
                          className={`table-status-tag ${
                            item.request_status === "SUCCESS" ? "success" : "failed"
                          }`}
                        >
                          {item.request_status}
                        </span>
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: "0.68rem",
                            padding: "0.15rem 0.45rem",
                            borderRadius: "4px",
                            backgroundColor:
                              item.cost_status === "ACTUAL"
                                ? "rgba(16, 185, 129, 0.2)"
                                : item.cost_status === "RECONCILED"
                                ? "rgba(56, 189, 248, 0.2)"
                                : "rgba(245, 158, 11, 0.2)",
                            color:
                              item.cost_status === "ACTUAL"
                                ? "#34d399"
                                : item.cost_status === "RECONCILED"
                                ? "#38bdf8"
                                : "#fde047",
                          }}
                        >
                          {item.cost_status}
                        </span>
                      </td>
                      <td style={{ fontWeight: 700, color: "#38bdf8" }}>
                        ${fmtCost(item.actual_cost != null ? item.actual_cost : item.estimated_cost, 5)}
                      </td>
                      <td style={{ fontSize: "0.7rem", fontFamily: "monospace", color: "#64748b" }}>
                        {item.provider_task_id || item.provider_request_id || "—"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="quick-toggle-btn"
                          style={{
                            padding: "0.2rem 0.5rem",
                            fontSize: "0.72rem",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            color: "#38bdf8",
                            borderColor: "rgba(56, 189, 248, 0.3)",
                            backgroundColor: "rgba(56, 189, 248, 0.05)",
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleInspectRecord(item);
                          }}
                          title="Inspect video / prompt content"
                        >
                          <Eye size={12} />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                  {(!ledgerItems || ledgerItems.length === 0) && (
                    <tr>
                      <td colSpan={11} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No AI usage recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Bar */}
            <div className="admin-pagination">
              <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                Showing {ledgerPage * ledgerLimit + 1}–
                {Math.min((ledgerPage + 1) * ledgerLimit, ledgerTotal)} of {ledgerTotal}
              </span>
              <div style={{ display: "flex", gap: "0.4rem" }}>
                <button
                  type="button"
                  className="quick-toggle-btn"
                  disabled={ledgerPage === 0}
                  onClick={() => setLedgerPage((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft size={14} /> Previous
                </button>
                <button
                  type="button"
                  className="quick-toggle-btn"
                  disabled={(ledgerPage + 1) * ledgerLimit >= ledgerTotal}
                  onClick={() => setLedgerPage((p) => p + 1)}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* =========================================================================
          Project Detail Drill-Down Modal
          ========================================================================= */}
      {selectedProjectId && (
        <div className="modal-backdrop" onClick={() => setSelectedProjectId(null)}>
          <div className="admin-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Layers size={18} style={{ color: "#38bdf8" }} />
                <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc" }}>
                  Project Cost Intelligence: {projectDetail?.project_name || selectedProjectId}
                </h3>
              </div>
              <button
                type="button"
                className="asset-remove-btn"
                onClick={() => setSelectedProjectId(null)}
              >
                <X size={16} />
              </button>
            </div>

            {loadingDetail || !projectDetail ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "3rem" }}>
                <div className="pulse-spinner" />
              </div>
            ) : (
              <div className="admin-modal-body">
                <div className="admin-kpi-grid" style={{ marginBottom: "1.25rem" }}>
                  <div className="admin-kpi-card highlight">
                    <span className="kpi-label">Total Project AI Spend</span>
                    <div className="kpi-value">${fmtCost(projectDetail.total_spend)}</div>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Claude Creative Planning</span>
                    <div className="kpi-value">${fmtCost(projectDetail.claude_spend)}</div>
                    <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                      {num(projectDetail.claude_tokens?.total)} Tokens
                    </span>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Seedance Video Synthesis</span>
                    <div className="kpi-value">${fmtCost(projectDetail.seedance_spend)}</div>
                    <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                      {num(projectDetail.video_generations_count)} Video Clips
                    </span>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Avg Cost / Finished Shot</span>
                    <div className="kpi-value">${fmtCost(projectDetail.cost_per_shot)}</div>
                  </div>
                </div>

                {/* Per-Shot Cost Breakdown */}
                <h4 style={{ fontSize: "0.88rem", color: "#e2e8f0", marginBottom: "0.6rem" }}>
                  Shot-by-Shot AI Cost Allocation
                </h4>
                <div className="shot-cost-grid">
                  {Object.entries(projectDetail.shot_costs || {}).map(([shotId, cost], idx) => (
                    <div key={shotId} className="shot-cost-pill">
                      <span>Shot #{idx + 1}:</span>
                      <strong>${fmtCost(cost)}</strong>
                    </div>
                  ))}
                  {Object.keys(projectDetail.shot_costs || {}).length === 0 && (
                    <span style={{ color: "#64748b", fontSize: "0.8rem" }}>
                      No per-shot records allocated.
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          Reconciliation Invoice Modal
          ========================================================================= */}
      
      {/* =========================================================================
          AI Usage & Generated Content Inspector Modal
          ========================================================================= */}
      {selectedRecordId && (
        <div className="modal-backdrop" onClick={() => setSelectedRecordId(null)}>
          <div
            className="admin-modal-content"
            style={{ maxWidth: "860px", width: "95%", maxHeight: "90vh" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="admin-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "8px",
                    background: "linear-gradient(135deg, rgba(168, 85, 247, 0.25), rgba(56, 189, 248, 0.25))",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                  }}
                >
                  {recordDetail?.billing_unit === "video_seconds" || recordDetail?.operation?.includes("video") ? (
                    <Film size={18} style={{ color: "#c084fc" }} />
                  ) : recordDetail?.operation?.includes("narration") ? (
                    <Volume2 size={18} style={{ color: "#34d399" }} />
                  ) : (
                    <Sparkles size={18} style={{ color: "#38bdf8" }} />
                  )}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc", fontWeight: 700 }}>
                    AI Spend & Generation Inspector
                  </h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.2rem", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                      Ledger ID: <code style={{ color: "#cbd5e1" }}>{selectedRecordId.slice(0, 13)}...</code>
                    </span>
                    {recordDetail && (
                      <>
                        <span style={{ color: "#475569" }}>•</span>
                        <span className="table-provider-pill" style={{ fontSize: "0.65rem", padding: "0.1rem 0.4rem" }}>
                          {recordDetail.provider}
                        </span>
                        <span style={{ fontSize: "0.72rem", color: "#e2e8f0", fontWeight: 600 }}>
                          {recordDetail.model}
                        </span>
                        <span
                          style={{
                            fontSize: "0.65rem",
                            padding: "0.1rem 0.35rem",
                            borderRadius: "4px",
                            textTransform: "uppercase",
                            backgroundColor:
                              recordDetail.usage_origin === "production"
                                ? "rgba(16, 185, 129, 0.15)"
                                : "rgba(245, 158, 11, 0.15)",
                            color: recordDetail.usage_origin === "production" ? "#34d399" : "#fbbf24",
                            border: `1px solid ${
                              recordDetail.usage_origin === "production"
                                ? "rgba(16, 185, 129, 0.3)"
                                : "rgba(245, 158, 11, 0.3)"
                            }`,
                          }}
                        >
                          {recordDetail.usage_origin}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="asset-remove-btn"
                onClick={() => setSelectedRecordId(null)}
              >
                <X size={18} />
              </button>
            </div>

            {loadingRecordDetail || !recordDetail ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "4rem 2rem", gap: "1rem" }}>
                <div className="pulse-spinner" />
                <span style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Loading generated content and media context...</span>
              </div>
            ) : (
              <div className="admin-modal-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {/* 1. Primary Generated Media / Video */}
                {(recordDetail.billing_unit === "video_seconds" || recordDetail.operation?.includes("video") || recordDetail.media_type === "video") && (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <Film size={15} style={{ color: "#c084fc" }} />
                        <span style={{ fontSize: "0.88rem", fontWeight: 700, color: "#f8fafc" }}>
                          {recordDetail.content_title || `Generated Video Clip (${recordDetail.video_duration_seconds || recordDetail.unit_quantity}s)`}
                        </span>
                      </div>
                      {recordDetail.media_url && (
                        <a
                          href={getArtifactUrl(recordDetail.media_url)}
                          target="_blank"
                          rel="noopener noreferrer"
                          download
                          className="quick-toggle-btn"
                          style={{
                            fontSize: "0.74rem",
                            padding: "0.22rem 0.55rem",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            color: "#c084fc",
                            borderColor: "rgba(192, 132, 252, 0.35)",
                          }}
                        >
                          <Download size={12} />
                          <span>Download MP4</span>
                        </a>
                      )}
                    </div>

                    {recordDetail.media_url ? (
                      <div
                        style={{
                          position: "relative",
                          borderRadius: "10px",
                          overflow: "hidden",
                          background: "#080c14",
                          border: "1px solid rgba(168, 85, 247, 0.3)",
                          boxShadow: "0 8px 30px rgba(0, 0, 0, 0.5)",
                          maxHeight: "360px",
                          display: "flex",
                          justifyContent: "center",
                          alignItems: "center",
                        }}
                      >
                        <video
                          controls
                          autoPlay
                          loop
                          playsInline
                          src={getArtifactUrl(recordDetail.media_url)}
                          style={{ width: "100%", maxHeight: "360px", objectFit: "contain", display: "block" }}
                        />
                      </div>
                    ) : (
                      <div
                        style={{
                          padding: "1.5rem",
                          borderRadius: "10px",
                          backgroundColor: "rgba(30, 41, 59, 0.4)",
                          border: "1px dashed rgba(255, 255, 255, 0.12)",
                          textAlign: "center",
                        }}
                      >
                        <Film size={28} style={{ color: "#64748b", margin: "0 auto 0.5rem auto", display: "block" }} />
                        <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#cbd5e1" }}>
                          {recordDetail.content_title || "Video Generation Record"}
                        </div>
                        <p style={{ margin: "0.3rem 0 0 0", fontSize: "0.78rem", color: "#94a3b8" }}>
                          {recordDetail.usage_origin === "test"
                            ? "Test harness simulation record — no persistent video file was written to disk."
                            : "Video file was either removed, expired, or was generated in a detached session."}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Audio Media Player if voiceover */}
                {(recordDetail.operation?.includes("narration") || recordDetail.media_type === "audio") && (
                  <div
                    style={{
                      padding: "1rem",
                      borderRadius: "10px",
                      background: "rgba(30, 41, 59, 0.4)",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.6rem" }}>
                      <Volume2 size={16} style={{ color: "#34d399" }} />
                      <span style={{ fontSize: "0.88rem", fontWeight: 600, color: "#f8fafc" }}>
                        Synthesized Voiceover Narration
                      </span>
                    </div>
                    {recordDetail.media_url ? (
                      <audio controls src={getArtifactUrl(recordDetail.media_url)} style={{ width: "100%" }} />
                    ) : (
                      <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                        Audio file not retained on disk.
                      </span>
                    )}
                  </div>
                )}

                {/* 2. Content Prompt / Brief on which credits were spent */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                    <span
                      style={{
                        fontSize: "0.76rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                      }}
                    >
                      <Sparkles size={13} style={{ color: "#c084fc" }} />
                      {recordDetail.operation?.includes("brief") || recordDetail.provider === "claude"
                        ? "Creative Prompt & Narrative Brief Input"
                        : "Visual Synthesis Prompt (Sent to Model)"}
                    </span>
                    {(recordDetail.content_prompt || recordDetail.shot?.visual_prompt || recordDetail.project?.brief) && (
                      <button
                        type="button"
                        className="quick-toggle-btn"
                        style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem", display: "inline-flex", alignItems: "center", gap: "0.25rem" }}
                        onClick={() =>
                          handleCopy(
                            recordDetail.content_prompt || recordDetail.shot?.visual_prompt || recordDetail.project?.brief || "",
                            "prompt"
                          )
                        }
                      >
                        {copiedKey === "prompt" ? (
                          <>
                            <Check size={11} style={{ color: "#34d399" }} /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={11} /> Copy Prompt
                          </>
                        )}
                      </button>
                    )}
                  </div>
                  <div
                    style={{
                      padding: "0.85rem 1rem",
                      borderRadius: "8px",
                      backgroundColor: "rgba(15, 23, 42, 0.65)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      fontSize: "0.82rem",
                      lineHeight: 1.55,
                      color: "#f1f5f9",
                      whiteSpace: "pre-wrap",
                      maxHeight: "180px",
                      overflowY: "auto",
                      fontFamily: "var(--font-sans)",
                    }}
                  >
                    {recordDetail.content_prompt ||
                      recordDetail.shot?.visual_prompt ||
                      recordDetail.project?.brief ||
                      "No explicit text prompt associated with this record."}
                  </div>
                </div>

                {/* Creative Scene Breakdown & Direction (if shot metadata is available) */}
                {recordDetail.shot && (
                  <div>
                    <span
                      style={{
                        fontSize: "0.76rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        display: "block",
                        marginBottom: "0.4rem",
                      }}
                    >
                      Scene Direction & Cinema Settings
                    </span>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: "0.5rem",
                      }}
                    >
                      <div style={{ padding: "0.6rem 0.75rem", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                        <span style={{ color: "#94a3b8", display: "block", fontSize: "0.68rem" }}>Shot Number</span>
                        <strong style={{ color: "#f8fafc", fontSize: "0.82rem" }}>Shot #{recordDetail.shot.shot_number}</strong>
                      </div>
                      {recordDetail.shot.camera_motion && (
                        <div style={{ padding: "0.6rem 0.75rem", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: "0.68rem" }}>Camera Motion</span>
                          <strong style={{ color: "#f8fafc", fontSize: "0.82rem" }}>{recordDetail.shot.camera_motion}</strong>
                        </div>
                      )}
                      {recordDetail.shot.transition && (
                        <div style={{ padding: "0.6rem 0.75rem", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: "0.68rem" }}>Transition</span>
                          <strong style={{ color: "#f8fafc", fontSize: "0.82rem" }}>{recordDetail.shot.transition}</strong>
                        </div>
                      )}
                      {(recordDetail.shot.actual_duration || recordDetail.shot.target_duration) && (
                        <div style={{ padding: "0.6rem 0.75rem", borderRadius: "6px", background: "rgba(255, 255, 255, 0.02)", border: "1px solid rgba(255, 255, 255, 0.06)" }}>
                          <span style={{ color: "#94a3b8", display: "block", fontSize: "0.68rem" }}>Duration</span>
                          <strong style={{ color: "#f8fafc", fontSize: "0.82rem" }}>
                            {recordDetail.shot.actual_duration || recordDetail.shot.target_duration}s
                          </strong>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Generated Content Output / Script (if Claude brief or storyboard) */}
                {recordDetail.content_output && (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                      <span
                        style={{
                          fontSize: "0.76rem",
                          fontWeight: 700,
                          color: "#94a3b8",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.35rem",
                        }}
                      >
                        <FileText size={13} style={{ color: "#38bdf8" }} />
                        Generated Creative Script / Storyboard Output
                      </span>
                      <button
                        type="button"
                        className="quick-toggle-btn"
                        style={{ fontSize: "0.7rem", padding: "0.15rem 0.45rem", display: "inline-flex", alignItems: "center", gap: "0.25rem" }}
                        onClick={() => handleCopy(recordDetail.content_output!, "output")}
                      >
                        {copiedKey === "output" ? (
                          <>
                            <Check size={11} style={{ color: "#34d399" }} /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={11} /> Copy Output
                          </>
                        )}
                      </button>
                    </div>
                    <div
                      style={{
                        padding: "0.85rem 1rem",
                        borderRadius: "8px",
                        backgroundColor: "rgba(15, 23, 42, 0.65)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        fontSize: "0.82rem",
                        lineHeight: 1.55,
                        color: "#f1f5f9",
                        whiteSpace: "pre-wrap",
                        maxHeight: "160px",
                        overflowY: "auto",
                      }}
                    >
                      {recordDetail.content_output}
                    </div>
                  </div>
                )}

                {/* 3. Project Campaign Context */}
                {recordDetail.project && (
                  <div
                    style={{
                      padding: "0.75rem 1rem",
                      borderRadius: "8px",
                      background: "rgba(56, 189, 248, 0.05)",
                      border: "1px solid rgba(56, 189, 248, 0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "0.6rem",
                    }}
                  >
                    <div>
                      <span style={{ fontSize: "0.68rem", color: "#38bdf8", textTransform: "uppercase", fontWeight: 700, display: "block" }}>
                        Project Campaign
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc" }}>
                          {recordDetail.project.product_name || "Untitled Film"}
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                          ({recordDetail.project.target_duration || 60}s • {recordDetail.project.aspect_ratio || "16:9"} • {recordDetail.project.stage})
                        </span>
                      </div>
                    </div>
                    {onSelectProject && (
                      <button
                        type="button"
                        className="btn-secondary-studio"
                        style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem", gap: "0.35rem" }}
                        onClick={() => {
                          setSelectedRecordId(null);
                          onSelectProject(recordDetail.project!.id);
                        }}
                      >
                        <ExternalLink size={12} />
                        <span>Open in Creative Studio</span>
                      </button>
                    )}
                  </div>
                )}

                {/* 4. Financial & Accounting Breakdown */}
                <div>
                  <span
                    style={{
                      fontSize: "0.76rem",
                      fontWeight: 700,
                      color: "#94a3b8",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      display: "block",
                      marginBottom: "0.4rem",
                    }}
                  >
                    Financial Accounting Breakdown
                  </span>
                  <div className="admin-kpi-grid">
                    <div className="admin-kpi-card highlight">
                      <span className="kpi-label">Ledger Spend</span>
                      <div className="kpi-value">
                        ${fmtCost(recordDetail.actual_cost != null ? recordDetail.actual_cost : recordDetail.estimated_cost, 5)}
                      </div>
                      <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                        Status: <strong style={{ color: "#38bdf8" }}>{recordDetail.cost_status}</strong> ({recordDetail.currency})
                      </span>
                    </div>

                    <div className="admin-kpi-card">
                      <span className="kpi-label">Consumption Measured</span>
                      <div className="kpi-value" style={{ fontSize: "1.05rem" }}>
                        {recordDetail.billing_unit === "video_seconds"
                          ? `${recordDetail.video_duration_seconds || recordDetail.unit_quantity}s`
                          : `${recordDetail.unit_quantity}`}
                      </div>
                      <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                        {recordDetail.billing_unit === "tokens" && recordDetail.input_tokens != null
                          ? `In: ${recordDetail.input_tokens} / Out: ${recordDetail.output_tokens || 0}`
                          : recordDetail.billing_unit}
                      </span>
                    </div>

                    <div className="admin-kpi-card">
                      <span className="kpi-label">Effective Unit Rate</span>
                      <div className="kpi-value" style={{ fontSize: "1.05rem" }}>
                        ${fmtCost(recordDetail.unit_price, 6)}
                      </div>
                      <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                        per {recordDetail.billing_unit === "video_seconds" ? "second" : "million tokens"}
                      </span>
                    </div>

                    <div className="admin-kpi-card">
                      <span className="kpi-label">Execution Status</span>
                      <div className="kpi-value" style={{ fontSize: "1rem" }}>
                        <span className={`table-status-tag ${recordDetail.request_status === "SUCCESS" ? "success" : "failed"}`}>
                          {recordDetail.request_status}
                        </span>
                      </div>
                      <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                        Origin: {recordDetail.usage_origin}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 5. Technical Identifiers & Reconciliation Action */}
                <div
                  style={{
                    padding: "0.85rem 1rem",
                    borderRadius: "8px",
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                    fontSize: "0.75rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                    <span style={{ fontWeight: 600, color: "#94a3b8" }}>Audit Identifiers & Timestamp</span>
                    {recordDetail.cost_status === "ESTIMATED" && recordDetail.provider_task_id && (
                      <button
                        type="button"
                        className="quick-toggle-btn"
                        style={{ fontSize: "0.72rem", padding: "0.2rem 0.5rem", color: "#10b981", borderColor: "rgba(16, 185, 129, 0.3)" }}
                        onClick={() => {
                          setReconcileTaskId(recordDetail.provider_task_id || "");
                          setReconcileCost(fmtCost(recordDetail.estimated_cost, 4));
                          setSelectedRecordId(null);
                          setReconcileModalOpen(true);
                        }}
                      >
                        <CheckCircle2 size={12} /> Reconcile with Invoice
                      </button>
                    )}
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.5rem" }}>
                    {recordDetail.provider_task_id && (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(0,0,0,0.2)", padding: "0.35rem 0.5rem", borderRadius: "4px" }}>
                        <span style={{ color: "#64748b" }}>Provider Task ID:</span>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                          <code style={{ color: "#38bdf8", fontFamily: "monospace" }}>{recordDetail.provider_task_id}</code>
                          <button
                            type="button"
                            onClick={() => handleCopy(recordDetail.provider_task_id!, "taskId")}
                            style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "2px" }}
                          >
                            {copiedKey === "taskId" ? <Check size={11} style={{ color: "#34d399" }} /> : <Copy size={11} />}
                          </button>
                        </div>
                      </div>
                    )}
                    {recordDetail.provider_request_id && (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(0,0,0,0.2)", padding: "0.35rem 0.5rem", borderRadius: "4px" }}>
                        <span style={{ color: "#64748b" }}>Provider Req ID:</span>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                          <code style={{ color: "#cbd5e1", fontFamily: "monospace" }}>{recordDetail.provider_request_id}</code>
                          <button
                            type="button"
                            onClick={() => handleCopy(recordDetail.provider_request_id!, "reqId")}
                            style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "2px" }}
                          >
                            {copiedKey === "reqId" ? <Check size={11} style={{ color: "#34d399" }} /> : <Copy size={11} />}
                          </button>
                        </div>
                      </div>
                    )}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(0,0,0,0.2)", padding: "0.35rem 0.5rem", borderRadius: "4px" }}>
                      <span style={{ color: "#64748b" }}>Created At:</span>
                      <span style={{ color: "#e2e8f0" }}>{new Date(recordDetail.created_at).toLocaleString()}</span>
                    </div>
                    {recordDetail.completed_at && (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(0,0,0,0.2)", padding: "0.35rem 0.5rem", borderRadius: "4px" }}>
                        <span style={{ color: "#64748b" }}>Completed At:</span>
                        <span style={{ color: "#e2e8f0" }}>{new Date(recordDetail.completed_at).toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {reconcileModalOpen && (
        <div className="modal-backdrop" onClick={() => setReconcileModalOpen(false)}>
          <div className="admin-modal-content" style={{ maxWidth: "500px" }} onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <CheckCircle2 size={18} style={{ color: "#10b981" }} />
                <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc" }}>
                  Reconcile Provider Billing
                </h3>
              </div>
              <button
                type="button"
                className="asset-remove-btn"
                onClick={() => setReconcileModalOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="admin-modal-body">
              <p style={{ fontSize: "0.82rem", color: "#94a3b8", lineHeight: 1.5, margin: "0 0 1rem 0" }}>
                When monthly provider bills or exact ModelArk usage logs arrive, enter the provider Task ID and actual invoice charge to update the ledger.
              </p>

              <div className="form-group-custom">
                <label className="form-label-custom">Provider Task ID</label>
                <input
                  type="text"
                  className="form-input-custom"
                  value={reconcileTaskId}
                  onChange={(e) => setReconcileTaskId(e.target.value)}
                  placeholder="e.g. task_seedance_..."
                />
              </div>

              <div className="form-group-custom">
                <label className="form-label-custom">Actual Invoice Charge (USD)</label>
                <input
                  type="number"
                  step="0.0001"
                  className="form-input-custom"
                  value={reconcileCost}
                  onChange={(e) => setReconcileCost(e.target.value)}
                  placeholder="0.2200"
                />
              </div>

              {reconcileMsg && (
                <div
                  style={{
                    padding: "0.55rem 0.85rem",
                    borderRadius: "6px",
                    fontSize: "0.8rem",
                    backgroundColor: reconcileMsg.isError ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.15)",
                    border: `1px solid ${reconcileMsg.isError ? "rgba(239, 68, 68, 0.3)" : "rgba(16, 185, 129, 0.3)"}`,
                    color: reconcileMsg.isError ? "#f87171" : "#34d399",
                    marginBottom: "1rem",
                  }}
                >
                  {reconcileMsg.text}
                </div>
              )}

              <button
                type="button"
                className="btn-primary-studio"
                style={{ width: "100%", justifyContent: "center" }}
                disabled={reconciling}
                onClick={handlePerformReconciliation}
              >
                {reconciling ? "Reconciling Ledger..." : "Apply Reconciled Billing"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
