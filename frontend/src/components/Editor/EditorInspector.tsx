import { type FC } from "react";
import {
  Sliders,
  Scissors,
  Volume2,
  Trash2,
  Copy,
  ArrowLeft,
  ArrowRight,
  Sparkles,
  Type,
  Music,
  Mic,
} from "lucide-react";
import {
  TimelineClip,
  TimelineOverlay,
  TimelineAudio,
  TimelineCaption,
} from "../../types";

interface EditorInspectorProps {
  selectedClip?: TimelineClip | null;
  selectedOverlay?: TimelineOverlay | null;
  selectedAudio?: TimelineAudio | null;
  selectedCaption?: TimelineCaption | null;
  onUpdateClip: (clip: TimelineClip) => void;
  onUpdateOverlay: (overlay: TimelineOverlay) => void;
  onUpdateAudio: (audio: TimelineAudio) => void;
  onUpdateCaption: (caption: TimelineCaption) => void;
  onDeleteClip: (clipId: string) => void;
  onDuplicateClip: (clipId: string) => void;
  onMoveClip: (clipId: string, direction: "earlier" | "later") => void;
  canMoveEarlier: boolean;
  canMoveLater: boolean;
  canDeleteClip: boolean;
}

export const EditorInspector: FC<EditorInspectorProps> = ({
  selectedClip,
  selectedOverlay,
  selectedAudio,
  selectedCaption,
  onUpdateClip,
  onUpdateOverlay,
  onUpdateAudio,
  onUpdateCaption,
  onDeleteClip,
  onDuplicateClip,
  onMoveClip,
  canMoveEarlier,
  canMoveLater,
  canDeleteClip,
}) => {
  if (!selectedClip && !selectedOverlay && !selectedAudio && !selectedCaption) {
    return (
      <div className="editor-inspector-panel empty">
        <Sliders size={28} style={{ opacity: 0.3, marginBottom: "0.5rem" }} />
        <span className="inspector-empty-title">Inspector & Clip Properties</span>
        <span className="inspector-empty-sub">
          Select a video clip, caption, audio track, or logo on the timeline to edit properties.
        </span>
      </div>
    );
  }

  return (
    <div className="editor-inspector-panel">
      {/* 1. Video Clip Controls */}
      {selectedClip && (
        <div className="inspector-section">
          <div className="inspector-header">
            <span className="inspector-title">Shot #{selectedClip.shot_number} Properties</span>
            <span className="inspector-badge">{selectedClip.duration.toFixed(2)}s</span>
          </div>

          <div className="inspector-body">
            {/* Description */}
            <div className="inspector-field">
              <label className="inspector-label">Scene Description</label>
              <div className="inspector-text-preview">
                {selectedClip.description || "Generated cinema scene"}
              </div>
            </div>

            {/* Source In/Out Trim Controls */}
            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">
                  <Scissors size={12} style={{ display: "inline", marginRight: "4px" }} />
                  Source In / Out Trimming
                </span>
                <span className="inspector-hint">Max {selectedClip.source_duration.toFixed(1)}s</span>
              </div>

              <div className="trim-inputs-grid">
                <div>
                  <span className="trim-sub-label">Trim Start (In)</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max={Math.max(0, selectedClip.source_end - 0.2)}
                    value={selectedClip.source_start}
                    onChange={(e) => {
                      const val = Math.max(0, parseFloat(e.target.value) || 0);
                      onUpdateClip({
                        ...selectedClip,
                        source_start: val,
                      });
                    }}
                    className="form-input-custom trim-input"
                  />
                </div>

                <div>
                  <span className="trim-sub-label">Trim End (Out)</span>
                  <input
                    type="number"
                    step="0.1"
                    min={selectedClip.source_start + 0.2}
                    max={selectedClip.source_duration}
                    value={selectedClip.source_end}
                    onChange={(e) => {
                      const val = Math.min(
                        selectedClip.source_duration,
                        parseFloat(e.target.value) || selectedClip.source_duration
                      );
                      onUpdateClip({
                        ...selectedClip,
                        source_end: val,
                      });
                    }}
                    className="form-input-custom trim-input"
                  />
                </div>
              </div>

              {/* Slider representation */}
              <div style={{ marginTop: "0.6rem" }}>
                <input
                  type="range"
                  min="0.2"
                  max={selectedClip.source_duration}
                  step="0.1"
                  value={selectedClip.source_end - selectedClip.source_start}
                  onChange={(e) => {
                    const newDur = parseFloat(e.target.value) || 0.5;
                    const newEnd = Math.min(
                      selectedClip.source_duration,
                      selectedClip.source_start + newDur
                    );
                    onUpdateClip({
                      ...selectedClip,
                      source_end: newEnd,
                    });
                  }}
                  className="inspector-slider"
                />
              </div>
            </div>

            {/* Transition Intent */}
            <div className="inspector-field">
              <label className="inspector-label">Outgoing Transition</label>
              <select
                value={selectedClip.transition || "Cut"}
                onChange={(e) =>
                  onUpdateClip({
                    ...selectedClip,
                    transition: e.target.value,
                  })
                }
                className="form-input-custom inspector-select"
              >
                <option value="Cut">Cut (Direct Seamless)</option>
                <option value="Dissolve">Dissolve (Soft Crossfade)</option>
                <option value="Fade">Fade to Black</option>
                <option value="Whip Pan">Whip Pan (Kinetic Action)</option>
              </select>
            </div>

            {/* Clip Volume */}
            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">
                  <Volume2 size={12} style={{ display: "inline", marginRight: "4px" }} />
                  Source Audio Volume
                </span>
                <span className="inspector-hint">{Math.round(selectedClip.volume * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                value={selectedClip.volume}
                onChange={(e) =>
                  onUpdateClip({
                    ...selectedClip,
                    volume: parseFloat(e.target.value),
                  })
                }
                className="inspector-slider"
              />
            </div>

            {/* Reorder and Clip Management */}
            <div className="inspector-actions-section">
              <div className="inspector-btn-row">
                <button
                  className="btn-secondary-studio inspector-action-btn"
                  onClick={() => onMoveClip(selectedClip.id, "earlier")}
                  disabled={!canMoveEarlier}
                  title="Move shot earlier in sequence"
                >
                  <ArrowLeft size={13} />
                  <span>Move Left</span>
                </button>
                <button
                  className="btn-secondary-studio inspector-action-btn"
                  onClick={() => onMoveClip(selectedClip.id, "later")}
                  disabled={!canMoveLater}
                  title="Move shot later in sequence"
                >
                  <span>Move Right</span>
                  <ArrowRight size={13} />
                </button>
              </div>

              <div className="inspector-btn-row" style={{ marginTop: "0.5rem" }}>
                <button
                  className="btn-secondary-studio inspector-action-btn"
                  onClick={() => onDuplicateClip(selectedClip.id)}
                  title="Duplicate clip"
                >
                  <Copy size={13} />
                  <span>Duplicate</span>
                </button>

                <button
                  className="btn-secondary-studio inspector-action-btn danger"
                  onClick={() => onDeleteClip(selectedClip.id)}
                  disabled={!canDeleteClip}
                  title={canDeleteClip ? "Remove clip from timeline" : "At least one clip required"}
                >
                  <Trash2 size={13} />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Brand Overlay Controls */}
      {selectedOverlay && (
        <div className="inspector-section">
          <div className="inspector-header">
            <span className="inspector-title">Brand Watermark Overlay</span>
            <Sparkles size={14} style={{ color: "#8b5cf6" }} />
          </div>

          <div className="inspector-body">
            <div className="inspector-field">
              <label className="inspector-label">Screen Position</label>
              <select
                value={selectedOverlay.position}
                onChange={(e: any) =>
                  onUpdateOverlay({
                    ...selectedOverlay,
                    position: e.target.value,
                  })
                }
                className="form-input-custom inspector-select"
              >
                <option value="top_right">Top Right (Standard)</option>
                <option value="top_left">Top Left</option>
                <option value="bottom_right">Bottom Right</option>
                <option value="bottom_left">Bottom Left</option>
                <option value="center">Center (Closing Reveal)</option>
              </select>
            </div>

            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">Overlay Scale</span>
                <span className="inspector-hint">{Math.round(selectedOverlay.scale * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.3"
                max="2.0"
                step="0.05"
                value={selectedOverlay.scale}
                onChange={(e) =>
                  onUpdateOverlay({
                    ...selectedOverlay,
                    scale: parseFloat(e.target.value),
                  })
                }
                className="inspector-slider"
              />
            </div>

            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">Opacity</span>
                <span className="inspector-hint">{Math.round(selectedOverlay.opacity * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={selectedOverlay.opacity}
                onChange={(e) =>
                  onUpdateOverlay({
                    ...selectedOverlay,
                    opacity: parseFloat(e.target.value),
                  })
                }
                className="inspector-slider"
              />
            </div>
          </div>
        </div>
      )}

      {/* 3. Caption / Subtitle Controls */}
      {selectedCaption && (
        <div className="inspector-section">
          <div className="inspector-header">
            <span className="inspector-title">Caption & Title Text</span>
            <Type size={14} style={{ color: "#eab308" }} />
          </div>

          <div className="inspector-body">
            <div className="inspector-field">
              <label className="inspector-label">Subtitle Text</label>
              <textarea
                rows={3}
                value={selectedCaption.text}
                onChange={(e) =>
                  onUpdateCaption({
                    ...selectedCaption,
                    text: e.target.value,
                  })
                }
                className="form-textarea-custom"
                style={{ fontSize: "0.85rem" }}
              />
            </div>

            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">Font Size</span>
                <span className="inspector-hint">{selectedCaption.font_size}px</span>
              </div>
              <input
                type="range"
                min="18"
                max="54"
                step="2"
                value={selectedCaption.font_size}
                onChange={(e) =>
                  onUpdateCaption({
                    ...selectedCaption,
                    font_size: parseInt(e.target.value),
                  })
                }
                className="inspector-slider"
              />
            </div>

            <div className="inspector-field">
              <label className="inspector-label">Text Color</label>
              <select
                value={selectedCaption.font_color}
                onChange={(e) =>
                  onUpdateCaption({
                    ...selectedCaption,
                    font_color: e.target.value,
                  })
                }
                className="form-input-custom inspector-select"
              >
                <option value="#ffffff">Pure White (#ffffff)</option>
                <option value="#fde047">Cinematic Gold (#fde047)</option>
                <option value="#38bdf8">Electric Cyan (#38bdf8)</option>
                <option value="#c084fc">Violet Accent (#c084fc)</option>
              </select>
            </div>

            <div className="inspector-field">
              <label className="inspector-label">Screen Placement</label>
              <select
                value={selectedCaption.position}
                onChange={(e: any) =>
                  onUpdateCaption({
                    ...selectedCaption,
                    position: e.target.value,
                  })
                }
                className="form-input-custom inspector-select"
              >
                <option value="bottom">Bottom (Standard Subtitles)</option>
                <option value="center">Center (Hero Title Card)</option>
                <option value="top">Top (Headliner Banner)</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* 4. Audio Controls */}
      {selectedAudio && (
        <div className="inspector-section">
          <div className="inspector-header">
            <span className="inspector-title">
              {selectedAudio.track_type === "narration" ? "Voiceover Narration" : "Soundtrack Audio"}
            </span>
            {selectedAudio.track_type === "narration" ? (
              <Mic size={14} style={{ color: "#38bdf8" }} />
            ) : (
              <Music size={14} style={{ color: "#a855f7" }} />
            )}
          </div>

          <div className="inspector-body">
            <div className="inspector-field">
              <div className="inspector-label-row">
                <span className="inspector-label">Master Gain (Volume)</span>
                <span className="inspector-hint">{Math.round(selectedAudio.volume * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max={selectedAudio.track_type === "narration" ? "2.0" : "1.0"}
                step="0.05"
                value={selectedAudio.volume}
                onChange={(e) =>
                  onUpdateAudio({
                    ...selectedAudio,
                    volume: parseFloat(e.target.value),
                  })
                }
                className="inspector-slider"
              />
            </div>

            {selectedAudio.track_type === "music" && (
              <>
                <div className="inspector-field">
                  <div className="inspector-label-row">
                    <span className="inspector-label">Fade In Duration</span>
                    <span className="inspector-hint">{selectedAudio.fade_in || 0}s</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="0.2"
                    value={selectedAudio.fade_in || 0}
                    onChange={(e) =>
                      onUpdateAudio({
                        ...selectedAudio,
                        fade_in: parseFloat(e.target.value),
                      })
                    }
                    className="inspector-slider"
                  />
                </div>

                <div className="inspector-field">
                  <div className="inspector-label-row">
                    <span className="inspector-label">Fade Out Duration</span>
                    <span className="inspector-hint">{selectedAudio.fade_out || 0}s</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="0.2"
                    value={selectedAudio.fade_out || 0}
                    onChange={(e) =>
                      onUpdateAudio({
                        ...selectedAudio,
                        fade_out: parseFloat(e.target.value),
                      })
                    }
                    className="inspector-slider"
                  />
                </div>

                <div className="inspector-field">
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={selectedAudio.ducking ?? true}
                      onChange={(e) =>
                        onUpdateAudio({
                          ...selectedAudio,
                          ducking: e.target.checked,
                        })
                      }
                    />
                    <span style={{ fontSize: "0.82rem", color: "#cbd5e1" }}>
                      Auto-duck behind voiceover in FFmpeg
                    </span>
                  </label>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
