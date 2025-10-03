// ===== ANIMATIONS JAVASCRIPT FILE =====

// Animation utilities and effects

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', function() {
  initializeAnimations();
});

function initializeAnimations() {
  setupFloatingElements();
  setupParallaxEffects();
  setupCounterAnimations();
  setupTypewriterEffect();
  setupMorphingShapes();
  setupParticleEffects();
  setupGlowEffects();
  setupHoverAnimations();
}

// ===== FLOATING ELEMENTS =====
function setupFloatingElements() {
  const floatingElements = document.querySelectorAll('.floating-elements *');

  floatingElements.forEach((element, index) => {
    // Add random delays and durations for organic movement
    const delay = Math.random() * 2;
    const duration = 4 + Math.random() * 4;

    element.style.animationDelay = `${delay}s`;
    element.style.animationDuration = `${duration}s`;

    // Add mouse interaction
    element.addEventListener('mouseenter', function() {
      this.style.animationPlayState = 'paused';
      this.style.transform = `${this.style.transform} scale(1.1)`;
    });

    element.addEventListener('mouseleave', function() {
      this.style.animationPlayState = 'running';
      this.style.transform = this.style.transform.replace(' scale(1.1)', '');
    });
  });
}

// ===== PARALLAX EFFECTS =====
function setupParallaxEffects() {
  const parallaxElements = document.querySelectorAll('.parallax');
  let ticking = false;

  function updateParallax() {
    const scrollTop = window.pageYOffset;

    parallaxElements.forEach(element => {
      const speed = element.dataset.speed || 0.5;
      const yPos = -(scrollTop * speed);
      element.style.transform = `translateY(${yPos}px)`;
    });

    ticking = false;
  }

  function requestTick() {
    if (!ticking) {
      requestAnimationFrame(updateParallax);
      ticking = true;
    }
  }

  window.addEventListener('scroll', requestTick, { passive: true });
}

// ===== COUNTER ANIMATIONS =====
function setupCounterAnimations() {
  const counters = document.querySelectorAll('[data-count]');

  const counterObserver = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  });

  counters.forEach(counter => {
    counterObserver.observe(counter);
  });
}

function animateCounter(element) {
  const target = parseInt(element.dataset.count);
  const duration = parseInt(element.dataset.duration) || 2000;
  const increment = target / (duration / 16);
  let current = 0;

  const timer = setInterval(() => {
    current += increment;

    if (current >= target) {
      current = target;
      clearInterval(timer);
    }

    element.textContent = Math.floor(current).toLocaleString();
  }, 16);
}

// ===== TYPEWRITER EFFECT =====
function setupTypewriterEffect() {
  const typewriterElements = document.querySelectorAll('.typewriter');

  typewriterElements.forEach(element => {
    const text = element.textContent;
    const speed = parseInt(element.dataset.speed) || 50;

    element.textContent = '';
    element.classList.add('typing');

    let i = 0;
    const timer = setInterval(() => {
      if (i < text.length) {
        element.textContent += text.charAt(i);
        i++;
      } else {
        clearInterval(timer);
        element.classList.remove('typing');
        element.classList.add('typed');
      }
    }, speed);
  });
}

// ===== MORPHING SHAPES =====
function setupMorphingShapes() {
  const shapes = document.querySelectorAll('.morph-shape');

  shapes.forEach(shape => {
    const morphs = shape.dataset.morphs ? shape.dataset.morphs.split(',') : [];
    if (morphs.length === 0) return;

    let currentIndex = 0;

    setInterval(() => {
      currentIndex = (currentIndex + 1) % morphs.length;
      shape.style.clipPath = morphs[currentIndex];
    }, 3000);
  });
}

// ===== PARTICLE EFFECTS =====
function setupParticleEffects() {
  const particleContainers = document.querySelectorAll('.particles');

  particleContainers.forEach(container => {
    createParticles(container);
  });
}

