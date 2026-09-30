/**
 * MythicBee — BeeSession System
 * Every gift gets a bee. Every bee has a mission.
 */

// ── Bee Generator ──────────────────────────────────────────
const ARCHETYPES = [
  { name: 'knight', title: 'Sir', suffix: 'the Valiant', traits: ['brave', 'honorable', 'dramatic'] },
  { name: 'scholar', title: 'Professor', suffix: '', traits: ['analytical', 'verbose', 'curious'] },
  { name: 'postman', title: '', suffix: 'Post', traits: ['efficient', 'punctual', 'reliable'] },
  { name: 'eccentric', title: '', suffix: 'the Unusual', traits: ['creative', 'unpredictable', 'brilliant'] },
  { name: 'bureaucrat', title: '', suffix: 'Esq.', traits: ['methodical', 'pedantic', 'surprisingly warm'] },
  { name: 'explorer', title: 'Captain', suffix: '', traits: ['adventurous', 'brave', 'curious'] },
  { name: 'artist', title: '', suffix: 'the Inspired', traits: ['creative', 'passionate', 'dramatic'] },
  { name: 'commentator', title: 'Senior', suffix: 'Correspondent', traits: ['excitable', 'dramatic', 'loud'] },
  { name: 'wizard', title: 'The', suffix: 'the Wise', traits: ['mysterious', 'helpful', 'cryptic'] },
  { name: 'detective', title: 'Inspector', suffix: '', traits: ['observant', 'methodical', 'dry wit'] },
  { name: 'gerald', title: '', suffix: '', traits: ['ordinary', 'reliable', 'surprisingly effective'] }
];

const FIRST_NAMES = ['Bartholomew', 'Myshkin', 'Lucifer', 'Ambrose', 'Percival', 'Borzitov', 'Spinoza', 'Ferdinand', 'Cornelius', 'Ignatius', 'Mittens', 'Gerald', 'Barnaby', 'Cedric', 'Dorian', 'Everett', 'Fitzwilliam', 'Gustav', 'Hector', 'Ivan'];

const SUFFIXES_VON = ['Nectar', 'Sting', 'Pollen', 'Bumble', 'Honeycomb', 'Waxwing', 'Dronesworth', 'Flowerbottom', 'Queenbury', 'Workerbee'];

const VISUAL_MODIFIERS = [
  { name: 'cape', color: 0xcc3333 },
  { name: 'bow_tie', color: 0xd4af37 },
  { name: 'monocle', color: 0xc0c0c0 },
  { name: 'tiny_glasses', color: 0x1a1a2e },
  { name: 'helmet', color: 0x808080 },
  { name: 'satchel', color: 0x8b4513 },
  { name: 'scarf', color: 0xff6b6b },
  { name: 'waistcoat', color: 0x2d5a1a },
  { name: 'clipboard', color: 0xf5f0e7 },
  { name: 'crown', color: 0xffd700 }
];

