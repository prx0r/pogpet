/**
 * Inworld Integration — Bartholomew Voice Agent
 * 
 * WebRTC connection to Inworld Realtime API
 * Handles: STT → LLM → TTS → function calls
 * 
 * Setup: https://docs.inworld.ai/realtime/quickstart-webrtc
 */

class InworldBartholomew {
  constructor(giftBrief) {
    this.giftBrief = giftBrief;
    this.connected = false;
    this.session = null;
    this.onToolCall = null;
    this.onSpeech = null;
  }

  // ── Connection ──────────────────────────────────────────────────────

  async connect() {
    // Inworld Realtime uses WebRTC
    // See: https://docs.inworld.ai/realtime/quickstart-webrtc
    
    console.log("MythicBee: Connecting to Inworld...");
    
    // Configuration would come from your Inworld project
    const config = {
      apiKey: "YOUR_INWORLD_API_KEY",
      playerName: "Bartholomew III",
      // System prompt set in Inworld Studio
    };
    
    // Inworld handles: WebRTC, STT, LLM, TTS, function calling
    // We just connect and handle the events
    
    this.connected = true;
    console.log("MythicBee: Connected");
  }

  // ── Event Handlers ──────────────────────────────────────────────────

  handleToolCall(toolName, params) {
    console.log(`MythicBee: Tool call — ${toolName}`, params);
    
    // Route to appropriate action
    switch (toolName) {
      case "fly_to":
        window.mythicBee?.flyTo(params.element);
        break;
      case "celebrate":
        window.mythicBee?.celebrate();
        break;
      case "show_products":
        this.showProducts(params.ids);
        break;
      case "update_gift_brief":
        this.updateBrief(params.fields);
        break;
      case "request_photo_upload":
        document.getElementById("photo-upload")?.click();
        break;
      default:
        console.log(`MythicBee: Unknown tool ${toolName}`);
    }
  }

  handleSpeech(text) {
    // Bartholomew is speaking
    window.mythicBee?.setState("talking");
  }

  handleSpeechEnd() {
    window.mythicBee?.setState("idle");
  }

  // ── Actions ─────────────────────────────────────────────────────────

  showProducts(productIds) {
    // Trigger product cards to appear on page
    document.dispatchEvent(new CustomEvent("mythicbee:show-products", {
      detail: { ids: productIds }
    }));
  }

  updateBrief(fields) {
    Object.assign(this.giftBrief, fields);
    console.log("GiftBrief updated:", this.giftBrief);
  }

  // ── Conversation Start ──────────────────────────────────────────────

  async startConversation() {
    await this.connect();
    
    // Initial greeting via Inworld
    // Bartholomew introduces himself
    // Conversation begins with gift_brief flow
  }
}

export default InworldBartholomew;
