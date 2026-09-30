/**
 * MythicBee — Prompt Bank
 * Context-aware mini-prompts that flash up during audio recording
 * to help users ramble productively about someone they love
 */

const PROMPT_BANK = {
  // ── Context-aware prompts (shown based on what we already know) ──────
  context: {
    relationship: {
      dad: [
        "What's something your dad does that nobody else does?",
        "What's the funniest thing your dad has ever said?",
        "What does your dad do that drives everyone mad... but you secretly love?",
        "What's a tradition your dad has that's purely his?",
        "If your dad had a catchphrase, what would it be?",
        "What's the most Dad thing your dad has ever done?",
        "What does your dad cook better than anyone?",
        "What's a skill your dad has that nobody knows about?",
        "What would your dad's biography be called?",
        "What's something your dad always says but never finishes?"
      ],
      mum: [
        "What's something your mum does that's purely her?",
        "What's your mum's superpower?",
        "What's the funniest thing your mum has ever said?",
        "What does your mum do that nobody else does?",
        "What's a tradition your mum has that's purely hers?",
        "What's the most Mum thing your mum has ever done?",
        "What does your mum cook better than anyone?",
        "What's a skill your mum has that nobody knows about?",
        "What would your mum's biography be called?",
        "What's something your mum always says?"
      ],
      partner: [
        "What's the first thing you noticed about them?",
        "What's a habit they have that you adore?",
        "What's the funniest moment you've shared?",
        "What do they do when they think nobody's watching?",
        "What's their most endearing quirk?",
        "What's a song that reminds you of them?",
        "What's something they're passionate about that lights them up?",
        "What's the most romantic thing they've ever done?",
        "What's a inside joke only you two get?",
        "What would their dating profile say?"
      ],
      friend: [
        "What makes them a great friend?",
        "What's the most ridiculous thing you've done together?",
        "What's their most annoying habit... that you actually love?",
        "What's a story only you two know?",
        "What would their biography be called?",
        "What's something they're secretly brilliant at?",
        "What's the funniest text they've ever sent you?",
        "What's a tradition you two share?",
        "What would their superpower be?",
        "What's something they do that always makes you laugh?"
      ],
      pet: [
        "What's their funniest habit?",
        "What do they do that makes you laugh every time?",
        "What's their favourite thing in the world?",
        "What's the most dramatic thing they've ever done?",
        "What's a quirk that's purely theirs?",
        "What would they say if they could talk?",
        "What's their favourite spot in the house?",
        "What's the cutest thing they do when they think nobody's watching?",
        "What's their most embarrassing moment?",
        "What's a nickname you have for them?"
      ],
      grandparent: [
        "What's the best advice they've ever given you?",
        "What's a story from their youth that you love?",
        "What's their most memorable habit?",
        "What's something they do that nobody else does?",
        "What's their secret to a long life?",
        "What's the most impressive thing they've done?",
        "What's a tradition they started?",
        "What's something they always say?",
        "What's their favourite memory?",
        "What would their biography be called?"
      ],
      sibling: [
        "What's the most annoying thing they do... that you secretly love?",
        "What's the funniest fight you've ever had?",
        "What's a code you two share?",
        "What's something they're secretly brilliant at?",
        "What's the most embarrassing thing they've done?",
        "What's a tradition you two have?",
        "What's something only a sibling would know?",
        "What's their most dramatic moment?",
        "What's a story only you two know?",
        "What would their biography be called?"
      ],
      child: [
        "What's the funniest thing they've ever said?",
        "What's their superpower?",
        "What do they do that makes you proud every time?",
        "What's a habit they have that's purely theirs?",
        "What's the most surprising thing they've said?",
        "What's their favourite thing in the world?",
        "What's a moment you'll never forget?",
        "What do they do when they think nobody's watching?",
        "What's their most dramatic moment?",
        "What would their biography be called?"
      ],
      other: [
        "What makes them special?",
        "What's the most memorable thing about them?",
        "What's something only you know about them?",
        "What's their most endearing quality?",
        "What's a story that captures who they are?",
        "What's something they do that nobody else does?",
        "What's the funniest thing about them?",
        "What's a moment that defines them?",
        "What's something they're passionate about?",
        "What would their biography be called?"
      ]
    },
    occasion: {
      birthday: [
        "What's the best birthday memory you have with them?",
        "What would their dream birthday look like?",
        "What's a gift they'd never expect?",
        "What's something they've always wanted to do?",
        "What's the most memorable birthday they've had?"
      ],
      christmas: [
        "What's a Christmas tradition they have?",
        "What's the best Christmas gift they've ever given?",
        "What's their favourite Christmas food?",
        "What's a Christmas memory that makes you smile?",
        "What would their perfect Christmas look like?"
      ],
      anniversary: [
        "What's the most romantic thing they've done?",
        "What's a moment that defines your relationship?",
        "What's something they do that reminds you why you love them?",
        "What's a tradition you share?",
        "What's the funniest moment you've had together?"
      ],
      "new-home": [
        "What's their favourite room in the house?",
        "What's a piece of furniture they love?",
        "What's their ideal Saturday morning at home?",
        "What's something they'd want in every room?",
        "What's a memory from their old home?"
      ],
      "just-because": [
        "What made you think of them today?",
        "What's something they've done recently that impressed you?",
        "What's a moment you shared recently?",
        "What's something they need to hear right now?",
        "What's a memory that always makes you smile?"
      ]
    },
    interests: {
      football: [
        "What's their favourite team?",
        "What's the most dramatic match they've watched?",
        "What's a football memory you share?",
        "What's their celebration when their team scores?",
        "What's their worst football hot take?"
      ],
      cooking: [
        "What's their signature dish?",
        "What's a recipe they're famous for?",
        "What's the worst thing they've ever cooked?",
        "What's their favourite kitchen gadget?",
        "What's a food memory you share?"
      ],
      gardening: [
        "What's their proudest plant?",
        "What's a gardening disaster they've had?",
        "What's their favourite thing to grow?",
        "What's a gardening tip they swear by?",
        "What's the most dramatic thing a plant has done?"
      ],
      music: [
        "What's their favourite song of all time?",
        "What's a song that reminds you of them?",
        "What's their most controversial music opinion?",
        "What's a concert memory you share?",
        "What's a song they always sing along to?"
      ],
      travel: [
        "What's their favourite place they've been?",
        "What's the most adventurous trip they've taken?",
        "What's a travel disaster story?",
        "What's their dream destination?",
        "What's a souvenir they brought back?"
      ]
    }
  },

  // ── General prompts (always relevant) ─────────────────────────────────
  general: [
    "Tell me about them. Start anywhere.",
    "What's the first thing that comes to mind when you think of them?",
    "What's something they do that nobody else does?",
    "What's their most endearing quality?",
    "What's a memory that captures who they are?",
    "What's something only you know about them?",
    "What's the funniest thing about them?",
    "What's something they're passionate about?",
    "What's a moment that defines them?",
    "What's something they always say or do?",
    "What's their superpower?",
    "What's a tradition they have?",
    "What's the most impressive thing they've done?",
    "What's something they do that makes you laugh?",
    "What's a story that captures who they are?",
    "What's something they'd want people to know about them?",
    "What's their most dramatic moment?",
    "What's something they're secretly brilliant at?",
    "What's a moment you'll never forget?",
    "What's something they do that makes them unique?"
  ],

  // ── Follow-up prompts (shown after initial ramble) ────────────────────
  followUp: [
    "Tell me more about that.",
    "What happened next?",
    "How did that make you feel?",
    "What's the funniest part of that story?",
    "What did they say?",
    "How did they react?",
    "What made that moment special?",
    "What's the best part of that story?",
    "What would they say about that?",
    "What's the punchline?"
  ],

  // ── Deep prompts (shown to get richer detail) ─────────────────────────
  deep: [
    "What's something they've done that changed you?",
    "What's a quality you wish you had like them?",
    "What's something they taught you?",
    "What's a moment that bonded you?",
    "What's something they'd be proud to know you remember?",
    "What's a small moment that means a lot?",
    "What's something they do that nobody notices?",
    "What's a memory that always makes you smile?",
    "What's something they've given you that isn't a thing?",
    "What's a story you'll tell about them someday?"
  ]
};

