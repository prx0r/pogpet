/**
 * GiftBrief — Structured user object for Bartholomew conversations.
 * 
 * The conversation is natural-language slot filling around this object.
 * Bartholomew reasons from what's missing, not from a questionnaire.
 */

// ── GiftBrief Schema ───────────────────────────────────────────────────

const GiftBrief = {
  // Core recipient info
  recipient: {
    name: null,           // "Steve"
    relationship: null,   // "dad" | "mum" | "partner" | "friend" | "child" | "pet"
    age: null,            // 60
    gender: null,         // "male" | "female" | null
  },

  // Occasion
  occasion: null,        // "birthday" | "fathers_day" | "christmas" | "anniversary" | "just_because"

  // What makes them unique
  interests: [],         // ["football", "Liverpool FC", "golf"]
  personality: [],       // ["teasing", "humorous", "adventurous"]
  memories: [],          // ["first date in Lisbon", "that time he scored"]
  inside_jokes: [],      // ["the knee story", "always late"]
  traits: [],            // ["60th birthday", "retiring", "new dad"]

  // Creative direction
  tone: null,            // "funny" | "beautiful" | "understated" | "sentimental" | "ridiculous" | "surprise_me"
  style: null,           // "cinematic" | "keepsake" | "newspaper" | "biography" | "story"

  // Source material
  assets: {
    photos: [],          // URLs or file references
    videos: [],
    voice_notes: [],
    text_snippets: [],   // quotes, stories, facts
  },

  // Product selection
  desired_product: null,  // "hero_film" | "football_legend" | "memory_keepsake" | null
  budget: null,          // "£24" | "£29" | "£34" | null
  deadline: null,        // "2026-06-15" | null

  // Confidence tracking
  confidence: {
    occasion: 0.0,       // 0-1
    recipient: 0.0,
    interests: 0.0,
    tone: 0.0,
    creative_direction: 0.0,
    product_match: 0.0,
  },

  // Conversation state
  conversation_turn: 0,
  last_action: null,     // "asked_about_interests" | "showed_products" etc.
  session_id: null,
};

// ── Function Calls (Bartholomew → Website) ──────────────────────────────

const BEE_FUNCTIONS = {
  // Gift brief management
  update_gift_brief: {
    description: "Update the gift brief with new information",
    parameters: { fields: "object — key/value pairs to update" },
    example: { occasion: "Father's Day", recipient: { relationship: "father", age: 60 } }
  },
  get_gift_brief: {
    description: "Get current gift brief state",
    returns: "GiftBrief object"
  },

  // Product display
  show_products: {
    description: "Show product cards on the page",
    parameters: { ids: "array of product IDs to show" },
    example: { ids: ["hero_film", "football_legend", "memory_keepsake"] }
  },
  show_example: {
    description: "Show a specific example/template",
    parameters: { example_id: "string" }
  },

  // Character animation
  fly_to: {
    description: "Fly Bartholomew to a page element",
    parameters: { element: "CSS selector" },
    side_effect: "client_only"
  },
  point_at: {
    description: "Point at a page element",
    parameters: { element: "CSS selector" },
    side_effect: "client_only"
  },
  celebrate: {
    description: "Play celebration animation",
    parameters: {},
    side_effect: "client_only"
  },
  set_expression: {
    description: "Change facial expression",
    parameters: { expression: "idle|thinking|excited|confused|happy" },
    side_effect: "client_only"
  },

  // User input
  request_photo_upload: {
    description: "Open photo upload dialog",
    parameters: {},
    side_effect: "client_only"
  },
  request_video_upload: {
    description: "Open video upload dialog",
    parameters: {},
    side_effect: "client_only"
  },

  // Product creation
  create_concept: {
    description: "Generate a new product concept from the gift brief",
    parameters: {},
    side_effect: "server"
  },
  create_preview: {
    description: "Generate preview of selected product",
    parameters: { product_id: "string" },
    side_effect: "server"
  },

  // Commerce
  add_to_cart: {
    description: "Add product to cart",
    parameters: { product_id: "string" },
    side_effect: "server"
  }
};

// ── Conversation Flow ───────────────────────────────────────────────────

const CONVERSATION_FLOW = {
  // What Bartholomew asks at each stage
  stages: {
    greeting: {
      prompt: "Who are we making something mythic for?",
      collects: ["recipient.name", "recipient.relationship"],
      next: "occasion"
    },
    occasion: {
      prompt: "What's happening?",
      collects: ["occasion"],
      options: ["birthday", "christmas", "anniversary", "new_home", "just_because"],
      next: "description"
    },
    description: {
      prompt: "Tell us what makes them, them.",
      collects: ["interests", "personality", "memories", "inside_jokes", "traits"],
      next: "photo"
    },
    photo: {
      prompt: "Add a photo, if you have one.",
      collects: ["assets.photos"],
      optional: true,
      next: "tone"
    },
    tone: {
      prompt: "What should it feel like?",
      collects: ["tone"],
      options: ["funny", "beautiful", "understated", "sentimental", "ridiculous", "surprise_me"],
      next: "generate"
    },
    generate: {
      action: "create_concept",
      shows_products: true,
      celebrate: true
    }
  },

  // How Bartholomew reasons between stages
  reasoning: {
    // After collecting enough info, don't ask more questions
    // Instead: "Right. I already have several ideas."
    // Then show products directly.
    min_info_for_generation: 3,  // at least name + relationship + one other
  }
};
