// Star at Night — State Management
// Persists gift session to localStorage

const STORAGE_KEY = 'star-at-night-session';

const marketConfig = {
  country: 'GB',
  currency: 'GBP',
  locale: 'en-GB'
};

function formatPrice(amount) {
  return new Intl.NumberFormat(marketConfig.locale, {
    style: 'currency',
    currency: marketConfig.currency
  }).format(amount);
}

function createEmptySession() {
  return {
    recipient: {
      name: '',
      relationship: ''
    },
    occasion: '',
    memories: [],
    description: '',
    tone: [],
    photos: [],
    concepts: [],
    selectedConceptId: null
  };
}

function loadSession() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.warn('Failed to load session:', e);
  }
  return createEmptySession();
}

function saveSession(session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch (e) {
    console.warn('Failed to save session:', e);
  }
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
}

// Export
window.StarAtNight = window.StarAtNight || {};
window.StarAtNight.state = {
  session: loadSession(),
  save: () => saveSession(window.StarAtNight.state.session),
  clear: clearSession,
  formatPrice,
  market: marketConfig
};
