/**
 * MythicBee — Gift Intelligence Engine
 * Adaptive conversational recommender with belief state
 */

const QBANK = [
  { text: "Tell me about them. Start anywhere.", category: "open", emotional: 0.9, info: 0.95, targets: ["relationship","interests","personality"] },
  { text: "What's the first thing that comes to mind when you think of them?", category: "emotional", emotional: 0.95, info: 0.85, targets: ["personality","interests","memory"] },
  { text: "What makes them laugh harder than anything?", category: "emotional", emotional: 0.92, info: 0.88, targets: ["humour_style","personality","inside_joke"] },
  { text: "What's something only you know about them?", category: "intimate", emotional: 0.97, info: 0.92, targets: ["inside_joke","memory","personality"] },
  { text: "What's a memory that always makes you smile?", category: "emotional", emotional: 0.94, info: 0.87, targets: ["memory","relationship","personality"] },
  { text: "What do they care about far too much?", category: "playful", emotional: 0.88, info: 0.90, targets: ["obsession","interests","personality"] },
  { text: "What would they absolutely hate receiving?", category: "negative", emotional: 0.82, info: 0.93, targets: ["negative_prefs","personality"] },
  { text: "What's their most ridiculous opinion?", category: "playful", emotional: 0.90, info: 0.85, targets: ["humour_style","personality","obsession"] },
  { text: "If they had a catchphrase, what would it be?", category: "creative", emotional: 0.87, info: 0.80, targets: ["personality","humour_style","inside_joke"] },
  { text: "What's the most Dad thing they've ever done?", category: "specific", emotional: 0.91, info: 0.88, targets: ["personality","humour_style","memory"], trigger: "relationship_dad" },
  { text: "What's a tradition they have that's purely theirs?", category: "intimate", emotional: 0.86, info: 0.84, targets: ["personality","interests","memory"] },
  { text: "What would their biography be called?", category: "creative", emotional: 0.85, info: 0.82, targets: ["personality","interests","humour_style"] },
  { text: "What's something they do that nobody else does?", category: "unique", emotional: 0.89, info: 0.87, targets: ["personality","obsession","inside_joke"] },
  { text: "What's the funniest text they've ever sent you?", category: "intimate", emotional: 0.88, info: 0.83, targets: ["humour_style","inside_joke","relationship"] },
  { text: "What's something they're secretly brilliant at?", category: "positive", emotional: 0.84, info: 0.81, targets: ["interests","personality","obsession"] },
  { text: "What's a moment that defines who they are?", category: "deep", emotional: 0.93, info: 0.91, targets: ["memory","personality","relationship"] },
  { text: "What's something they've given you that isn't a thing?", category: "deep", emotional: 0.95, info: 0.89, targets: ["memory","relationship","personality"] },
  { text: "What's a story you'll tell about them someday?", category: "deep", emotional: 0.96, info: 0.90, targets: ["memory","relationship","personality"] },
  { text: "What's something they'd be proud to know you remember?", category: "deep", emotional: 0.97, info: 0.92, targets: ["memory","relationship","personality"] },
  { text: "What's their superpower?", category: "creative", emotional: 0.85, info: 0.82, targets: ["personality","interests","obsession"] }
];

const FLASH_PROMPTS = [
  "What's something only you know?",
  "What makes them laugh?",
  "What's their most ridiculous opinion?",
  "What would they absolutely hate?",
  "What's a memory that defines them?",
  "What do they care about too much?",
  "What's their superpower?",
  "What's a song that reminds you of them?",
  "What's a tradition they have?",
  "What's the most dramatic thing they've done?"
];

class GiftIntelligence {
  constructor() {
    this.brief = { recipient:'', relationship:'', occasion:'', interests:[], personality:'', memory:'', inside_joke:'', obsession:'', negative_prefs:[] };
    this.confidence = {};
    this.asked = [];
    this.turnCount = 0;
    this.engagement = 0.3;
  }

