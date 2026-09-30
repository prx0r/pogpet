// Star at Night — Starfield
// Seeded PRNG for consistent constellations

function mulberry32(a) {
  return function() {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    var t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  }
}

function createStarfield(container, seed = 42) {
  const rng = mulberry32(seed);
  const isMobile = window.innerWidth < 768;
  const starCount = isMobile ? 18 : 27;
  
  const fragment = document.createDocumentFragment();
  
  for (let i = 0; i < starCount; i++) {
    const star = document.createElement('div');
    const type = rng();
    
    let size, opacity, className;
    
    if (type < 0.6) {
      // Micro star
      size = 0.7;
      className = 'star--micro';
    } else if (type < 0.9) {
      // Normal star
      size = 1.1;
      className = 'star--normal';
    } else {
      // Bright star (4-point SVG)
      size = 3;
      className = 'star--bright';
    }
    
    opacity = 0.12 + rng() * 0.43;
    const duration = 4 + rng() * 7;
    const delay = rng() * duration;
    
    star.className = `star ${className}`;
    star.style.cssText = `
      left: ${rng() * 100}%;
      top: ${rng() * 100}%;
      width: ${size}px;
      height: ${size}px;
      opacity: 0;
      --tw-opacity-min: ${opacity * 0.5};
      --tw-opacity-max: ${opacity};
      animation: twinkle ${duration}s ease-in-out ${delay}s infinite;
    `;
    
    fragment.appendChild(star);
  }
  
  container.appendChild(fragment);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('.starfield');
  if (container) {
    createStarfield(container, 42);
  }
});

window.StarAtNight = window.StarAtNight || {};
window.StarAtNight.starfield = { create: createStarfield };
