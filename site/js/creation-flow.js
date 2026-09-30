/**
 * MythicBee — Interactive Creation Flow
 * Split-panel: form on left, live preview on right
 * Real image upload, template selection, instant customization
 * Audio recording with Cloudflare Whisper + LLM extraction
 */

import { TEMPLATES, autoFillFromBrief } from './templates.js';
import PreviewRenderer from './preview-renderer.js';
import { AudioRecorder } from './audio-recorder.js';

class CreationFlow {
  constructor() {
    this.currentStep = 0;
    this.selectedTemplate = null;
    this.preview = null;
    this.recorder = new AudioRecorder();
    this.formData = {
      recipient: "",
      relationship: "",
      occasion: "",
      description: "",
      tone: "",
      photo: null,
      templateData: {}
    };
    this.panel = null;
  }

  init() {
    // Create the creation panel
    this.panel = document.createElement("div");
    this.panel.id = "creation-panel";
    this.panel.className = "creation-flow";
    this.panel.innerHTML = this.getHTML();
    document.body.appendChild(this.panel);

    // Init preview renderer
    const previewContainer = this.panel.querySelector(".creation-flow__preview");
    this.preview = new PreviewRenderer(previewContainer);

    // Wire events
    this.panel.querySelector(".creation-flow__close").addEventListener("click", () => this.close());
    this.panel.querySelector("[data-action='back']").addEventListener("click", () => this.prevStep());

    // Template selection
    this.panel.querySelectorAll(".template-card").forEach(card => {
      card.addEventListener("click", () => this.selectTemplate(card.dataset.template));
    });

    // Photo upload
    const uploadArea = this.panel.querySelector(".upload-area");
    const fileInput = this.panel.querySelector("#photo-upload");

    uploadArea.addEventListener("click", () => fileInput.click());
    uploadArea.addEventListener("dragover", (e) => { e.preventDefault(); uploadArea.classList.add("dragover"); });
    uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
      this.handlePhotoUpload(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", (e) => this.handlePhotoUpload(e.target.files[0]));

    // Audio recording
    this.setupRecording();

    // Listen for bee events
    document.addEventListener("mythicbee:show-results", () => this.open());

    // Auto-fill from GiftBrief if available
    document.addEventListener("giftbrief:updated", (e) => {
      if (this.selectedTemplate) {
        const filled = autoFillFromBrief(this.selectedTemplate, e.detail);
        Object.entries(filled).forEach(([key, value]) => {
          this.formData.templateData[key] = value;
          this.preview.updateField(key, value);
          const input = this.panel.querySelector(`[data-field="${key}"]`);
          if (input) input.value = value;
        });
      }
    });

    console.log("MythicBee: Creation flow initialized");
  }

  getHTML() {
    const templateCards = Object.values(TEMPLATES).map(t => `
      <div class="template-card" data-template="${t.id}">
        <div class="template-card__preview template-card__preview--${t.layout}"></div>
        <div class="template-card__info">
          <h3 class="template-card__name">${t.name}</h3>
          <p class="template-card__desc">${t.description}</p>
          <span class="template-card__price">From £${t.price}</span>
        </div>
      </div>
    `).join("");

    return `
      <div class="creation-flow__header">
        <h2 class="creation-flow__title">Make something for someone</h2>
        <button class="creation-flow__close" aria-label="Close">&times;</button>
      </div>
      
      <div class="creation-flow__body">
        <!-- Left: Form -->
        <div class="creation-flow__form">
          <!-- Step 0: Template selection -->
          <div class="creation-step active" data-step="0">
            <h3 class="creation-step__title">What should we make?</h3>
            <div class="template-grid">${templateCards}</div>
          </div>

          <!-- Step 1: Recipient info -->
          <div class="creation-step" data-step="1">
            <h3 class="creation-step__title">Who is this for?</h3>
            <div class="form-group">
              <label class="form-label">Their name</label>
              <input type="text" class="form-input" data-field="recipient" placeholder="e.g. Mum, Dad, Sarah...">
            </div>
            <div class="form-group">
              <label class="form-label">They're my</label>
              <select class="form-input" data-field="relationship">
                <option value="">Choose...</option>
                <option value="mum">Mum</option>
                <option value="dad">Dad</option>
                <option value="partner">Partner</option>
                <option value="friend">Friend</option>
                <option value="child">Child</option>
                <option value="grandparent">Grandparent</option>
                <option value="sibling">Sibling</option>
                <option value="pet">Pet</option>
                <option value="other">Someone else</option>
              </select>
            </div>
            <button class="btn btn--primary" data-action="next">Continue</button>
          </div>

          <!-- Step 2: Occasion -->
          <div class="creation-step" data-step="2">
            <h3 class="creation-step__title">What's happening?</h3>
            <div class="chip-group">
              <button class="chip" data-occasion="birthday">Birthday</button>
              <button class="chip" data-occasion="christmas">Christmas</button>
              <button class="chip" data-occasion="anniversary">Anniversary</button>
              <button class="chip" data-occasion="new-home">New home</button>
              <button class="chip" data-occasion="just-because">Just because</button>
              <button class="chip" data-occasion="something-else">Something else</button>
            </div>
            <button class="btn btn--primary" data-action="next">Continue</button>
          </div>

          <!-- Step 3: Tell us about them (Audio Recording) -->
          <div class="creation-step" data-step="3">
            <h3 class="creation-step__title">Tell us about <span class="dynamic-name">them</span></h3>
            
            <!-- Recording UI -->
            <div class="record-section" id="record-section">
              <p class="record-section__hint">Press record and just ramble about them. We'll pull out the good bits.</p>
              
              <!-- Prompt card (flashes during recording) -->
              <div class="prompt-card" id="prompt-card" style="display:none;">
                <span class="prompt-card__label">Think about this:</span>
                <p class="prompt-card__text" id="prompt-text"></p>
              </div>

              <!-- Visualizer + timer -->
              <div class="record-visualizer" id="record-visualizer" style="display:none;">
                <div class="record-visualizer__bars" id="record-bars"></div>
                <span class="record-visualizer__time" id="record-time">0:00</span>
              </div>

              <!-- Record button -->
              <button class="record-btn" id="record-btn" data-action="toggle-record">
                <span class="record-btn__dot"></span>
                <span class="record-btn__label">Hold to record</span>
              </button>

              <!-- Transcript (after recording) -->
              <div class="transcript-box" id="transcript-box" style="display:none;">
                <div class="transcript-box__header">
                  <span class="transcript-box__title">What we heard:</span>
                  <button class="btn btn--ghost btn--sm" data-action="re-record">Re-record</button>
                </div>
                <div class="transcript-box__text" id="transcript-text"></div>
                <button class="btn btn--primary btn--sm" data-action="extract-details">
                  ✨ Extract details
                </button>
              </div>

              <!-- Manual fallback -->
              <details class="manual-entry">
                <summary>Or type it out instead</summary>
                <textarea class="form-input" data-field="description" placeholder="They love gardening, have the driest humour, and once ate an entire cake in one sitting..."></textarea>
              </details>
            </div>

            <!-- Personality chips -->
            <div class="form-group" style="margin-top: 20px;">
              <label class="form-label">What's their vibe?</label>
              <div class="chip-group">
                <button class="chip" data-tone="funny">Funny</button>
                <button class="chip" data-tone="beautiful">Beautiful</button>
                <button class="chip" data-tone="understated">Understated</button>
                <button class="chip" data-tone="sentimental">Sentimental</button>
                <button class="chip" data-tone="ridiculous">A little ridiculous</button>
              </div>
            </div>

            <button class="btn btn--primary" data-action="next">Continue</button>
          </div>

          <!-- Step 4: Photo upload -->
          <div class="creation-step" data-step="4">
            <h3 class="creation-step__title">Add a photo</h3>
            <div class="upload-area" id="photo-drop">
              <input type="file" id="photo-upload" accept="image/*" hidden>
              <div class="upload-area__content">
                <span class="upload-area__icon">+</span>
                <span class="upload-area__text">Drop a photo here or click to browse</span>
                <span class="upload-area__hint">Optional, but it makes it personal</span>
              </div>
              <div class="upload-preview"></div>
            </div>
            <div class="creation-step__actions">
              <button class="btn btn--ghost" data-action="skip-photo">Skip for now</button>
              <button class="btn btn--primary" data-action="next">Continue</button>
            </div>
          </div>

          <!-- Step 5: Customize -->
          <div class="creation-step" data-step="5">
            <h3 class="creation-step__title">Make it yours</h3>
            <p class="creation-step__hint">Click any text in the preview to edit it</p>
            <div class="customize-fields" id="customize-fields"></div>
            <button class="btn btn--primary" data-action="next">Continue</button>
          </div>

          <!-- Step 6: Ready -->
          <div class="creation-step" data-step="6">
            <h3 class="creation-step__title">Ready to make it?</h3>
            <p class="creation-step__summary">
              We'll create a <span class="dynamic-template"></span> for <span class="dynamic-recipient"></span>.
              It'll be ready in about 24 hours.
            </p>
            <div class="creation-step__actions">
              <button class="btn btn--ghost" data-action="back">Make changes</button>
              <button class="btn btn--primary" data-action="add-to-bag">
                Add to bag — £<span class="dynamic-price"></span>
              </button>
            </div>
          </div>
        </div>

        <!-- Right: Live preview -->
        <div class="creation-flow__preview">
          <div class="preview-empty">
            <div class="preview-empty__icon">✦</div>
            <p>Choose a template to see your preview</p>
          </div>
        </div>
      </div>
    `;
  }

  open() {
    this.panel.classList.add("creation-flow--open");
    document.body.style.overflow = "hidden";
    this.goToStep(0);
  }

  close() {
    this.panel.classList.remove("creation-flow--open");
    document.body.style.overflow = "";
  }

  selectTemplate(templateId) {
    this.selectedTemplate = TEMPLATES[templateId];
    this.preview.setTemplate(this.selectedTemplate);

    // Highlight selected
    this.panel.querySelectorAll(".template-card").forEach(c => c.classList.remove("selected"));
    this.panel.querySelector(`[data-template="${templateId}"]`).classList.add("selected");

    // Auto-fill from GiftBrief
    if (window.mythicBee && window.mythicBee.giftBrief) {
      const filled = autoFillFromBrief(this.selectedTemplate, window.mythicBee.giftBrief);
      Object.entries(filled).forEach(([key, value]) => {
        this.formData.templateData[key] = value;
        this.preview.updateField(key, value);
      });
    }

    this.nextStep();
  }

  handlePhotoUpload(file) {
    if (!file || !file.type.startsWith("image/")) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      this.formData.photo = e.target.result;
      this.preview.setPhoto(e.target.result);

      // Show preview in upload area
      const preview = this.panel.querySelector(".upload-preview");
      preview.innerHTML = `<img src="${e.target.result}" alt="Uploaded photo">`;
      this.panel.querySelector(".upload-area__content").style.display = "none";
    };
    reader.readAsDataURL(file);
  }

