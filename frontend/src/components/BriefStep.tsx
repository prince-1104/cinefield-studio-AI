import { useState, type FC, type FormEvent, type ChangeEvent } from "react";
import { ProjectCreate, ProjectDetail } from "../types";
import { createProject, generateScript, uploadAssets } from "../api/client";
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
} from "lucide-react";

interface BriefStepProps {
  onProjectCreated: (project: ProjectDetail) => void;
  onError: (msg: string) => void;
}

export const BriefStep: FC<BriefStepProps> = ({
  onProjectCreated,
  onError,
}) => {
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

  const [productImage, setProductImage] = useState<File | null>(null);
  const [productImagePreview, setProductImagePreview] = useState<string | null>(null);

  const [logo, setLogo] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  const [music, setMusic] = useState<File | null>(null);
  const [musicPreview, setMusicPreview] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);

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
    setFormData({
      product_name: "Pexyl.ai",
      brief: "Where every story becomes a production. An AI-native cinematic engine empowering creators and enterprises to architect micro-dramas, cinema, music videos, and premium commercials with multimodal continuity.",
      audience: "Filmmakers, creative directors, enterprise advertisers, and storytellers demanding cinematic production value",
      tone: "photorealistic, cinematic, premium, dramatic, futuristic",
      cta: "Where Every Story Becomes a Production. Launch on Pexyl.ai",
      target_duration: 60,
      shot_count: 8,
      aspect_ratio: "16:9",
    });
    setTargetDuration(60);
    setShotCount(8);
    setAspectRatio("16:9");
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

      // 3. Initiate Gemini storyboard generation
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
            <Sparkles size={14} style={{ color: "#8b5cf6" }} />
            <span>Load Pexyl 60s Launch Campaign</span>
          </button>
        </div>
        <p className="workspace-subheading">
          Define your campaign narrative, target duration (15s, 30s, or 60s), and production assets.
          Gemini Omni Flash will architect and synthesize a multi-shot cinematic arc with timeline continuity.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
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
                  rows={3}
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
                        Informs Gemini Omni Flash for high-fidelity product continuity
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
