// Star at Night — Main App
// Initializes all components

document.addEventListener('DOMContentLoaded', () => {
  // Initialize starfield
  const starfield = document.querySelector('.starfield');
  if (starfield && window.StarAtNight.starfield) {
    window.StarAtNight.starfield.create(starfield, 42);
  }
  
  // Initialize creation flow
  if (window.StarAtNight.creationFlow) {
    window.StarAtNight.creationFlow.init();
  }
  
  // Scroll reveal
  const reveals = document.querySelectorAll('.reveal');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('reveal--visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  
  reveals.forEach(el => revealObserver.observe(el));
  
  // Nav scroll behavior
  const nav = document.querySelector('.nav');
  if (nav) {
    let lastScroll = 0;
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;
      if (currentScroll > 50) {
        nav.classList.add('nav--scrolled');
      } else {
        nav.classList.remove('nav--scrolled');
      }
      lastScroll = currentScroll;
    }, { passive: true });
  }
  
  // Star parallax (subtle mouse movement)
  const heroStar = document.querySelector('.star-container--hero');
  if (heroStar) {
    document.addEventListener('mousemove', (e) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 6; // ±3px
      const y = (e.clientY / window.innerHeight - 0.5) * 4; // ±2px
      heroStar.style.transform = `translate(${x}px, ${y}px)`;
    }, { passive: true });
  }
  
  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
});

window.StarAtNight = window.StarAtNight || {};
window.StarAtNight.app = { version: '1.0.0' };
