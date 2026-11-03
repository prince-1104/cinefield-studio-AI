import { useState, useEffect, type FC, type FormEvent, type ChangeEvent } from "react";
import { ProjectCreate, ProjectDetail, WebsiteAnalysisResult, GeneratedBriefResponse, WebsiteAssetCandidate } from "../types";
import {
  createProject,
  generateScript,
  uploadAssets,
  getVideoModels,
  analyzeWebsite,
  generateCreativeBrief,
  importWebsiteAsset,
  getArtifactUrl,
} from "../api/client";
import {
  FileText,
  ImagePlus,
  Music,
  Sparkles,
  X,
  CheckCircle2,
  Tv,
  Smartphone,
  Layers,
  Clock,
  Clapperboard,
  Globe,
  Wand2,
  RefreshCw,
  Edit3,
  Check,
  Palette,
} from "lucide-react";

interface BriefStepProps {
  onProjectCreated: (project: ProjectDetail) => void;
  onError: (msg: string) => void;
}

const VIDEO_CATEGORIES = [
  "Advertisement",
  "Branding",
  "Product Promotion",
  "Product Launch",
  "Movie",
  "Micro Drama",
  "Music Video",
  "Social Media Video",
  "Corporate Video",
  "Educational Video",
  "Custom",
] as const;

const NARRATION_PREFERENCES = [
  "Dramatic Voiceover",
  "Cinematic Whisper",
  "Energetic Pitch",
  "Calm Documentary",
  "No Narration",
] as const;