function generateBee(missionContext = {}) {
  // Seed from context
  const occasion = missionContext.occasion || '';
  const relationship = missionContext.relationship || '';
  const tone = missionContext.tone || '';

  // Pick archetype based on context
  let archetype;
  if (relationship === 'dad' || occasion.includes('birthday')) {
    archetype = ARCHETYPES.find(a => a.name === 'commentator') || ARCHETYPES[0];
  } else if (relationship === 'pet') {
    archetype = ARCHETYPES.find(a => a.name === 'gerald') || ARCHETYPES[10];
  } else if (tone === 'sentimental' || occasion.includes('anniversary')) {
    archetype = ARCHETYPES.find(a => a.name === 'artist') || ARCHETYPES[6];
  } else if (tone === 'chaotic' || tone === 'funny') {
    archetype = ARCHETYPES.find(a => a.name === 'eccentric') || ARCHETYPES[3];
  } else {
    archetype = ARCHETYPES[Math.floor(Math.random() * ARCHETYPES.length)];
  }

  // Generate name
  let name;
  const nameStyle = Math.random();
  if (nameStyle < 0.3 && archetype.title) {
    // "Title Name"
    name = `${archetype.title} ${FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)]}`;
  } else if (nameStyle < 0.5) {
    // "Name von Noun"
    name = `${FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)]} von ${SUFFIXES_VON[Math.floor(Math.random() * SUFFIXES_VON.length)]}`;
  } else if (nameStyle < 0.7) {
    // "Name the Adjective"
    const adjectives = ['Third', 'the Third', 'the Magnificent', 'the Terrible', 'the Unknown', 'Jr.'];
    name = `${FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)]} ${adjectives[Math.floor(Math.random() * adjectives.length)]}`;
  } else {
    // Just "Gerald"
    name = FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)];
  }

  // Visual
  const baseColor = Math.random() > 0.5 ? 0xffd700 : 0xe8b600;
  const capeColor = [0xcc3333, 0x1a1a2e, 0x2d5a1a, 0x8b4513][Math.floor(Math.random() * 4)];
  const modifier = VISUAL_MODIFIERS[Math.floor(Math.random() * VISUAL_MODIFIERS.length)];

  // Personality
  const personality = {
    pomposity: Math.random() * 0.5 + (archetype.name === 'commentator' ? 0.5 : 0),
    sentimentality: Math.random() * 0.5 + (tone === 'sentimental' ? 0.3 : 0),
    chaos: Math.random() * 0.3 + (archetype.name === 'eccentric' ? 0.4 : 0),
    curiosity: Math.random() * 0.4 + 0.4,
    brevity: Math.random() * 0.6 + 0.2,
    confidence: Math.random() * 0.3 + 0.6
  };

  return {
    name,
    archetype: archetype.name,
    traits: archetype.traits,
    personality,
    visual: {
      baseColor,
      capeColor,
      modifier: modifier.name,
      modifierColor: modifier.color
    },
    voice: archetype.name === 'commentator' ? 'excited' : archetype.name === 'gerald' ? 'calm' : 'formal',
    skills: generateSkills(archetype, missionContext)
  };
}

function generateSkills(archetype, context) {
  const skills = {};
  const domains = ['fathers', 'mothers', 'partners', 'friends', 'pets', 'colleagues'];
  domains.forEach(d => { skills[d] = Math.floor(Math.random() * 3) + 1; });
  
  if (archetype.name === 'commentator') skills.fathers = 5;
  if (archetype.name === 'gerald') skills.friends = 4;
  if (archetype.name === 'artist') skills.partners = 5;
  
  return skills;
}

// ── BeeSession Class ────────────────────────────────────────
class BeeSession {
  constructor(options = {}) {
    this.beeId = options.beeId || `bee_${Date.now().toString(36)}`;
    this.userId = options.userId || null;
    this.state = options.state || 'active';
    
    // Generate bee if not provided
    this.bee = options.bee || generateBee(options.mission || {});
    
    // Mission
    this.mission = options.mission || {
      recipient: null,
      relationship: null,
      occasion: null,
      deadline: null
    };
    
    // Gift state (what we know about the recipient)
    this.giftState = options.giftState || {
      brief: {},
      hypotheses: [],
      creativeHooks: [],
      confidence: {}
    };
    
    // Satchel (basket)
    this.satchel = options.satchel || {
      items: [],
      total: 0
    };
    
    // Honey
    this.honey = options.honey || 0;
    
    // Experience manifests
    this.experiences = options.experiences || [];
    
    // Timestamps
    this.createdAt = options.createdAt || new Date().toISOString();
    this.lastActiveAt = options.lastActiveAt || new Date().toISOString();
    this.completedAt = null;
  }

  // ── State transitions ───────────────────────────────────
  activate() { this.state = 'active'; this.lastActiveAt = new Date().toISOString(); }
  rest() { this.state = 'resting'; }
  pack() { this.state = 'packed'; }
  returnToHive() { this.state = 'in_hive'; }
  deliver() { this.state = 'delivered'; this.completedAt = new Date().toISOString(); }

  // ── Mission ─────────────────────────────────────────────
  setMission(recipient, relationship, occasion, deadline) {
    this.mission = { recipient, relationship, occasion, deadline };
    this.lastActiveAt = new Date().toISOString();
  }