/**
 * Get contextual prompts based on what we know from the GiftBrief
 */
function getContextualPrompts(brief) {
  const prompts = [];
  
  // Add relationship-specific prompts
  if (brief.relationship && PROMPT_BANK.context.relationship[brief.relationship]) {
    prompts.push(...PROMPT_BANK.context.relationship[brief.relationship]);
  }
  
  // Add occasion-specific prompts
  if (brief.occasion && PROMPT_BANK.context.occasion[brief.occasion]) {
    prompts.push(...PROMPT_BANK.context.occasion[brief.occasion]);
  }
  
  // Add interest-specific prompts
  if (brief.interests && Array.isArray(brief.interests)) {
    brief.interests.forEach(interest => {
      const key = interest.toLowerCase();
      if (PROMPT_BANK.context.interests[key]) {
        prompts.push(...PROMPT_BANK.context.interests[key]);
      }
    });
  }
  
  // Always add some general prompts
  prompts.push(...PROMPT_BANK.general);
  
  // Shuffle and return
  return shuffle(prompts);
}

/**
 * Get the next prompt to show during recording
 */
function getNextPrompt(brief, usedPrompts, timeElapsed) {
  // After 30 seconds, start showing deeper prompts
  if (timeElapsed > 30) {
    const unusedDeep = PROMPT_BANK.deep.filter(p => !usedPrompts.includes(p));
    if (unusedDeep.length > 0) {
      return unusedDeep[Math.floor(Math.random() * unusedDeep.length)];
    }
  }
  
  // After 15 seconds, show follow-ups
  if (timeElapsed > 15) {
    const unusedFollowUp = PROMPT_BANK.followUp.filter(p => !usedPrompts.includes(p));
    if (unusedFollowUp.length > 0) {
      return unusedFollowUp[Math.floor(Math.random() * unusedFollowUp.length)];
    }
  }
  
  // Otherwise, contextual prompts
  const contextual = getContextualPrompts(brief);
  const unused = contextual.filter(p => !usedPrompts.includes(p));
  if (unused.length > 0) {
    return unused[Math.floor(Math.random() * unused.length)];
  }
  
  // Fallback: any general prompt
  return PROMPT_BANK.general[Math.floor(Math.random() * PROMPT_BANK.general.length)];
}

function shuffle(array) {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export { PROMPT_BANK, getContextualPrompts, getNextPrompt };