export const BriefStep: FC<BriefStepProps> = ({
  onProjectCreated,
  onError,
}) => {
  // Manual & Form Data State
  const [formData, setFormData] = useState<ProjectCreate>({
    product_name: "Pexyl.ai",
    brief: "Where every story becomes a production. An AI-native cinematic engine empowering creators and enterprises to architect micro-dramas, cinema, music videos, and premium commercials with multimodal continuity.",
    audience: "Filmmakers, creative directors, enterprise advertisers, and storytellers demanding cinematic production value",
    tone: "photorealistic, cinematic, premium, dramatic, futuristic",
    cta: "Where Every Story Becomes a Production. Launch on Pexyl.ai",
    target_duration: 60,
    shot_count: 8,
    aspect_ratio: "16:9",
  });

  const [aspectRatio, setAspectRatio] = useState<"16:9" | "9:16">("16:9");
  const [targetDuration, setTargetDuration] = useState<number>(60);
  const [shotCount, setShotCount] = useState<number>(8);

  // Asset States
  const [productImage, setProductImage] = useState<File | null>(null);
  const [productImagePreview, setProductImagePreview] = useState<string | null>(null);

  const [logo, setLogo] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  const [music, setMusic] = useState<File | null>(null);
  const [musicPreview, setMusicPreview] = useState<string | null>(null);

  // AI Creative Director State
  const [creativePrompt, setCreativePrompt] = useState<string>("");
  const [websiteUrl, setWebsiteUrl] = useState<string>("");
  const [videoCategory, setVideoCategory] = useState<string>("Advertisement");
  const [narrationPref, setNarrationPref] = useState<string>("Dramatic Voiceover");

  const [analyzingWebsite, setAnalyzingWebsite] = useState<boolean>(false);
  const [websiteResult, setWebsiteResult] = useState<WebsiteAnalysisResult | null>(null);

  const [generatingBrief, setGeneratingBrief] = useState<boolean>(false);
  const [generatedBrief, setGeneratedBrief] = useState<GeneratedBriefResponse | null>(null);
  const [importingUrl, setImportingUrl] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);

  // Fetch available models dynamically from backend to use configured default model
  useEffect(() => {
    getVideoModels()
      .then((models) => {
        const defaultModel = models.find((m) => m.is_default) || models[0];
        if (defaultModel) {
          setFormData((prev) => ({
            ...prev,
            selected_video_model: defaultModel.id,
            selected_video_provider: defaultModel.provider,
          }));
        }
      })
      .catch((err) => console.warn("Failed to fetch initial video models:", err));
  }, []);

  const tonePresets = [
    "photorealistic, cinematic, premium, dramatic, futuristic",
    "bold, energetic, modern, punchy",
    "minimalist, luxury, sophisticated, calm",
    "dramatic, intense, epic, emotional",
  ];

  const handleSelectDurationPreset = (dur: number) => {
    setTargetDuration(dur);
    if (dur === 15) {
      setShotCount(3);
    } else if (dur === 30) {
      setShotCount(5);
    } else if (dur === 60) {
      setShotCount(8);
    }
  };

  const handleLoadPexylPreset = () => {
    setCreativePrompt("Launch cinematic advertisement for Pexyl.ai — an omni cinema engine turning vague ideas into multi-shot videos.");
    setWebsiteUrl("https://pexyl.ai");
    setVideoCategory("Product Launch");
    setFormData((prev) => ({
      ...prev,
      product_name: "Pexyl.ai",
      brief: "Where every story becomes a production. An AI-native cinematic engine empowering creators and enterprises to architect micro-dramas, cinema, music videos, and premium commercials with multimodal continuity.",
      audience: "Filmmakers, creative directors, enterprise advertisers, and storytellers demanding cinematic production value",
      tone: "photorealistic, cinematic, premium, dramatic, futuristic",
      cta: "Where Every Story Becomes a Production. Launch on Pexyl.ai",
      target_duration: 60,
      shot_count: 8,
      aspect_ratio: "16:9",
    }));
    setTargetDuration(60);
    setShotCount(8);
    setAspectRatio("16:9");
  };

  // 1. Analyze Website Handler
  const handleAnalyzeWebsite = async () => {
    if (!websiteUrl.trim()) {
      onError("Please enter a website URL to analyze (e.g., https://example.com)");
      return;
    }
    setAnalyzingWebsite(true);
    try {
      const res = await analyzeWebsite(websiteUrl.trim());
      setWebsiteResult(res);

      // Auto-suggest product name if currently default or empty
      if (!formData.product_name || formData.product_name === "Pexyl.ai") {
        const brandParts = res.title ? res.title.split(/[-|:]/) : [];
        const brandName = brandParts.length > 0 && brandParts[0] ? brandParts[0].trim() : res.domain;
        if (brandName) {
          setFormData((prev) => ({ ...prev, product_name: brandName }));
        }
      }

      // If user hasn't typed a creative prompt, prefill a smart starter
      if (!creativePrompt.trim()) {
        const starter = `Create a high-impact ${videoCategory.toLowerCase()} for ${res.domain}. Key proposition: ${res.description.slice(0, 150)}...`;
        setCreativePrompt(starter);
      }
    } catch (err: any) {
      console.error("Website analysis failed:", err);
      onError(err.response?.data?.detail || err.message || "Failed to analyze website");
    } finally {
      setAnalyzingWebsite(false);
    }
  };

  // 2. Generate Creative Brief with Claude
  const handleGenerateBriefWithClaude = async () => {
    const promptToUse = creativePrompt.trim() || formData.brief.trim();
    if (!promptToUse && !websiteUrl.trim()) {
      onError("Please enter a creative concept, prompt, or website URL for Claude to analyze.");
      return;
    }

    setGeneratingBrief(true);
    try {
      const briefReq = {
        prompt: promptToUse || `Create a cinematic ${videoCategory.toLowerCase()} for ${formData.product_name}`,
        website_url: websiteUrl.trim() || undefined,
        website_data: websiteResult || undefined,
        video_category: videoCategory,
        target_duration: targetDuration,
        aspect_ratio: aspectRatio,
        creative_style: formData.tone,
        target_audience: formData.audience,
        narration_preference: narrationPref,
        cta: formData.cta,
      };

      const res = await generateCreativeBrief(briefReq);
      setGeneratedBrief(res);

      // Auto-populate all form fields
      setFormData((prev) => ({
        ...prev,
        product_name: res.product_name || prev.product_name,
        brief: res.brief,
        tone: res.tone,
        audience: res.audience,
        cta: res.cta,
        target_duration: res.target_duration,
        shot_count: res.shot_count,
        aspect_ratio: res.aspect_ratio,
      }));

      setTargetDuration(res.target_duration);
      setShotCount(res.shot_count);
      if (res.aspect_ratio === "16:9" || res.aspect_ratio === "9:16") {
        setAspectRatio(res.aspect_ratio);
      }
    } catch (err: any) {
      console.error("Brief generation failed:", err);
      onError(err.response?.data?.detail || err.message || "Failed to generate brief with Claude");
    } finally {
      setGeneratingBrief(false);
    }
  };

  // 3. Import Asset Candidate
  const handleImportAssetCandidate = async (
    candidate: WebsiteAssetCandidate,
    type: "product" | "logo"
  ) => {
    setImportingUrl(candidate.url);
    try {
      const res = await importWebsiteAsset(candidate.url, type);
      const artifactUrl = getArtifactUrl(res.asset_path);

      // Fetch blob and convert to File to integrate with normal multipart pipeline
      const blobRes = await fetch(artifactUrl);
      const blob = await blobRes.blob();
      const file = new File([blob], res.file_name, { type: res.content_type || "image/png" });

      if (type === "product") {
        setProductImage(file);
        setProductImagePreview(artifactUrl);
      } else {
        setLogo(file);
        setLogoPreview(artifactUrl);
      }
    } catch (err: any) {
      console.error("Failed to import asset:", err);
      onError(err.response?.data?.detail || err.message || "Failed to import website asset");
    } finally {
      setImportingUrl(null);
    }
  };

  const handleProductImageChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setProductImage(file);
    if (file) {
      setProductImagePreview(URL.createObjectURL(file));
    } else {
      setProductImagePreview(null);
    }
  };

  const handleLogoChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setLogo(file);
    if (file) {
      setLogoPreview(URL.createObjectURL(file));
    } else {
      setLogoPreview(null);
    }
  };

  const handleMusicChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setMusic(file);
    if (file) {
      setMusicPreview(URL.createObjectURL(file));
    } else {
      setMusicPreview(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      // 1. Create project with campaign parameters, target duration & shot count
      const payload: ProjectCreate = {
        ...formData,
        target_duration: targetDuration,
        shot_count: shotCount,
        aspect_ratio: aspectRatio,
      };

      let project = await createProject(payload);

      // 2. Upload reference assets if supplied
      if (productImage || logo || music) {
        project = await uploadAssets(project.id, {
          productImage,
          logo,
          music,
        });
      }

      // 3. Initiate Gemini / Claude storyboard generation
      await generateScript(project.id);

      onProjectCreated(project);
    } catch (err: any) {
      console.error("Failed to submit brief:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to create campaign"
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="brief-workspace">
      {/* Workspace Header */}
      <div className="workspace-header">
        <div className="workspace-title-row">
          <h1 className="workspace-heading">Create Cinematic Production</h1>
          <button
            type="button"
            className="btn-secondary-studio"
            onClick={handleLoadPexylPreset}
            title="Load calibrated 60s 8-shot Pexyl launch film"
            style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem" }}
          >
            <Sparkles size={14} style={{ color: "#d97706" }} />
            <span>Load Pexyl 60s Launch Campaign</span>
          </button>
        </div>
        <p className="workspace-subheading">
          Enter a prompt or website URL to let Claude automatically architect your creative brief, narrative hook, and storyboard arc.
          Seedance 2.5 and Gemini then synthesize high-fidelity video shots with timeline continuity.
        </p>
      </div>

      {/* =========================================================================
          SECTION 1: AI Creative Director (Claude Powered)
          ========================================================================= */}
      <div className="ai-director-card">
        <div className="ai-director-header">
          <div className="ai-director-title-box">
            <div className="claude-avatar-badge">
              <Sparkles size={18} className="claude-sparkle-icon" />
            </div>
            <div>
              <div className="ai-director-title">
                <span>AI Creative Director</span>
                <span className="claude-powered-tag">Powered by Claude</span>
              </div>
              <div className="ai-director-subtitle">
                Transform vague ideas or website URLs into production-ready creative briefs, visual hooks, and cinematic storyboards.
              </div>
            </div>
          </div>
        </div>

        <div className="ai-director-body">
          {/* 1. Creative Prompt (Large Textarea) */}
          <div className="form-group-custom">
            <label className="form-label-custom" htmlFor="creative_prompt_input">
              <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Wand2 size={13} style={{ color: "#f59e0b" }} />
                <span>Creative Prompt (Concept or Vague Idea)</span>
              </span>
              <span className="form-label-hint">Prompt-to-Video</span>
            </label>
            <textarea
              id="creative_prompt_input"
              rows={3}
              className="form-textarea-custom ai-prompt-textarea"
              value={creativePrompt}
              onChange={(e) => setCreativePrompt(e.target.value)}
              placeholder="e.g. Create a high-energy cinematic launch video for my AI startup. Focus on speed, multimodal continuity, and futuristic dark visuals..."
            />
          </div>

          {/* 2. Website URL & Analyze Button */}
          <div className="form-group-custom">
            <label className="form-label-custom" htmlFor="website_url_input">
              <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <Globe size={13} style={{ color: "#38bdf8" }} />
                <span>Website URL (Website-to-Video Automation)</span>
              </span>
              <span className="form-label-hint">Optional · Auto-extracts brand, copy & assets</span>
            </label>
            <div className="website-analyzer-row">
              <div className="website-input-wrap">
                <Globe size={15} className="website-input-icon" />
                <input
                  id="website_url_input"
                  type="url"
                  className="form-input-custom website-input"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  placeholder="https://example.com or https://pexyl.ai"
                />
              </div>
              <button
                type="button"
                className="btn-analyze-website"
                disabled={analyzingWebsite || !websiteUrl.trim()}
                onClick={handleAnalyzeWebsite}
              >
                {analyzingWebsite ? (
                  <>
                    <div className="pulse-spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Globe size={14} />
                    <span>Analyze Website</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Website Discovered Intelligence Drawer */}
          {websiteResult && (
            <div className="website-intelligence-card">
              <div className="intelligence-header">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <CheckCircle2 size={16} style={{ color: "#10b981" }} />
                  <span style={{ fontWeight: 600, fontSize: "0.85rem", color: "#f1f5f9" }}>
                    Website Analyzed: {websiteResult.domain}
                  </span>
                </div>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>{websiteResult.title}</span>
              </div>

              {/* Detected Brand Colors */}
              {websiteResult.brand_colors && websiteResult.brand_colors.length > 0 && (
                <div className="intelligence-row">
                  <span className="intelligence-label">
                    <Palette size={12} /> Detected Brand Palette:
                  </span>
                  <div className="color-swatches-grid">
                    {websiteResult.brand_colors.map((color, idx) => (
                      <div key={idx} className="color-swatch-badge">
                        <span className="color-dot" style={{ backgroundColor: color }} />
                        <span className="color-hex">{color}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Discovered Media Assets Gallery */}
              {((websiteResult.logo_candidates && websiteResult.logo_candidates.length > 0) ||
                (websiteResult.product_image_candidates && websiteResult.product_image_candidates.length > 0)) && (
                <div className="intelligence-row">
                  <span className="intelligence-label">
                    <Layers size={12} /> Discovered Assets (Click to Adopt into Production Assets):
                  </span>
                  <div className="discovered-assets-grid">
                    {websiteResult.logo_candidates?.slice(0, 3).map((candidate, idx) => (
                      <div key={`logo-${idx}`} className="asset-candidate-card">
                        <div className="candidate-thumb-box logo-checkerboard">
                          <img src={candidate.url} alt="Logo candidate" className="candidate-thumb" />
                        </div>
                        <div className="candidate-info">
                          <span className="candidate-tag">Brand Logo</span>
                          <button
                            type="button"
                            className="candidate-action-btn"
                            disabled={importingUrl === candidate.url}
                            onClick={() => handleImportAssetCandidate(candidate, "logo")}
                          >
                            {importingUrl === candidate.url ? "Importing..." : "Use as Logo"}
                          </button>
                        </div>
                      </div>
                    ))}

                    {websiteResult.product_image_candidates?.slice(0, 4).map((candidate, idx) => (
                      <div key={`product-${idx}`} className="asset-candidate-card">
                        <div className="candidate-thumb-box">
                          <img src={candidate.url} alt="Product candidate" className="candidate-thumb" />
                        </div>
                        <div className="candidate-info">
                          <span className="candidate-tag">Product Asset</span>
                          <button
                            type="button"
                            className="candidate-action-btn"
                            disabled={importingUrl === candidate.url}
                            onClick={() => handleImportAssetCandidate(candidate, "product")}
                          >
                            {importingUrl === candidate.url ? "Importing..." : "Use as Asset"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 3. Video Category Pills */}
          <div className="form-group-custom">
            <label className="form-label-custom">
              <span>Select Video Category</span>
              <span className="form-label-hint">Instructs Claude's creative arc & pacing</span>
            </label>
            <div className="category-pills-wrap">
              {VIDEO_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  className={`category-pill ${videoCategory === cat ? "active" : ""}`}
                  onClick={() => setVideoCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* 4. Quick Production Settings for Claude */}
          <div className="ai-production-settings-grid">
            {/* Target Duration */}
            <div className="form-group-custom" style={{ margin: 0 }}>
              <label className="form-label-custom">
                <Clock size={12} style={{ color: "#8b5cf6" }} />
                <span>Duration</span>
              </label>
              <div className="quick-toggle-group">
                {[15, 30, 60].map((dur) => (
                  <button
                    key={dur}
                    type="button"
                    className={`quick-toggle-btn ${targetDuration === dur ? "active" : ""}`}
                    onClick={() => handleSelectDurationPreset(dur)}
                  >
                    {dur}s
                  </button>
                ))}
              </div>
            </div>

            {/* Aspect Ratio */}
            <div className="form-group-custom" style={{ margin: 0 }}>
              <label className="form-label-custom">
                <span>Aspect Ratio</span>
              </label>
              <div className="quick-toggle-group">
                <button
                  type="button"
                  className={`quick-toggle-btn ${aspectRatio === "16:9" ? "active" : ""}`}
                  onClick={() => setAspectRatio("16:9")}
                >
                  <Tv size={12} /> 16:9 Cinema
                </button>
                <button
                  type="button"
                  className={`quick-toggle-btn ${aspectRatio === "9:16" ? "active" : ""}`}
                  onClick={() => setAspectRatio("9:16")}
                >
                  <Smartphone size={12} /> 9:16 Social
                </button>
              </div>
            </div>

            {/* Narration Preference */}
            <div className="form-group-custom" style={{ margin: 0 }}>
              <label className="form-label-custom">
                <span>Narration Preference</span>
              </label>
              <select
                className="form-input-custom"
                value={narrationPref}
                onChange={(e) => setNarrationPref(e.target.value)}
                style={{ height: "36px", padding: "0.25rem 0.5rem" }}
              >
                {NARRATION_PREFERENCES.map((pref) => (
                  <option key={pref} value={pref}>
                    {pref}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 5. Primary Action: Claude Brief Generation Button */}
          <div className="claude-actions-bar">
            <button
              type="button"
              className="btn-claude-generate"
              disabled={generatingBrief}
              onClick={handleGenerateBriefWithClaude}
            >
              {generatingBrief ? (
                <>
                  <div className="pulse-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                  <span>Claude is Architecting Production Strategy & Visual Arc...</span>
                </>
              ) : (
                <>
                  {generatedBrief ? <RefreshCw size={15} /> : <Sparkles size={16} />}
                  <span>
                    {generatedBrief ? "Regenerate Creative Brief with Claude" : "Generate Creative Brief with Claude"}
                  </span>
                </>
              )}
            </button>

            {generatedBrief && (
              <button
                type="button"
                className="btn-secondary-studio"
                onClick={() => {
                  const element = document.getElementById("detailed-brief-section");
                  element?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                <Edit3 size={14} />
                <span>Edit Brief Details Below</span>
              </button>
            )}
          </div>

          {/* 6. Claude's Generated Creative Direction Card */}
          {generatedBrief && (
            <div className="claude-strategy-card">
              <div className="strategy-card-header">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Sparkles size={15} style={{ color: "#f59e0b" }} />
                  <span className="strategy-title">
                    Claude Creative Strategy · {generatedBrief.video_category}
                  </span>
                </div>
                <span className="strategy-badge">{generatedBrief.provider_used.toUpperCase()}</span>
              </div>

              {generatedBrief.hook && (
                <div className="strategy-block">
                  <span className="strategy-block-title">Visual Hook & Opening Angle:</span>
                  <p className="strategy-block-text">{generatedBrief.hook}</p>
                </div>
              )}

              {generatedBrief.narration_preview && (
                <div className="strategy-block">
                  <span className="strategy-block-title">Narration Script Preview:</span>
                  <p className="strategy-block-text narration-quote">"{generatedBrief.narration_preview}"</p>
                </div>
              )}

              <div className="strategy-meta-grid">
                <div>
                  <span className="strategy-block-title">Audio & Music Direction:</span>
                  <span className="strategy-tag">{generatedBrief.suggested_music_mood}</span>
                </div>
                <div>
                  <span className="strategy-block-title">Timeline Target:</span>
                  <span className="strategy-tag">
                    {generatedBrief.target_duration}s · {generatedBrief.shot_count} Shots · {generatedBrief.aspect_ratio}
                  </span>
                </div>
              </div>

              <div className="strategy-block" style={{ marginTop: "0.75rem" }}>
                <span className="strategy-block-title">Creative Director's Vision:</span>
                <p className="strategy-block-text" style={{ fontSize: "0.8rem", color: "#cbd5e1" }}>
                  {generatedBrief.creative_reasoning}
                </p>
              </div>

              <div className="strategy-success-banner">
                <Check size={14} style={{ color: "#10b981" }} />
                <span>All campaign specifications below have been populated by Claude. Review and generate your storyboard.</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* =========================================================================
          SECTION 2: Detailed Brief & Production Assets (Editable Form)
          ========================================================================= */}
      <form onSubmit={handleSubmit} id="detailed-brief-section">
        <div className="brief-studio-layout">
          {/* Left Column: Creative Brief Panel */}
          <div className="studio-panel">
            <div className="studio-panel-header">
              <div>
                <div className="studio-panel-title">
                  <FileText size={17} style={{ color: "#8b5cf6" }} />
                  <span>Creative Brief & Strategy</span>
                </div>
                <div className="studio-panel-desc">
                  Core specifications that instruct the narrative structure and timeline budget
                </div>
              </div>
            </div>

            <div className="form-stack">
              {/* Duration & Shot Count Presets */}
              <div className="form-group-custom">
                <label className="form-label-custom">
                  <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Clock size={13} style={{ color: "#8b5cf6" }} />
                    <span>Target Production Duration</span>
                  </span>
                  <span className="form-label-hint">{targetDuration}s total · {shotCount} shots</span>
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className={`aspect-option ${targetDuration === 15 ? "active" : ""}`}
                    onClick={() => handleSelectDurationPreset(15)}
                    style={{ padding: "0.6rem 0.75rem", justifyContent: "center", textAlign: "center" }}
                  >
                    <div>
                      <div className="aspect-option-title">15 Seconds</div>
                      <div className="aspect-option-desc">3 Shots (~5s each)</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`aspect-option ${targetDuration === 30 ? "active" : ""}`}
                    onClick={() => handleSelectDurationPreset(30)}
                    style={{ padding: "0.6rem 0.75rem", justifyContent: "center", textAlign: "center" }}
                  >
                    <div>
                      <div className="aspect-option-title">30 Seconds</div>
                      <div className="aspect-option-desc">5 Shots (~6s each)</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`aspect-option ${targetDuration === 60 ? "active" : ""}`}
                    onClick={() => handleSelectDurationPreset(60)}
                    style={{ padding: "0.6rem 0.75rem", justifyContent: "center", textAlign: "center" }}
                  >
                    <div>
                      <div className="aspect-option-title">60 Seconds</div>
                      <div className="aspect-option-desc">8–12 Shots (Cinema)</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Product Name */}
              <div className="form-group-custom">
                <label className="form-label-custom" htmlFor="product_name">
                  <span>Product or Feature Name</span>
                  <span className="form-label-hint">Required</span>
                </label>
                <input
                  id="product_name"
                  type="text"
                  required
                  className="form-input-custom"
                  value={formData.product_name}
                  onChange={(e) =>
                    setFormData({ ...formData, product_name: e.target.value })
                  }
                  placeholder="e.g. Pexyl.ai or Apex Pulse"
                />
              </div>

              {/* Product Brief / Selling Points */}
              <div className="form-group-custom">
                <label className="form-label-custom" htmlFor="brief">
                  <span>Product Brief & Narrative Arc</span>
                  <span className="form-label-hint">Required</span>
                </label>
                <textarea
                  id="brief"
                  required
                  rows={4}
                  className="form-textarea-custom"
                  value={formData.brief}
                  onChange={(e) =>
                    setFormData({ ...formData, brief: e.target.value })
                  }
                  placeholder="Detail the core vision, value proposition, and visual narrative..."
                />
              </div>

              {/* Creative Tone & Presets */}
              <div className="form-group-custom">
                <label className="form-label-custom" htmlFor="tone">
                  <span>Creative Tone & Aesthetic Direction</span>
                  <span className="form-label-hint">Custom or Select Preset</span>
                </label>
                <input
                  id="tone"
                  type="text"
                  required
                  className="form-input-custom"
                  value={formData.tone}
                  onChange={(e) =>
                    setFormData({ ...formData, tone: e.target.value })
                  }
                  placeholder="e.g. photorealistic, cinematic, premium, dramatic, futuristic"
                />
                <div className="tone-chips-grid">
                  {tonePresets.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className={`tone-chip ${formData.tone === preset ? "active" : ""}`}
                      onClick={() => setFormData({ ...formData, tone: preset })}
                    >
                      {(preset.split(",")[0] || "").trim()} Style
                    </button>
                  ))}
                </div>
              </div>

              {/* Target Audience */}
              <div className="form-group-custom">
                <label className="form-label-custom" htmlFor="audience">
                  <span>Target Audience</span>
                  <span className="form-label-hint">Required</span>
                </label>
                <input
                  id="audience"
                  type="text"
                  required
                  className="form-input-custom"
                  value={formData.audience}
                  onChange={(e) =>
                    setFormData({ ...formData, audience: e.target.value })
                  }
                  placeholder="e.g. Creators, enterprise advertisers, filmmakers"
                />
              </div>

              {/* Call to Action */}
              <div className="form-group-custom">
                <label className="form-label-custom" htmlFor="cta">
                  <span>Call to Action (CTA)</span>
                  <span className="form-label-hint">Closing overlay & tagline</span>
                </label>
                <input
                  id="cta"
                  type="text"
                  required
                  className="form-input-custom"
                  value={formData.cta}
                  onChange={(e) =>
                    setFormData({ ...formData, cta: e.target.value })
                  }
                  placeholder="e.g. Where Every Story Becomes a Production. Launch on Pexyl.ai"
                />
              </div>

              {/* Composition & Shot Count Configuration */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div className="form-group-custom">
                  <label className="form-label-custom">
                    <span>Aspect Ratio</span>
                  </label>
                  <div className="aspect-selector" style={{ gridTemplateColumns: "1fr 1fr" }}>
                    <div
                      className={`aspect-option ${aspectRatio === "16:9" ? "active" : ""}`}
                      onClick={() => setAspectRatio("16:9")}
                      style={{ padding: "0.5rem" }}
                    >
                      <div className="aspect-icon-box" style={{ width: "20px", height: "20px" }}>
                        <Tv size={12} />
                      </div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>16:9 Cinema</div>
                    </div>

                    <div
                      className={`aspect-option ${aspectRatio === "9:16" ? "active" : ""}`}
                      onClick={() => setAspectRatio("9:16")}
                      style={{ padding: "0.5rem" }}
                    >
                      <div className="aspect-icon-box" style={{ width: "20px", height: "20px" }}>
                        <Smartphone size={12} />
                      </div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>9:16 Social</div>
                    </div>
                  </div>
                </div>

                <div className="form-group-custom">
                  <label className="form-label-custom" htmlFor="shot_count_input">
                    <span>Planned Shot Count</span>
                  </label>
                  <input
                    id="shot_count_input"
                    type="number"
                    min={1}
                    max={16}
                    className="form-input-custom"
                    value={shotCount}
                    onChange={(e) => setShotCount(Math.max(1, Math.min(16, parseInt(e.target.value) || 1)))}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Reference Assets Studio */}
          <div className="studio-panel">
            <div className="studio-panel-header">
              <div>
                <div className="studio-panel-title">
                  <Layers size={17} style={{ color: "#38bdf8" }} />
                  <span>Production Assets</span>
                </div>
                <div className="studio-panel-desc">
                  Reference files for multimodal visual continuity and audio mixing
                </div>
              </div>
            </div>

            <div className="assets-stack">
              {/* Product Reference Image */}
              <div className="asset-dropzone">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleProductImageChange}
                />
                {!productImage ? (
                  <div className="asset-empty-state">
                    <div className="asset-icon-circle">
                      <ImagePlus size={20} />
                    </div>
                    <div className="asset-meta">
                      <span className="asset-title">Product Visual Reference</span>
                      <span className="asset-hint">
                        Informs AI video models (Seedance & Gemini) for high-fidelity product continuity
                      </span>
                      <div className="asset-tags">
                        <span className="asset-format-tag">JPG / PNG / WEBP</span>
                        <span className="asset-format-tag">Max 10MB</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="asset-filled-state">
                    {productImagePreview && (
                      <img
                        src={productImagePreview}
                        alt="Product preview"
                        className="asset-preview-thumb"
                      />
                    )}
                    <div className="asset-file-details">
                      <div className="asset-filename">{productImage.name}</div>
                      <div className="asset-filesize">
                        <CheckCircle2 size={12} />
                        <span>Ready ({formatFileSize(productImage.size)})</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="asset-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setProductImage(null);
                        setProductImagePreview(null);
                      }}
                      title="Remove image"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>

              {/* Brand Logo Watermark */}
              <div className="asset-dropzone">
                <input
                  type="file"
                  accept="image/png"
                  onChange={handleLogoChange}
                />
                {!logo ? (
                  <div className="asset-empty-state">
                    <div className="asset-icon-circle">
                      <Sparkles size={20} />
                    </div>
                    <div className="asset-meta">
                      <span className="asset-title">Brand Logo Overlay</span>
                      <span className="asset-hint">
                        Watermarked onto the upper corner and closing reveal
                      </span>
                      <div className="asset-tags">
                        <span className="asset-format-tag">PNG with alpha</span>
                        <span className="asset-format-tag">Transparent</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="asset-filled-state">
                    {logoPreview && (
                      <div className="logo-checkerboard" style={{ borderRadius: "6px" }}>
                        <img
                          src={logoPreview}
                          alt="Logo preview"
                          style={{ maxWidth: "40px", maxHeight: "40px", objectFit: "contain" }}
                        />
                      </div>
                    )}
                    <div className="asset-file-details">
                      <div className="asset-filename">{logo.name}</div>
                      <div className="asset-filesize">
                        <CheckCircle2 size={12} />
                        <span>Ready ({formatFileSize(logo.size)})</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="asset-remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setLogo(null);
                        setLogoPreview(null);
                      }}
                      title="Remove logo"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>

              {/* Background Music */}
              <div className="asset-dropzone">
                <input
                  type="file"
                  accept="audio/mp3,audio/wav,audio/mpeg,audio/aac"
                  onChange={handleMusicChange}
                />
                {!music ? (
                  <div className="asset-empty-state">
                    <div className="asset-icon-circle">
                      <Music size={20} />
                    </div>
                    <div className="asset-meta">
                      <span className="asset-title">Background Soundtrack</span>
                      <span className="asset-hint">
                        Ducked dynamically behind the AI voiceover in FFmpeg
                      </span>
                      <div className="asset-tags">
                        <span className="asset-format-tag">MP3 / WAV / AAC</span>
                        <span className="asset-format-tag">Stereo Audio</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ width: "100%" }}>
                    <div className="asset-filled-state">
                      <div className="asset-icon-circle" style={{ width: "38px", height: "38px" }}>
                        <Music size={18} />
                      </div>
                      <div className="asset-file-details">
                        <div className="asset-filename">{music.name}</div>
                        <div className="asset-filesize">
                          <CheckCircle2 size={12} />
                          <span>Ready ({formatFileSize(music.size)})</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="asset-remove-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setMusic(null);
                          setMusicPreview(null);
                        }}
                        title="Remove soundtrack"
                      >
                        <X size={14} />
                      </button>
                    </div>
                    {musicPreview && (
                      <div className="audio-player-preview">
                        <audio controls src={musicPreview} style={{ width: "100%" }} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="studio-action-bar">
          <button
            type="submit"
            className="btn-primary-studio"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <div className="pulse-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                <span>Architecting {targetDuration}s Timeline & {shotCount} Shots...</span>
              </>
            ) : (
              <>
                <Clapperboard size={16} />
                <span>Generate {targetDuration}s ({shotCount}-Shot) Storyboard Arc</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
