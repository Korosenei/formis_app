/**
 * FORMIS - Main JavaScript
 * Fonctionnalités principales et interactions
 */

(function() {
    'use strict';

    // Configuration globale
    const FORMIS = {
        animations: {
            duration: 300,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
        },
        breakpoints: {
            sm: 576,
            md: 768,
            lg: 992,
            xl: 1200
        }
    };

    // Utils
    const Utils = {
        // Debounce function
        debounce: function(func, wait, immediate) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    timeout = null;
                    if (!immediate) func(...args);
                };
                const callNow = immediate && !timeout;
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
                if (callNow) func(...args);
            };
        },

        // Throttle function
        throttle: function(func, limit) {
            let inThrottle;
            return function(...args) {
                if (!inThrottle) {
                    func.apply(this, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            }
        },

        // Get viewport width
        getViewportWidth: function() {
            return Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        },

        // Check if element is in viewport
        isInViewport: function(element) {
            const rect = element.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        },

        // Smooth scroll to element
        scrollToElement: function(element, offset = 0) {
            const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
            const offsetPosition = elementPosition - offset;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }
    };

    // Navbar functionality
    const Navbar = {
        init: function() {
            this.setupScrollEffect();
            this.setupMobileToggle();
            this.setupSmoothScroll();
        },

        setupScrollEffect: function() {
            const navbar = document.querySelector('.navbar');
            if (!navbar) return;

            let lastScrollY = window.scrollY;
            let ticking = false;

            const updateNavbar = () => {
                const currentScrollY = window.scrollY;

                if (currentScrollY > 100) {
                    navbar.classList.add('navbar-scrolled');
                } else {
                    navbar.classList.remove('navbar-scrolled');
                }

                // Hide/show navbar on scroll
                if (currentScrollY > lastScrollY && currentScrollY > 200) {
                    navbar.style.transform = 'translateY(-100%)';
                } else {
                    navbar.style.transform = 'translateY(0)';
                }

                lastScrollY = currentScrollY;
                ticking = false;
            };

            const requestTick = () => {
                if (!ticking) {
                    requestAnimationFrame(updateNavbar);
                    ticking = true;
                }
            };

            window.addEventListener('scroll', requestTick);
        },

        setupMobileToggle: function() {
            const toggleButton = document.querySelector('.navbar-toggler');
            const navbarCollapse = document.querySelector('.navbar-collapse');

            if (!toggleButton || !navbarCollapse) return;

            toggleButton.addEventListener('click', function() {
                const isExpanded = toggleButton.getAttribute('aria-expanded') === 'true';

                toggleButton.setAttribute('aria-expanded', !isExpanded);
                navbarCollapse.classList.toggle('show');

                // Animate hamburger icon
                toggleButton.classList.toggle('active');
            });

            // Close mobile menu when clicking outside
            document.addEventListener('click', function(e) {
                if (!toggleButton.contains(e.target) && !navbarCollapse.contains(e.target)) {
                    navbarCollapse.classList.remove('show');
                    toggleButton.setAttribute('aria-expanded', 'false');
                    toggleButton.classList.remove('active');
                }
            });
        },

        setupSmoothScroll: function() {
            const navLinks = document.querySelectorAll('.nav-link[href^="#"]');

            navLinks.forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();

                    const targetId = this.getAttribute('href');
                    const targetElement = document.querySelector(targetId);

                    if (targetElement) {
                        Utils.scrollToElement(targetElement, 80);

                        // Close mobile menu if open
                        const navbarCollapse = document.querySelector('.navbar-collapse');
                        if (navbarCollapse && navbarCollapse.classList.contains('show')) {
                            navbarCollapse.classList.remove('show');
                            document.querySelector('.navbar-toggler').setAttribute('aria-expanded', 'false');
                        }
                    }
                });
            });
        }
    };

    // Animations and scroll effects
    const Animations = {
        init: function() {
            this.setupScrollAnimations();
            this.setupParallax();
            this.setupCounters();
        },

        setupScrollAnimations: function() {
            const animatedElements = document.querySelectorAll('[data-animate]');

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const animation = entry.target.dataset.animate;
                        const delay = entry.target.dataset.delay || 0;

                        setTimeout(() => {
                            entry.target.classList.add('animate-' + animation);
                        }, delay);

                        observer.unobserve(entry.target);
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            });

            animatedElements.forEach(element => {
                observer.observe(element);
            });
        },

        setupParallax: function() {
            const parallaxElements = document.querySelectorAll('[data-parallax]');

            if (parallaxElements.length === 0) return;

            const handleParallax = Utils.throttle(() => {
                const scrollTop = window.pageYOffset;

                parallaxElements.forEach(element => {
                    const speed = parseFloat(element.dataset.parallax) || 0.5;
                    const yPos = -(scrollTop * speed);
                    element.style.transform = `translateY(${yPos}px)`;
                });
            }, 10);

            window.addEventListener('scroll', handleParallax);
        },

        setupCounters: function() {
            const counters = document.querySelectorAll('[data-counter]');

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.animateCounter(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.5 });

            counters.forEach(counter => {
                observer.observe(counter);
            });
        },

        animateCounter: function(element) {
            const target = parseInt(element.dataset.counter);
            const duration = parseInt(element.dataset.duration) || 2000;
            const start = 0;
            const increment = target / (duration / 16);

            let current = start;
            const timer = setInterval(() => {
                current += increment;
                element.textContent = Math.floor(current);

                if (current >= target) {
                    clearInterval(timer);
                    element.textContent = target;
                }
            }, 16);
        }
    };

    // Toast notifications
    const Toast = {
        show: function(message, type = 'info', duration = 5000) {
            const toast = this.create(message, type);
            this.display(toast, duration);
        },

        create: function(message, type) {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;

            const icons = {
                success: 'fas fa-check-circle',
                error: 'fas fa-exclamation-circle',
                warning: 'fas fa-exclamation-triangle',
                info: 'fas fa-info-circle'
            };

            toast.innerHTML = `
                <div class="toast-content">
                    <i class="${icons[type]} toast-icon"></i>
                    <span class="toast-message">${message}</span>
                    <button class="toast-close" type="button">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;

            return toast;
        },

        display: function(toast, duration) {
            let container = document.querySelector('.toast-container');

            if (!container) {
                container = document.createElement('div');
                container.className = 'toast-container';
                document.body.appendChild(container);
            }

            container.appendChild(toast);

            // Animate in
            setTimeout(() => {
                toast.classList.add('toast-show');
            }, 10);

            // Setup close button
            const closeBtn = toast.querySelector('.toast-close');
            closeBtn.addEventListener('click', () => this.hide(toast));

            // Auto hide
            setTimeout(() => {
                this.hide(toast);
            }, duration);
        },

        hide: function(toast) {
            toast.classList.add('toast-hide');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }
    };

    // Form enhancements
    const Forms = {
        init: function() {
            this.setupFloatingLabels();
            this.setupValidation();
            this.setupFileUploads();
        },

        setupFloatingLabels: function() {
            const formGroups = document.querySelectorAll('.form-group');

            formGroups.forEach(group => {
                const input = group.querySelector('input, textarea, select');
                const label = group.querySelector('label');

                if (input && label) {
                    input.addEventListener('focus', () => {
                        group.classList.add('form-group-focused');
                    });

                    input.addEventListener('blur', () => {
                        if (!input.value) {
                            group.classList.remove('form-group-focused');
                        }
                    });

                    // Check initial value
                    if (input.value) {
                        group.classList.add('form-group-focused');
                    }
                }
            });
        },

        setupValidation: function() {
            const forms = document.querySelectorAll('form[data-validate]');

            forms.forEach(form => {
                form.addEventListener('submit', (e) => {
                    if (!this.validateForm(form)) {
                        e.preventDefault();
                    }
                });

                // Real-time validation
                const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
                inputs.forEach(input => {
                    input.addEventListener('blur', () => {
                        this.validateField(input);
                    });
                });
            });
        },

        validateForm: function(form) {
            let isValid = true;
            const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');

            inputs.forEach(input => {
                if (!this.validateField(input)) {
                    isValid = false;
                }
            });

            return isValid;
        },

        validateField: function(field) {
            const value = field.value.trim();
            const fieldGroup = field.closest('.form-group');
            let isValid = true;
            let message = '';

            // Remove existing error
            this.removeFieldError(fieldGroup);

            // Required validation
            if (field.hasAttribute('required') && !value) {
                isValid = false;
                message = 'Ce champ est requis';
            }

            // Email validation
            if (field.type === 'email' && value) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    isValid = false;
                    message = 'Adresse email invalide';
                }
            }

            // Phone validation
            if (field.type === 'tel' && value) {
                const phoneRegex = /^[\+]?[0-9\s\-\(\)]{8,}$/;
                if (!phoneRegex.test(value)) {
                    isValid = false;
                    message = 'Numéro de téléphone invalide';
                }
            }

            // Password validation
            if (field.type === 'password' && value) {
                if (value.length < 8) {
                    isValid = false;
                    message = 'Le mot de passe doit contenir au moins 8 caractères';
                }
            }

            // Show error if invalid
            if (!isValid) {
                this.showFieldError(fieldGroup, message);
            }

            return isValid;
        },

        showFieldError: function(fieldGroup, message) {
            fieldGroup.classList.add('form-group-error');

            const errorDiv = document.createElement('div');
            errorDiv.className = 'form-error';
            errorDiv.textContent = message;

            fieldGroup.appendChild(errorDiv);
        },

        removeFieldError: function(fieldGroup) {
            fieldGroup.classList.remove('form-group-error');
            const existingError = fieldGroup.querySelector('.form-error');
            if (existingError) {
                existingError.remove();
            }
        },

        setupFileUploads: function() {
            const fileInputs = document.querySelectorAll('input[type="file"]');

            fileInputs.forEach(input => {
                const wrapper = document.createElement('div');
                wrapper.className = 'file-upload-wrapper';

                input.parentNode.insertBefore(wrapper, input);
                wrapper.appendChild(input);

                const label = document.createElement('label');
                label.className = 'file-upload-label';
                label.htmlFor = input.id;
                label.innerHTML = `
                    <i class="fas fa-cloud-upload-alt"></i>
                    <span>Choisir un fichier</span>
                `;

                wrapper.appendChild(label);

                input.addEventListener('change', function() {
                    const fileName = this.files[0] ? this.files[0].name : 'Aucun fichier choisi';
                    label.querySelector('span').textContent = fileName;

                    if (this.files[0]) {
                        wrapper.classList.add('file-selected');
                    } else {
                        wrapper.classList.remove('file-selected');
                    }
                });
            });
        }
    };

    // Loading states
    const Loading = {
        show: function(element, text = 'Chargement...') {
            const originalContent = element.innerHTML;
            element.dataset.originalContent = originalContent;
            element.disabled = true;

            element.innerHTML = `
                <span class="loading-spinner"></span>
                <span class="loading-text">${text}</span>
            `;

            element.classList.add('loading');
        },

        hide: function(element) {
            const originalContent = element.dataset.originalContent;
            if (originalContent) {
                element.innerHTML = originalContent;
                element.disabled = false;
                element.classList.remove('loading');
                delete element.dataset.originalContent;
            }
        }
    };

    // Modal functionality
    const Modal = {
        show: function(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('modal-show');
                document.body.classList.add('modal-open');

                // Focus trap
                this.setupFocusTrap(modal);
            }
        },

        hide: function(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('modal-show');
                document.body.classList.remove('modal-open');
            }
        },

        setupFocusTrap: function(modal) {
            const focusableElements = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );

            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    if (e.shiftKey) {
                        if (document.activeElement === firstElement) {
                            lastElement.focus();
                            e.preventDefault();
                        }
                    } else {
                        if (document.activeElement === lastElement) {
                            firstElement.focus();
                            e.preventDefault();
                        }
                    }
                }
            });

            firstElement.focus();
        }
    };

    // Search functionality
    const Search = {
        init: function() {
            this.setupSearchInputs();
        },

        setupSearchInputs: function() {
            const searchInputs = document.querySelectorAll('[data-search]');

            searchInputs.forEach(input => {
                const target = document.querySelector(input.dataset.search);
                if (target) {
                    const debouncedSearch = Utils.debounce((query) => {
                        this.performSearch(query, target);
                    }, 300);

                    input.addEventListener('input', (e) => {
                        debouncedSearch(e.target.value);
                    });
                }
            });
        },

        performSearch: function(query, target) {
            const items = target.querySelectorAll('[data-searchable]');

            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                const matches = text.includes(query.toLowerCase());

                item.style.display = matches ? '' : 'none';
            });

            // Show no results message
            const visibleItems = target.querySelectorAll('[data-searchable]:not([style*="none"])');
            let noResultsMsg = target.querySelector('.no-results');

            if (visibleItems.length === 0 && query.trim() !== '') {
                if (!noResultsMsg) {
                    noResultsMsg = document.createElement('div');
                    noResultsMsg.className = 'no-results text-center p-4';
                    noResultsMsg.innerHTML = `
                        <i class="fas fa-search text-muted" style="font-size: 2rem;"></i>
                        <p class="mt-2 text-muted">Aucun résultat trouvé</p>
                    `;
                    target.appendChild(noResultsMsg);
                }
                noResultsMsg.style.display = 'block';
            } else if (noResultsMsg) {
                noResultsMsg.style.display = 'none';
            }
        }
    };

    // Lazy loading for images
    const LazyLoad = {
        init: function() {
            const images = document.querySelectorAll('img[data-src]');

            if ('IntersectionObserver' in window) {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            img.src = img.dataset.src;
                            img.classList.add('lazy-loaded');
                            observer.unobserve(img);
                        }
                    });
                });

                images.forEach(img => observer.observe(img));
            } else {
                // Fallback for older browsers
                images.forEach(img => {
                    img.src = img.dataset.src;
                });
            }
        }
    };

    // Initialize everything when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        Navbar.init();
        Animations.init();
        Forms.init();
        Search.init();
        LazyLoad.init();

        // Setup modal triggers
        document.addEventListener('click', function(e) {
            const modalTrigger = e.target.closest('[data-modal]');
            if (modalTrigger) {
                e.preventDefault();
                Modal.show(modalTrigger.dataset.modal);
            }

            const modalClose = e.target.closest('[data-modal-close]');
            if (modalClose) {
                const modal = modalClose.closest('.modal');
                if (modal) {
                    Modal.hide(modal.id);
                }
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // ESC key closes modals
            if (e.key === 'Escape') {
                const openModal = document.querySelector('.modal.modal-show');
                if (openModal) {
                    Modal.hide(openModal.id);
                }
            }
        });

        // Setup confirmation dialogs
        document.addEventListener('click', function(e) {
            const confirmTrigger = e.target.closest('[data-confirm]');
            if (confirmTrigger) {
                const message = confirmTrigger.dataset.confirm || 'Êtes-vous sûr ?';
                if (!confirm(message)) {
                    e.preventDefault();
                    return false;
                }
            }
        });

        // Auto-hide alerts
        const alerts = document.querySelectorAll('.alert[data-auto-hide]');
        alerts.forEach(alert => {
            const duration = parseInt(alert.dataset.autoHide) || 5000;
            setTimeout(() => {
                alert.style.opacity = '0';
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 300);
            }, duration);
        });
    });

    // Expose public API
    window.FORMIS = {
        Toast,
        Modal,
        Loading,
        Utils,
        ...FORMIS
    };

})();