  updateFromText(text) {
    const l = text.toLowerCase();
    const words = text.split(/\s+/).length;
    this.engagement = Math.min(1, this.engagement + words * 0.008);
    this.turnCount++;

    if (/dad|father/i.test(l)) { this.brief.relationship = 'dad'; this.brief.recipient = 'Dad'; }
    if (/mum|mom|mother/i.test(l)) { this.brief.relationship = 'mum'; this.brief.recipient = 'Mum'; }
    if (/husband|partner|boyfriend/i.test(l)) { this.brief.relationship = 'partner'; this.brief.recipient = 'Partner'; }
    if (/friend/i.test(l)) { this.brief.relationship = 'friend'; this.brief.recipient = 'Friend'; }
    if (/dog|cat|pet/i.test(l)) { this.brief.relationship = 'pet'; }
    if (/birthday/i.test(l)) this.brief.occasion = 'birthday';
    if (/christmas/i.test(l)) this.brief.occasion = 'christmas';
    if (/funny|hilarious/i.test(l)) this.brief.personality = 'funny';
    if (/sarcastic|witty|dry/i.test(l)) this.brief.personality = 'sarcastic';
    ['football','soccer','arsenal','liverpool','chelsea','music','guitar','cooking','garden','golf','fishing','travel','wine','beer','book','film','nba','nfl','rugby'].forEach(i => {
      if (l.includes(i) && !this.brief.interests.includes(i)) this.brief.interests.push(i);
    });

    this.updateConfidence();
    return this.brief;
  }

  updateConfidence() {
    const b = this.brief;
    this.confidence = {
      relationship: b.relationship ? 0.95 : 0.1,
      occasion: b.occasion ? 0.90 : 0.1,
      interests: b.interests.length > 0 ? Math.min(0.95, 0.3 + b.interests.length * 0.15) : 0.1,
      personality: b.personality ? 0.85 : 0.1,
      memory: b.memory ? 0.90 : 0.05
    };
  }

  getNextQuestion() {
    const asked = new Set(this.asked);
    const eligible = QBANK.filter(q => !asked.has(q.text));
    if (eligible.length === 0) return null;

    const scored = eligible.map(q => {
      let score = q.emotional * 0.4 + q.info * 0.3;
      const uncertain = q.targets.filter(t => (this.confidence[t] || 0) < 0.7);
      score += uncertain.length * 0.1;
      if (this.turnCount < 3) score += (q.category === 'emotional' || q.category === 'intimate') ? 0.2 : 0;
      return { ...q, score };
    }).sort((a, b) => b.score - a.score);

    const best = scored[0];
    this.asked.push(best.text);
    return best;
  }

  getFlashPrompt() {
    const unused = FLASH_PROMPTS.filter(f => !this.asked.includes(f));
    if (unused.length === 0) return FLASH_PROMPTS[Math.floor(Math.random() * FLASH_PROMPTS.length)];
    return unused[Math.floor(Math.random() * unused.length)];
  }

  getConcepts() {
    const b = this.brief;
    const c = [];
    if (b.relationship === 'dad' || b.interests.some(i => ['football','soccer','arsenal','liverpool','chelsea'].includes(i)))
      c.push({ type: 'gamewinners', name: 'GameWinners', desc: 'Turn them into a sporting legend', emoji: '⚽' });
    if (b.relationship === 'pet' || b.interests.some(i => ['dog','cat','pet'].includes(i)))
      c.push({ type: 'dogcasso', name: 'Dogcasso', desc: 'Renaissance pet portrait', emoji: '🐕' });
    c.push({ type: 'breaking_news', name: 'Breaking News', desc: 'Personalized headline', emoji: '📰' });
    if (b.occasion === 'birthday') c.push({ type: 'coverstar', name: 'CoverStar', desc: 'Magazine cover', emoji: '📸' });
    if (b.relationship === 'dad') c.push({ type: 'legend_of_dad', name: 'Legend of Dad', desc: 'Cinematic documentary', emoji: '🎬' });
    return c.slice(0, 3);
  }

  isReadyForConcepts() {
    const c = this.confidence;
    return (c.relationship >= 0.7 && (c.interests >= 0.5 || c.personality >= 0.5) && this.turnCount >= 3);
  }

  getSummary() {
    const vals = Object.values(this.confidence);
    return {
      brief: { ...this.brief },
      confidence: { ...this.confidence },
      overallConfidence: vals.reduce((a, b) => a + b, 0) / vals.length,
      turnCount: this.turnCount,
      ready: this.isReadyForConcepts()
    };
  }
}

export default GiftIntelligence;
