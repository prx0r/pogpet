/**
 * MythicBee Character Controller — Bartholomew III
 * Uses pose sprites + Motion.js for animation
 * Adapted from BartholomewController.ts for static HTML/JS
 */

class MythicBeeController {
  constructor() {
    this.state = "idle";
    this.sprite = null;
    this.root = null;
    this.chatOpen = false;
    this.idleAnimation = null;
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.home = { left: 0, top: 0 };
    this.homeMargin = 24;
  }

  async init() {
    // Create the character DOM
    this.root = document.createElement("div");
    this.root.id = "bartholomew";
    this.root.setAttribute("aria-label", "Bartholomew the MythicBee");
    this.root.setAttribute("role", "button");
    this.root.setAttribute("tabindex", "0");
    this.root.style.cssText = `
      position: fixed;
      z-index: 2147483601;
      cursor: pointer;
      width: 160px;
      height: 160px;
      image-rendering: auto;
      filter: drop-shadow(0 5px 12px rgba(0,0,0,0.4));
      transition: filter 0.3s;
    `;

    // Create sprite image
    this.sprite = document.createElement("img");
    this.sprite.src = "assets/poses/01_neutral.webp";
    this.sprite.alt = "Bartholomew";
    this.sprite.style.cssText = "width: 100%; height: 100%; object-fit: contain;";
    this.root.appendChild(this.sprite);

    // Add to page
    document.body.appendChild(this.root);

    // Pin home position
    this.pinHome();

    // Click handler
    this.root.addEventListener("click", (e) => {
      e.stopPropagation();
      this.onBeeClick();
    });

    // Start idle animation
    this.setState("idle");

    console.log("MythicBee: Bartholomew III is alive");
  }

  // ── Position ────────────────────────────────────────────────────────

  pinHome() {
    const w = 160;
    const h = 160;
    this.home = {
      left: Math.max(this.homeMargin, window.innerWidth - w - this.homeMargin),
      top: Math.max(this.homeMargin, window.innerHeight - h - this.homeMargin)
    };
    this.root.style.left = `${this.home.left}px`;
    this.root.style.top = `${this.home.top}px`;
  }

  // ── State Machine ───────────────────────────────────────────────────

  async setState(state) {
    this.state = state;

    // Stop any running animation
    if (this.idleAnimation && this.idleAnimation.stop) {
      this.idleAnimation.stop();
    }
    this.idleAnimation = null;

    // Map state to expression/pose
    const expressionMap = {
      idle: "neutral",
      listening: "listening",
      thinking: "thinking",
      speaking: "talking",
      flying: "confident",
      presenting: "presenting",
      celebrating: "celebrate",
      sleeping: "sleeping"
    };

    this.setExpression(expressionMap[state] || "neutral");

    // Animate with Motion.js if available
    if (this.reducedMotion || typeof animate === "undefined") return;

    const { animate: motionAnimate } = await import("https://cdn.jsdelivr.net/npm/motion@latest/+esm");

    switch (state) {
      case "idle":
        this.idleAnimation = motionAnimate(this.sprite,
          { y: [0, -8, 0], rotate: [-1.2, 1.2, -1.2] },
          { duration: 2.7, repeat: Infinity, ease: "easeInOut" });
        break;
      case "listening":
        this.idleAnimation = motionAnimate(this.sprite,
          { y: [0, -4, 0], scale: [1, 1.025, 1] },
          { duration: 1.15, repeat: Infinity, ease: "easeInOut" });
        break;
      case "thinking":
        this.idleAnimation = motionAnimate(this.sprite,
          { rotate: [0, -4, 3, 0], y: [0, -5, 0] },
          { duration: 1.7, repeat: Infinity, ease: "easeInOut" });
        break;
      case "speaking":
        this.idleAnimation = motionAnimate(this.sprite,
          { y: [0, -3, 0], rotate: [0, 0.8, 0] },
          { duration: 0.55, repeat: Infinity, ease: "easeInOut" });
        break;
      case "sleeping":
        this.idleAnimation = motionAnimate(this.sprite,
          { y: [0, 2, 0], scale: [1, 0.985, 1] },
          { duration: 2.8, repeat: Infinity, ease: "easeInOut" });
        break;
    }
  }

  setExpression(expression) {
    this.root.dataset.expression = expression;
    const poseMap = {
      neutral: "assets/poses/01_neutral.webp",
      happy: "assets/poses/02_happy.webp",
      wink: "assets/poses/03_wink.webp",
      listening: "assets/poses/04_listening.webp",
      thinking: "assets/poses/05_thinking.webp",
      surprised: "assets/poses/06_surprised.webp",
      confident: "assets/poses/07_confident.webp",
      talking: "assets/poses/08_talking.webp",
      presenting: "assets/poses/09_presenting.webp",
      celebrate: "assets/poses/11_celebrate_arms.webp",
      sleeping: "assets/poses/12_sleeping.webp"
    };
    if (poseMap[expression]) {
      this.sprite.src = poseMap[expression];
    }
  }

