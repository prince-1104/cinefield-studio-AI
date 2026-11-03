import { useState, useEffect, type FC } from "react";
import {
  OverviewMetrics,
  ProviderMetric,
  ModelMetric,
  ProjectCostMetric,
  ProjectDetailMetrics,
  AIUsageRecord,
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
} from "lucide-react";

interface AdminDashboardProps {
  onBackToStudio: () => void;
}

export const AdminDashboard: FC<AdminDashboardProps> = ({ onBackToStudio }) => {
  // Authentication State
  const [adminKey, setAdminKey] = useState<string>(
    localStorage.getItem("pexyl_admin_key") || "pexyl-admin-secret-2026"
  );
  const [authInput, setAuthInput] = useState<string>(adminKey);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Date Filter State
  const [rangePreset, setRangePreset] = useState<string>("30d");

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
        getAdminOverview(rangePreset, undefined, undefined, adminKey),
        getAdminProviders(rangePreset, undefined, undefined, adminKey),
        getAdminModels(rangePreset, undefined, undefined, adminKey),
        getAdminProjects(rangePreset, undefined, undefined, adminKey),
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
  }, [rangePreset, adminKey]);

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

        {/* Date Filter & CSV Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
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
                <div className="kpi-value">${overview.total_spend.toFixed(4)}</div>
                <div className="kpi-breakdown">
                  <span>Actual: <strong>${overview.actual_spend.toFixed(4)}</strong></span>
                  <span>Est: <strong>${overview.estimated_spend.toFixed(4)}</strong></span>
                  {overview.unknown_spend > 0 && (
                    <span style={{ color: "#f59e0b" }}>Unreconciled: ${overview.unknown_spend.toFixed(4)}</span>
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
                  {(overview.total_tokens / 1000).toFixed(1)}k
                </div>
                <div className="kpi-breakdown">
                  <span>In: <strong>{(overview.total_input_tokens / 1000).toFixed(1)}k</strong></span>
                  <span>Out: <strong>{(overview.total_output_tokens / 1000).toFixed(1)}k</strong></span>
                </div>
              </div>

              {/* Video Generations */}
              <div className="admin-kpi-card">
                <div className="kpi-header">
                  <span className="kpi-label">Seedance Video Generations</span>
                  <Film size={16} style={{ color: "#8b5cf6" }} />
                </div>
                <div className="kpi-value">{overview.total_video_generations} Clips</div>
                <div className="kpi-breakdown">
                  <span style={{ color: "#34d399" }}>✓ {overview.successful_generations} Done</span>
                  {overview.failed_generations > 0 && (
                    <span style={{ color: "#f87171" }}>✕ {overview.failed_generations} Failed</span>
                  )}
                  <span>{overview.total_video_seconds.toFixed(0)}s Total</span>
                </div>
              </div>

              {/* AI Projects */}
              <div className="admin-kpi-card">
                <div className="kpi-header">
                  <span className="kpi-label">Active AI Projects</span>
                  <Layers size={16} style={{ color: "#10b981" }} />
                </div>
                <div className="kpi-value">{overview.total_projects_using_ai}</div>
                <div className="kpi-breakdown">
                  <span>{overview.total_requests} Total API Calls Logged</span>
                </div>
              </div>
            </div>
          )}

          {/* =====================================================================
              2. Provider Analytics Grid
              ===================================================================== */}
          <div className="admin-section">
            <h2 className="admin-section-heading">Provider Spend Breakdown</h2>
            <div className="admin-cards-grid">
              {providers.map((p) => (
                <div key={p.provider} className="provider-summary-card">
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                    <span className="provider-title">{p.provider.toUpperCase()}</span>
                    <span className="provider-cost-badge">${p.total_cost.toFixed(4)}</span>
                  </div>
                  <div className="provider-metric-row">
                    <span>Total API Requests:</span>
                    <strong>{p.request_count}</strong>
                  </div>
                  {p.provider === "claude" && (
                    <div className="provider-metric-row">
                      <span>Tokens Processed:</span>
                      <strong>{((p.input_tokens + p.output_tokens) / 1000).toFixed(1)}k</strong>
                    </div>
                  )}
                  {p.provider === "seedance" && (
                    <div className="provider-metric-row">
                      <span>Videos Generated:</span>
                      <strong>{p.video_generation_count} clips</strong>
                    </div>
                  )}
                  <div className="provider-metric-row">
                    <span>Failure Rate:</span>
                    <strong style={{ color: p.failure_rate > 0 ? "#f87171" : "#34d399" }}>
                      {p.failure_rate}%
                    </strong>
                  </div>
                </div>
              ))}
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
                  {models.map((m) => (
                    <tr key={`${m.provider}-${m.model}`}>
                      <td>
                        <span className="table-provider-pill">{m.provider}</span>
                      </td>
                      <td style={{ fontWeight: 600, color: "#f8fafc" }}>{m.model}</td>
                      <td>{m.total_requests}</td>
                      <td>
                        {m.video_generation_count > 0
                          ? `${m.video_generation_count} videos`
                          : `${((m.input_tokens + m.output_tokens) / 1000).toFixed(1)}k tokens`}
                      </td>
                      <td style={{ color: "#34d399" }}>${m.actual_cost.toFixed(4)}</td>
                      <td style={{ color: "#94a3b8" }}>${m.estimated_cost.toFixed(4)}</td>
                      <td style={{ fontWeight: 700, color: "#38bdf8" }}>${m.total_cost.toFixed(4)}</td>
                      <td>${m.avg_cost_per_request.toFixed(4)}</td>
                      <td>
                        <span
                          className={`table-status-tag ${m.failure_rate > 0 ? "failed" : "success"}`}
                        >
                          {m.failure_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                  {models.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No model usage recorded for this timeframe.
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
                  {projects.map((proj) => (
                    <tr key={proj.project_id}>
                      <td style={{ fontWeight: 600, color: "#f8fafc" }}>
                        <div>{proj.project_name}</div>
                        <span style={{ fontSize: "0.68rem", color: "#64748b", fontFamily: "monospace" }}>
                          {proj.project_id.slice(0, 8)}...
                        </span>
                      </td>
                      <td>{proj.owner}</td>
                      <td>{proj.total_requests}</td>
                      <td>
                        {((proj.claude_input_tokens + proj.claude_output_tokens) / 1000).toFixed(1)}k
                      </td>
                      <td>
                        {proj.video_generation_count} ({proj.successful_videos} ok / {proj.failed_videos} fail)
                      </td>
                      <td style={{ color: "#34d399" }}>${proj.actual_spend.toFixed(4)}</td>
                      <td style={{ color: "#94a3b8" }}>${proj.estimated_spend.toFixed(4)}</td>
                      <td style={{ fontWeight: 700, color: "#38bdf8" }}>${proj.total_spend.toFixed(4)}</td>
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
                  {projects.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No projects have recorded AI spend in this timeframe.
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
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Operation</th>
                    <th>Units Consumed</th>
                    <th>Status</th>
                    <th>Cost Type</th>
                    <th>Cost (USD)</th>
                    <th>Task / Request ID</th>
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
                    <tr key={item.id}>
                      <td style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td>
                        <span className="table-provider-pill">{item.provider}</span>
                      </td>
                      <td style={{ fontSize: "0.78rem", fontWeight: 600, color: "#f1f5f9" }}>
                        {item.model}
                      </td>
                      <td style={{ fontSize: "0.75rem", color: "#cbd5e1" }}>{item.operation}</td>
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
                        ${(item.actual_cost != null ? item.actual_cost : item.estimated_cost).toFixed(5)}
                      </td>
                      <td style={{ fontSize: "0.7rem", fontFamily: "monospace", color: "#64748b" }}>
                        {item.provider_task_id || item.provider_request_id || "—"}
                      </td>
                    </tr>
                  ))}
                  {ledgerItems.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: "center", color: "#64748b", padding: "2rem" }}>
                        No records match the current filters.
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
                    <div className="kpi-value">${projectDetail.total_spend.toFixed(4)}</div>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Claude Creative Planning</span>
                    <div className="kpi-value">${projectDetail.claude_spend.toFixed(4)}</div>
                    <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                      {projectDetail.claude_tokens.total} Tokens
                    </span>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Seedance Video Synthesis</span>
                    <div className="kpi-value">${projectDetail.seedance_spend.toFixed(4)}</div>
                    <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                      {projectDetail.video_generations_count} Video Clips
                    </span>
                  </div>
                  <div className="admin-kpi-card">
                    <span className="kpi-label">Avg Cost / Finished Shot</span>
                    <div className="kpi-value">${projectDetail.cost_per_shot.toFixed(4)}</div>
                  </div>
                </div>

                {/* Per-Shot Cost Breakdown */}
                <h4 style={{ fontSize: "0.88rem", color: "#e2e8f0", marginBottom: "0.6rem" }}>
                  Shot-by-Shot AI Cost Allocation
                </h4>
                <div className="shot-cost-grid">
                  {Object.entries(projectDetail.shot_costs).map(([shotId, cost], idx) => (
                    <div key={shotId} className="shot-cost-pill">
                      <span>Shot #{idx + 1}:</span>
                      <strong>${cost.toFixed(4)}</strong>
                    </div>
                  ))}
                  {Object.keys(projectDetail.shot_costs).length === 0 && (
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