  // ── Audio Recording ──────────────────────────────────────────────────

  setupRecording() {
    const recordBtn = this.panel.querySelector("#record-btn");
    const visualizer = this.panel.querySelector("#record-visualizer");
    const promptCard = this.panel.querySelector("#prompt-card");
    const promptText = this.panel.querySelector("#prompt-text");
    const transcriptBox = this.panel.querySelector("#transcript-box");
    const transcriptText = this.panel.querySelector("#transcript-text");
    const recordTime = this.panel.querySelector("#record-time");
    const recordBars = this.panel.querySelector("#record-bars");

    // Create visualizer bars
    for (let i = 0; i < 20; i++) {
      const bar = document.createElement("div");
      bar.className = "record-visualizer__bar";
      recordBars.appendChild(bar);
    }

    // Toggle recording on click
    recordBtn.addEventListener("click", async () => {
      if (this.recorder.isRecording) {
        await this.stopRecording();
      } else {
        await this.startRecording();
      }
    });

    // Re-record button
    const reRecordBtn = this.panel.querySelector("[data-action='re-record']");
    if (reRecordBtn) {
      reRecordBtn.addEventListener("click", () => {
        transcriptBox.style.display = "none";
        visualizer.style.display = "none";
        promptCard.style.display = "none";
        recordBtn.style.display = "";
        recordBtn.classList.remove("recording");
        recordBtn.querySelector(".record-btn__label").textContent = "Hold to record";
      });
    }

    // Extract details button
    const extractBtn = this.panel.querySelector("[data-action='extract-details']");
    if (extractBtn) {
      extractBtn.addEventListener("click", () => this.extractDetails());
    }
  }