  // ── Gift state ──────────────────────────────────────────
  updateBrief(key, value) {
    this.giftState.brief[key] = value;
    this.lastActiveAt = new Date().toISOString();
  }

  addHypothesis(hypothesis) {
    this.giftState.hypotheses.push({
      ...hypothesis,
      createdAt: new Date().toISOString()
    });
  }

  addCreativeHook(hook) {
    this.giftState.creativeHooks.push({
      ...hook,
      createdAt: new Date().toISOString()
    });
  }

  // ── Satchel ─────────────────────────────────────────────
  addItem(item) {
    this.satchel.items.push({
      id: `item_${Date.now().toString(36)}`,
      ...item,
      addedAt: new Date().toISOString()
    });
    this.satchel.total = this.satchel.items.reduce((sum, i) => sum + (i.price || 0), 0);
    this.lastActiveAt = new Date().toISOString();
  }

  removeItem(itemId) {
    this.satchel.items = this.satchel.items.filter(i => i.id !== itemId);
    this.satchel.total = this.satchel.items.reduce((sum, i) => sum + (i.price || 0), 0);
  }

  getSatchel() {
    return {
      items: [...this.satchel.items],
      total: this.satchel.total,
      count: this.satchel.items.length
    };
  }

  // ── Honey ───────────────────────────────────────────────
  earnHoney(amount, reason) {
    this.honey += amount;
    return { delta: amount, reason, balance: this.honey };
  }

  spendHoney(amount, reason) {
    if (this.honey < amount) return null;
    this.honey -= amount;
    return { delta: -amount, reason, balance: this.honey };
  }

  // ── Experiences ─────────────────────────────────────────
  addExperience(experience) {
    this.experiences.push({
      id: `exp_${Date.now().toString(36)}`,
      ...experience,
      createdAt: new Date().toISOString()
    });
  }

  // ── Serialization ───────────────────────────────────────
  toJSON() {
    return {
      beeId: this.beeId,
      userId: this.userId,
      state: this.state,
      bee: this.bee,
      mission: this.mission,
      giftState: this.giftState,
      satchel: this.satchel,
      honey: this.honey,
      experiences: this.experiences,
      createdAt: this.createdAt,
      lastActiveAt: this.lastActiveAt,
      completedAt: this.completedAt
    };
  }

  static fromJSON(data) {
    return new BeeSession(data);
  }
}

// ── Bee Manager (persists sessions) ────────────────────────
class BeeManager {
  constructor() {
    this.sessions = new Map();
    this.load();
  }

  load() {
    try {
      const stored = localStorage.getItem('mythicbee-bees');
      if (stored) {
        const arr = JSON.parse(stored);
        arr.forEach(data => this.sessions.set(data.beeId, BeeSession.fromJSON(data)));
      }
    } catch (e) {}
  }

  save() {
    const arr = Array.from(this.sessions.values()).map(s => s.toJSON());
    localStorage.setItem('mythicbee-bees', JSON.stringify(arr));
  }

  createSession(options = {}) {
    const session = new BeeSession(options);
    this.sessions.set(session.beeId, session);
    this.save();
    return session;
  }

  getSession(beeId) {
    return this.sessions.get(beeId);
  }

  getActiveSessions() {
    return Array.from(this.sessions.values()).filter(s => s.state === 'active');
  }

  getAllSessions() {
    return Array.from(this.sessions.values());
  }

  getSleepingSessions() {
    return Array.from(this.sessions.values()).filter(s => s.state === 'resting');
  }

  rerollBee(beeId, missionContext) {
    const session = this.sessions.get(beeId);
    if (!session) return null;
    
    // Archive old bee
    session.rest();
    
    // Create new bee with same mission
    const newSession = this.createSession({
      mission: session.mission,
      missionContext
    });
    
    this.save();
    return newSession;
  }

  getStats() {
    const all = this.getAllSessions();
    return {
      total: all.length,
      active: all.filter(s => s.state === 'active').length,
      resting: all.filter(s => s.state === 'resting').length,
      delivered: all.filter(s => s.state === 'delivered').length,
      totalHoney: all.reduce((sum, s) => sum + s.honey, 0)
    };
  }
}

export { BeeSession, BeeManager, generateBee };
