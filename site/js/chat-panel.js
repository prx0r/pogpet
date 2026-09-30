/**
 * MythicBee — Chat Panel
 * Speech bubble interface for Bartholomew conversations
 */

class ChatPanel {
  constructor() {
    this.isOpen = false;
    this.messages = [];
    this.panel = null;
  }

  init() {
    // Create chat panel DOM
    this.panel = document.createElement("div");
    this.panel.id = "chat-panel";
    this.panel.className = "chat-panel";
    this.panel.innerHTML = `
      <div class="chat-panel__header">
        <span class="chat-panel__name">Bartholomew III</span>
        <span class="chat-panel__subtitle">Keeper of MythicBee</span>
        <button class="chat-panel__close" aria-label="Close chat">&times;</button>
      </div>
      <div class="chat-panel__messages"></div>
      <div class="chat-panel__input-area">
        <input type="text" class="chat-panel__input" placeholder="Tell me about someone..." aria-label="Chat message">
        <button class="chat-panel__send" aria-label="Send">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    `;
    document.body.appendChild(this.panel);

    // Event listeners
    this.panel.querySelector(".chat-panel__close").addEventListener("click", () => this.close());
    this.panel.querySelector(".chat-panel__send").addEventListener("click", () => this.sendMessage());
    this.panel.querySelector(".chat-panel__input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.sendMessage();
    });

    // Listen for bee clicks
    document.addEventListener("mythicbee:chat-toggle", (e) => {
      if (e.detail.open) this.open();
      else this.close();
    });

    // Add greeting
    this.addMessage("bot", "Greetings. Bartholomew the Third, Keeper of MythicBee. I'm here to make someone in your life considerably more legendary. What's the occasion?");
  }

  open() {
    this.isOpen = true;
    this.panel.classList.add("chat-panel--open");
    this.panel.querySelector(".chat-panel__input").focus();
    if (window.mythicBee) window.mythicBee.setState("listening");
  }

  close() {
    this.isOpen = false;
    this.panel.classList.remove("chat-panel--open");
    if (window.mythicBee) window.mythicBee.setState("idle");
  }

  addMessage(type, text) {
    this.messages.push({ type, text, timestamp: Date.now() });
    const messagesEl = this.panel.querySelector(".chat-panel__messages");
    const msg = document.createElement("div");
    msg.className = `chat-message chat-message--${type}`;
    msg.textContent = text;
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  sendMessage() {
    const input = this.panel.querySelector(".chat-panel__input");
    const text = input.value.trim();
    if (!text) return;

    this.addMessage("user", text);
    input.value = "";

    // Bartholomew thinks
    if (window.mythicBee) window.mythicBee.setState("thinking");

    // Simulate bot response (replace with Inworld later)
    setTimeout(() => {
      this.processUserMessage(text);
    }, 1200);
  }

  processUserMessage(text) {
    const lower = text.toLowerCase();

    // Simple intent detection
    if (lower.includes("birthday") || lower.includes("turning")) {
      this.addMessage("bot", "A birthday! How wonderful. Who are we celebrating?");
      if (window.mythicBee) window.mythicBee.setState("speaking");
      this.fillBrief({ occasion: "birthday" });
    } else if (lower.includes("father") || lower.includes("dad")) {
      this.addMessage("bot", "Dads are legendary. Tell me — what makes your dad, well, *your* dad?");
      if (window.mythicBee) window.mythicBee.setState("speaking");
      this.fillBrief({ relationship: "dad", recipient: "Dad" });
    } else if (lower.includes("60") || lower.includes("sixty")) {
      this.addMessage("bot", "Sixty! That's a proper milestone. What does he love? Hobbies, passions, terrible jokes — anything helps.");
      if (window.mythicBee) window.mythicBee.setState("speaking");
      this.fillBrief({ age: 60 });
    } else if (lower.includes("liverpool") || lower.includes("football")) {
      this.addMessage("bot", "A Liverpool fan! I'm already seeing ideas. Want me to show you something?");
      if (window.mythicBee) window.mythicBee.setState("speaking");
      this.fillBrief({ interests: ["football", "Liverpool"] });
      // Trigger product showcase after a beat
      setTimeout(() => this.showProducts(), 2000);
    } else if (lower.includes("show") || lower.includes("see") || lower.includes("yes")) {
      this.showProducts();
    } else {
      // Generic response
      const responses = [
        "Tell me more. What do they absolutely love?",
        "Interesting! What else should I know?",
        "Got it. What's their sense of humor like?",
        "Love that. Any particular memories or inside jokes?"
      ];
      this.addMessage("bot", responses[Math.floor(Math.random() * responses.length)]);
      if (window.mythicBee) window.mythicBee.setState("speaking");
    }

    // Return to idle after speaking
    setTimeout(() => {
      if (window.mythicBee) window.mythicBee.setState("idle");
    }, 3000);
  }

  fillBrief(partial) {
    // Merge into GiftBrief
    if (window.mythicBee && window.mythicBee.giftBrief) {
      Object.assign(window.mythicBee.giftBrief, partial);
    } else if (window.mythicBee) {
      window.mythicBee.giftBrief = partial;
    }
  }

  showProducts() {
    this.addMessage("bot", "Here are three things I made for them. Click one to personalise it further.");
    if (window.mythicBee) window.mythicBee.setState("presenting");

    // Open creation panel and jump to results
    document.dispatchEvent(new CustomEvent("mythicbee:show-results"));

    // Fly to the first product
    setTimeout(() => {
      const firstProduct = document.querySelector('.product-card');
      if (firstProduct && window.mythicBee) {
        window.mythicBee.pointAt(firstProduct);
      }
    }, 1500);
  }
}

// Auto-init
if (typeof window !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    window.chatPanel = new ChatPanel();
    window.chatPanel.init();
  });
}

export default ChatPanel;