  async startRecording() {
    const recordBtn = this.panel.querySelector("#record-btn");
    const visualizer = this.panel.querySelector("#record-visualizer");
    const promptCard = this.panel.querySelector("#prompt-card");
    const promptText = this.panel.querySelector("#prompt-text");
    const recordTime = this.panel.querySelector("#record-time");
    const recordBars = this.panel.querySelector("#record-bars");

    const started = await this.recorder.startRecording(
      // onPrompt
      (prompt) => {
        promptText.textContent = prompt;
        promptCard.style.display = "block";
        promptCard.classList.remove("prompt-card--fade");
        void promptCard.offsetWidth; // Trigger reflow
        promptCard.classList.add("prompt-card--fade");
      },
      // onLevel
      (level) => {
        const bars = recordBars.querySelectorAll(".record-visualizer__bar");
        bars.forEach((bar, i) => {
          const height = Math.max(4, level * 40 * (0.5 + Math.random() * 0.5));
          bar.style.height = `${height}px`;
        });
      }
    );

    if (started) {
      recordBtn.classList.add("recording");
      recordBtn.querySelector(".record-btn__label").textContent = "Tap to stop";
      visualizer.style.display = "flex";

      // Update timer
      this._timerInterval = setInterval(() => {
        recordTime.textContent = this.recorder.getElapsedTime();
      }, 500);
    }
  }