  // ── Audio Reactive ──────────────────────────────────────────────────

  onAudioLevel(level) {
    if (this.state !== "speaking" || this.reducedMotion) return;
    if (typeof animate === "undefined") return;
    const v = Math.max(0, Math.min(1, level));
    animate(this.sprite,
      { scaleX: 1 + v * 0.012, scaleY: 1 + v * 0.035 },
      { duration: 0.075, ease: "linear" });
  }

  // ── Movement ────────────────────────────────────────────────────────

  async flyTo(element, side = "right") {
    await this.setState("flying");
    const target = element.getBoundingClientRect();
    const self = this.root.getBoundingClientRect();
    const gap = 16;
    let left = target.right + gap;
    let top = target.top + target.height / 2 - self.height / 2;
    if (side === "left") left = target.left - self.width - gap;
    if (side === "above") { left = target.left + target.width / 2 - self.width / 2; top = target.top - self.height - gap; }
    if (side === "below") { left = target.left + target.width / 2 - self.width / 2; top = target.bottom + gap; }
    left = Math.max(8, Math.min(window.innerWidth - self.width - 8, left));
    top = Math.max(8, Math.min(window.innerHeight - self.height - 8, top));

    if (this.reducedMotion || typeof animate === "undefined") {
      this.root.style.left = `${left}px`;
      this.root.style.top = `${top}px`;
    } else {
      const { animate: motionAnimate } = await import("https://cdn.jsdelivr.net/npm/motion@latest/+esm");
      await motionAnimate(this.root,
        { left: `${left}px`, top: `${top}px`, rotate: [0, -7, 4, 0], scale: [1, 0.92, 1.02, 1] },
        { duration: 0.82, ease: [0.22, 1, 0.36, 1] });
    }
    await this.setState("presenting");
  }

  async returnHome() {
    if (this.reducedMotion || typeof animate === "undefined") {
      this.root.style.left = `${this.home.left}px`;
      this.root.style.top = `${this.home.top}px`;
    } else {
      const { animate: motionAnimate } = await import("https://cdn.jsdelivr.net/npm/motion@latest/+esm");
      await motionAnimate(this.root,
        { left: `${this.home.left}px`, top: `${this.home.top}px`, rotate: [0, 5, 0] },
        { duration: 0.75, ease: "easeInOut" });
    }
    await this.setState("idle");
  }

  async celebrate() {
    await this.setState("celebrating");
    if (!this.reducedMotion && typeof animate !== "undefined") {
      const { animate: motionAnimate } = await import("https://cdn.jsdelivr.net/npm/motion@latest/+esm");
      await motionAnimate(this.root,
        { y: [0, -36, 0], rotate: [0, -7, 8, 0], scale: [1, 1.08, 1] },
        { duration: 0.85, ease: "easeInOut" });
    }
    await this.setState("idle");
  }

  async pointAt(element) {
    await this.flyTo(element, "right");
    if (!this.reducedMotion && typeof animate !== "undefined") {
      const { animate: motionAnimate } = await import("https://cdn.jsdelivr.net/npm/motion@latest/+esm");
      await motionAnimate(this.sprite, { rotate: [0, -5, 0] }, { duration: 0.45 });
    }
  }

  // ── Chat Integration ────────────────────────────────────────────────

  onBeeClick() {
    this.chatOpen = !this.chatOpen;
    document.dispatchEvent(
      new CustomEvent("mythicbee:chat-toggle", {
        detail: { open: this.chatOpen }
      })
    );

    this.celebrate();

    const greetings = [
      "Need a gift idea?",
      "Tell me about someone!",
      "Let's make something legendary.",
      "What's the occasion?",
      "I know a guy... it's me."
    ];
    this.speak(greetings[Math.floor(Math.random() * greetings.length)]);
  }

  speak(text) {
    // Use speech synthesis for now
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1.1;
      speechSynthesis.speak(utterance);
    }
  }

  // ── Lifecycle ───────────────────────────────────────────────────────

  destroy() {
    if (this.idleAnimation && this.idleAnimation.stop) {
      this.idleAnimation.stop();
    }
    if (this.root && this.root.parentNode) {
      this.root.parentNode.removeChild(this.root);
    }
  }
}

// Auto-init
if (typeof window !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    window.mythicBee = new MythicBeeController();
    window.mythicBee.init();
  });
}

export default MythicBeeController;