function createParticles(container) {
  const particleCount = parseInt(container.dataset.count) || 50;
  const particleColor = container.dataset.color || '#4FD1C7';

  for (let i = 0; i < particleCount; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';

    // Random position
    const x = Math.random() * 100;
    const y = Math.random() * 100;

    // Random animation properties
    const size = Math.random() * 4 + 2;
    const duration = Math.random() * 20 + 10;
    const delay = Math.random() * 5;

    particle.style.cssText = `
      position: absolute;
      left: ${x}%;
      top: ${y}%;
      width: ${size}px;
      height: ${size}px;
      background: ${particleColor};
      border-radius: 50%;
      animation: particleFloat ${duration}s infinite linear ${delay}s;
      pointer-events: none;
    `;

    container.appendChild(particle);
  }

  // Add particle animation keyframes if not already added
  if (!document.querySelector('#particle-animations')) {
    const style = document.createElement('style');
    style.id = 'particle-animations';
    style.textContent = `
      @keyframes particleFloat {
        0% {
          transform: translateY(100vh) scale(0);
          opacity: 1;
        }
        100% {
          transform: translateY(-100px) scale(1);
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }
}

// ===== GLOW EFFECTS =====
function setupGlowEffects() {
  const glowElements = document.querySelectorAll('.glow-effect');

  glowElements.forEach(element => {
    element.addEventListener('mouseenter', function() {
      this.style.boxShadow = `0 0 20px ${getComputedStyle(this).color}`;
    });

    element.addEventListener('mouseleave', function() {
      this.style.boxShadow = '';
    });
  });
}

// ===== HOVER ANIMATIONS =====
function setupHoverAnimations() {
  // Magnetic effect for buttons
  const magneticButtons = document.querySelectorAll('.btn-magnetic');

  magneticButtons.forEach(button => {
    button.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;

      this.style.transform = `translate(${x * 0.1}px, ${y * 0.1}px)`;
    });

    button.addEventListener('mouseleave', function() {
      this.style.transform = '';
    });
  });

  // Tilt effect for cards
  const tiltCards = document.querySelectorAll('.tilt-card');

  tiltCards.forEach(card => {
    card.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const rotateX = (e.clientY - centerY) / 10;
      const rotateY = (centerX - e.clientX) / 10;

      this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    });

    card.addEventListener('mouseleave', function() {
      this.style.transform = '';
    });
  });
}

// ===== SCROLL-TRIGGERED ANIMATIONS =====
function createScrollAnimation(element, animationType, options = {}) {
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        applyAnimation(entry.target, animationType, options);
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: options.threshold || 0.1,
    rootMargin: options.rootMargin || '0px'
  });

  observer.observe(element);
}

function applyAnimation(element, type, options) {
  const duration = options.duration || 600;
  const delay = options.delay || 0;
  const easing = options.easing || 'ease-out';

  element.style.transition = `all ${duration}ms ${easing} ${delay}ms`;

  switch (type) {
    case 'fadeIn':
      element.style.opacity = '0';
      element.style.transform = 'translateY(20px)';
      setTimeout(() => {
        element.style.opacity = '1';
        element.style.transform = 'translateY(0)';
      }, 10);
      break;

    case 'slideInLeft':
      element.style.transform = 'translateX(-50px)';
      element.style.opacity = '0';
      setTimeout(() => {
        element.style.transform = 'translateX(0)';
        element.style.opacity = '1';
      }, 10);
      break;

    case 'slideInRight':
      element.style.transform = 'translateX(50px)';
      element.style.opacity = '0';
      setTimeout(() => {
        element.style.transform = 'translateX(0)';
        element.style.opacity = '1';
      }, 10);
      break;

    case 'scaleIn':
      element.style.transform = 'scale(0.8)';
      element.style.opacity = '0';
      setTimeout(() => {
        element.style.transform = 'scale(1)';
        element.style.opacity = '1';
      }, 10);
      break;

    case 'rotateIn':
      element.style.transform = 'rotate(-180deg) scale(0.8)';
      element.style.opacity = '0';
      setTimeout(() => {
        element.style.transform = 'rotate(0deg) scale(1)';
        element.style.opacity = '1';
      }, 10);
      break;
  }
}

// ===== STAGGERED ANIMATIONS =====
function staggerAnimation(elements, animationType, staggerDelay = 100) {
  elements.forEach((element, index) => {
    createScrollAnimation(element, animationType, {
      delay: index * staggerDelay
    });
  });
}

// ===== LOADING ANIMATIONS =====
function createLoadingAnimation(element, type = 'pulse') {
  element.classList.add('loading', `loading-${type}`);

  const style = document.createElement('style');
  style.textContent = `
    .loading-pulse {
      animation: pulse 1.5s ease-in-out infinite;
    }

    .loading-spin {
      animation: spin 1s linear infinite;
    }

    .loading-bounce {
      animation: bounce 1s ease-in-out infinite;
    }

    .loading-fade {
      animation: fade 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.7; transform: scale(1.05); }
    }

    @keyframes bounce {
      0%, 20%, 53%, 80%, 100% { transform: translateY(0); }
      40%, 43% { transform: translateY(-20px); }
      70% { transform: translateY(-10px); }
      90% { transform: translateY(-4px); }
    }

    @keyframes fade {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
  `;

  if (!document.querySelector('#loading-animations')) {
    style.id = 'loading-animations';
    document.head.appendChild(style);
  }
}

function removeLoadingAnimation(element) {
  element.classList.remove('loading', 'loading-pulse', 'loading-spin', 'loading-bounce', 'loading-fade');
}

// ===== REVEAL ANIMATIONS ON SCROLL =====
function setupRevealAnimations() {
  const revealElements = document.querySelectorAll('.reveal-on-scroll');

  const revealObserver = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  revealElements.forEach(element => {
    revealObserver.observe(element);
  });
}

// ===== PAGE TRANSITION EFFECTS =====
function pageTransition(callback, type = 'fade') {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: var(--white);
    z-index: 9999;
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
  `;

  document.body.appendChild(overlay);

  setTimeout(() => {
    overlay.style.opacity = '1';
  }, 10);

  setTimeout(() => {
    if (callback && typeof callback === 'function') {
      callback();
    }

    setTimeout(() => {
      overlay.style.opacity = '0';
      setTimeout(() => {
        document.body.removeChild(overlay);
      }, 300);
    }, 100);
  }, 300);
}

// ===== BREATHING ANIMATION =====
function breathingAnimation(element) {
  element.style.animation = 'breathing 4s ease-in-out infinite';

  if (!document.querySelector('#breathing-animation')) {
    const style = document.createElement('style');
    style.id = 'breathing-animation';
    style.textContent = `
      @keyframes breathing {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
      }
    `;
    document.head.appendChild(style);
  }
}

// ===== WAVE ANIMATION =====
function waveAnimation(element) {
  const text = element.textContent;
  element.innerHTML = '';

  [...text].forEach((char, index) => {
    const span = document.createElement('span');
    span.textContent = char === ' ' ? '\u00A0' : char;
    span.style.animationDelay = `${index * 0.1}s`;
    span.style.display = 'inline-block';
    span.classList.add('wave-char');
    element.appendChild(span);
  });

  if (!document.querySelector('#wave-animation')) {
    const style = document.createElement('style');
    style.id = 'wave-animation';
    style.textContent = `
      .wave-char {
        animation: wave 2s ease-in-out infinite;
      }

      @keyframes wave {
        0%, 60%, 100% { transform: translateY(0); }
        30% { transform: translateY(-20px); }
      }
    `;
    document.head.appendChild(style);
  }
}

// ===== EXPORT FUNCTIONS =====
window.FORMIS_ANIMATIONS = {
  createScrollAnimation,
  staggerAnimation,
  createLoadingAnimation,
  removeLoadingAnimation,
  pageTransition,
  breathingAnimation,
  waveAnimation,
  applyAnimation
};