import { useState, type FC, type FormEvent } from "react";
import { ProjectCreate, ProjectDetail } from "../types";
import { createProject, generateScript, uploadAssets } from "../api/client";

interface BriefStepProps {
  onProjectCreated: (project: ProjectDetail) => void;
  onError: (msg: string) => void;
}

export const BriefStep: FC<BriefStepProps> = ({
  onProjectCreated,
  onError,
}) => {
  const [formData, setFormData] = useState<ProjectCreate>({
    product_name: "Apex Pulse",
    brief: "Sleek wireless carbon-fiber noise-cancelling headphones crafted for producers and travelers.",
    audience: "Creative professionals, travelers, and audiophiles who demand studio-grade acoustics",
    tone: "cinematic, high-tech, confident, inspiring",
    cta: "Experience Pure Sound. Pre-Order Apex Pulse Today.",
  });

  const [productImage, setProductImage] = useState<File | null>(null);
  const [logo, setLogo] = useState<File | null>(null);
  const [music, setMusic] = useState<File | null>(null);

  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      // 1. Create project
      let project = await createProject(formData);

      // 2. Upload assets if provided
      if (productImage || logo || music) {
        project = await uploadAssets(project.id, {
          productImage,
          logo,
          music,
        });
      }

      // 3. Trigger script planning job
      await generateScript(project.id);

      onProjectCreated(project);
    } catch (err: any) {
      console.error("Failed to submit brief:", err);
      onError(
        err.response?.data?.detail || err.message || "Failed to create project"
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <h2 className="card-title">1. Campaign Brief & Brand Assets</h2>
      <p className="card-subtitle">
        Enter your product specifications and creative direction. The Gemini AI
        planner will craft an optimal 3-shot storyboard narrative.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="product_name">Product / Feature Name *</label>
            <input
              id="product_name"
              type="text"
              required
              value={formData.product_name}
              onChange={(e) =>
                setFormData({ ...formData, product_name: e.target.value })
              }
              placeholder="e.g. Apex Pulse Headphones"
            />
          </div>

          <div className="form-group">
            <label htmlFor="tone">Creative Tone *</label>
            <input
              id="tone"
              type="text"
              required
              value={formData.tone}
              onChange={(e) =>
                setFormData({ ...formData, tone: e.target.value })
              }
              placeholder="e.g. cinematic, dramatic, futuristic, energetic"
            />
          </div>

          <div className="form-group full-width">
            <label htmlFor="brief">Product Brief & Key Selling Points *</label>
            <textarea
              id="brief"
              required
              value={formData.brief}
              onChange={(e) =>
                setFormData({ ...formData, brief: e.target.value })
              }
              placeholder="Describe what the product is, its primary benefit, and visual appeal..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="audience">Target Audience *</label>
            <input
              id="audience"
              type="text"
              required
              value={formData.audience}
              onChange={(e) =>
                setFormData({ ...formData, audience: e.target.value })
              }
              placeholder="e.g. Urban commuters, gamers, high-performance athletes"
            />
          </div>

          <div className="form-group">
            <label htmlFor="cta">Call to Action (CTA) *</label>
            <input
              id="cta"
              type="text"
              required
              value={formData.cta}
              onChange={(e) =>
                setFormData({ ...formData, cta: e.target.value })
              }
              placeholder="e.g. Order Now at ApexPulse.com"
            />
          </div>
        </div>

        {/* Brand & Reference Asset Uploads */}
        <h3
          className="card-title"
          style={{ marginTop: "1.75rem", fontSize: "1.05rem" }}
        >
          Reference Assets (Optional)
        </h3>
        <p className="card-subtitle">
          Add a product reference image for multimodal visual fidelity, logo watermark, and background music.
        </p>

        <div className="upload-grid">
          <div className="upload-box">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setProductImage(e.target.files?.[0] || null)}
            />
            <div className="upload-icon">📷</div>
            <div className="upload-title">Product Image</div>
            <div className="upload-desc">JPG/PNG reference for Gemini video continuity</div>
            {productImage && (
              <div className="upload-filename">✓ {productImage.name}</div>
            )}
          </div>

          <div className="upload-box">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setLogo(e.target.files?.[0] || null)}
            />
            <div className="upload-icon">🏷️</div>
            <div className="upload-title">Brand Logo</div>
            <div className="upload-desc">PNG transparent watermark overlay</div>
            {logo && <div className="upload-filename">✓ {logo.name}</div>}
          </div>

          <div className="upload-box">
            <input
              type="file"
              accept="audio/*"
              onChange={(e) => setMusic(e.target.files?.[0] || null)}
            />
            <div className="upload-icon">🎵</div>
            <div className="upload-title">Background Music</div>
            <div className="upload-desc">MP3 soundtrack to mix behind narration</div>
            {music && <div className="upload-filename">✓ {music.name}</div>}
          </div>
        </div>

        <div style={{ marginTop: "2rem", display: "flex", justifyContent: "flex-end" }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
          >
            {submitting ? "Analyzing & Planning Storyboard..." : "Generate 3-Shot Storyboard ➔"}
          </button>
        </div>
      </form>
    </div>
  );
};