  async stopRecording() {
    const recordBtn = this.panel.querySelector("#record-btn");
    const visualizer = this.panel.querySelector("#record-visualizer");
    const promptCard = this.panel.querySelector("#prompt-card");
    const transcriptBox = this.panel.querySelector("#transcript-box");
    const transcriptText = this.panel.querySelector("#transcript-text");

    clearInterval(this._timerInterval);
    recordBtn.classList.remove("recording");
    recordBtn.querySelector(".record-btn__label").textContent = "Processing...";

    const audioBlob = await this.recorder.stopRecording();
    
    if (audioBlob) {
      // Show transcript box
      transcriptText.textContent = "Transcribing with Whisper...";
      transcriptBox.style.display = "block";
      visualizer.style.display = "none";
      promptCard.style.display = "none";
      recordBtn.style.display = "none";

      // Transcribe
      const transcript = await this.recorder.transcribe(audioBlob);
      transcriptText.textContent = transcript;
      this.formData.description = transcript;
    }
  }

  async extractDetails() {
    const extractBtn = this.panel.querySelector("[data-action='extract-details']");
    const transcriptText = this.panel.querySelector("#transcript-text");
    
    extractBtn.disabled = true;
    extractBtn.textContent = "Extracting details...";

    const brief = {
      relationship: this.formData.relationship,
      occasion: this.formData.occasion,
      interests: []
    };

    const extracted = await this.recorder.extractGiftBrief(this.formData.description, brief);
    
    if (extracted) {
      // Merge extracted data into form
      if (extracted.recipient) this.formData.recipient = extracted.recipient;
      if (extracted.relationship) this.formData.relationship = extracted.relationship;
      if (extracted.interests) this.formData.interests = extracted.interests;
      if (extracted.personality) this.formData.personality = extracted.personality;
      if (extracted.memories) this.formData.memories = extracted.memories;
      if (extracted.tone) this.formData.tone = extracted.tone;
      if (extracted.creativeDirection) this.formData.creativeDirection = extracted.creativeDirection;

      // Update preview
      if (this.preview) {
        this.preview.updateField("body", this.formData.description);
      }

      // Show success
      extractBtn.textContent = "✓ Details extracted!";
      extractBtn.classList.add("btn--success");

      // Auto-advance after 1.5s
      setTimeout(() => this.nextStep(), 1500);
    } else {
      extractBtn.disabled = false;
      extractBtn.textContent = "✨ Extract details";
      alert("Couldn't extract details. Please try again or type them manually.");
    }
  }

  goToStep(step) {
    this.currentStep = step;
    this.panel.querySelectorAll(".creation-step").forEach(s => s.classList.remove("active"));
    this.panel.querySelector(`[data-step="${step}"]`).classList.add("active");

    // Show/hide back button
    const backBtn = this.panel.querySelector("[data-action='back']");
    if (backBtn) backBtn.style.display = step > 0 ? "" : "none";

    // Update summary on final step
    if (step === 6) {
      this.updateSummary();
    }
  }

  nextStep() {
    // Save current step data
    this.saveStepData();

    // Validate current step
    if (!this.validateStep()) return;

    if (this.currentStep < 6) {
      this.goToStep(this.currentStep + 1);
    }
  }

  prevStep() {
    if (this.currentStep > 0) {
      this.goToStep(this.currentStep - 1);
    }
  }

  saveStepData() {
    const step = this.panel.querySelector(`[data-step="${this.currentStep}"]`);
    if (!step) return;

    // Save inputs
    step.querySelectorAll("[data-field]").forEach(input => {
      const field = input.dataset.field;
      this.formData[field] = input.value;
      this.preview.updateField(field, input.value);
    });

    // Save chips
    const activeChip = step.querySelector(".chip.active");
    if (activeChip) {
      const occasion = activeChip.dataset.occasion;
      const tone = activeChip.dataset.tone;
      if (occasion) this.formData.occasion = occasion;
      if (tone) this.formData.tone = tone;
    }
  }

  validateStep() {
    switch (this.currentStep) {
      case 0:
        return !!this.selectedTemplate;
      case 1:
        return !!this.formData.recipient;
      default:
        return true;
    }
  }

  updateSummary() {
    const recipient = this.panel.querySelector(".dynamic-recipient");
    const template = this.panel.querySelector(".dynamic-template");
    const price = this.panel.querySelector(".dynamic-price");

    if (recipient) recipient.textContent = this.formData.recipient || "them";
    if (template) template.textContent = this.selectedTemplate?.name || "gift";
    if (price) price.textContent = this.selectedTemplate?.price || 0;
  }
}

// Auto-init
if (typeof window !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    window.creationFlow = new CreationFlow();
    window.creationFlow.init();

    // Wire "Make their gift" buttons
    document.querySelectorAll('[data-action="open-creation"]').forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        window.creationFlow.open();
      });
    });
  });
}

export default CreationFlow;
