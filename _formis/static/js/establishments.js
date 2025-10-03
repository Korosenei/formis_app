/**
 * JavaScript pour la gestion des établissements
 * FORMIS - Plateforme de gestion éducative
 */

document.addEventListener('DOMContentLoaded', function() {
    // Configuration globale
    const config = {
        animationDelay: 100,
        scrollOffset: 50,
        transitionDuration: 300,
        debounceDelay: 250
    };

    // ==========================================================================
    // UTILITAIRES
    // ==========================================================================
    
    // Fonction de debounce pour optimiser les performances
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Fonction pour créer des notifications toast
    function showToast(message, type = 'info', duration = 3000) {
        const toastContainer = document.getElementById('toast-container') || createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast-notification`;
        toast.style.cssText = `
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
            margin-bottom: 0.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: none;
            border-radius: 8px;
        `;
        
        const iconMap = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        };
        
        toast.innerHTML = `
            <i class="${iconMap[type]} me-2"></i>
            ${message}
            <button type="button" class="btn-close btn-close-white ms-auto" onclick="this.parentElement.remove()"></button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Animation d'entrée
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        }, 10);
        
        // Auto-suppression
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.parentElement.removeChild(toast);
                }
            }, 300);
        }, duration);
    }

    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 350px;
        `;
        document.body.appendChild(container);
        return container;
    }

    // ==========================================================================
    // ANIMATIONS ET EFFETS VISUELS
    // ==========================================================================
    
    // Animation des cartes au scroll
    function initScrollAnimations() {
        const elements = document.querySelectorAll('.establishment-card, .content-section, .stat-card');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('animate-in');
                    }, index * config.animationDelay);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: `0px 0px -${config.scrollOffset}px 0px`
        });

        elements.forEach(element => {
            element.style.opacity = '0';
            element.style.transform = 'translateY(30px)';
            element.style.transition = `opacity 0.6s ease, transform 0.6s ease`;
            observer.observe(element);
        });
    }

    // Animation des statistiques (compteurs animés)
    function animateCounters() {
        const counters = document.querySelectorAll('.stat-card h3, .stats-summary h3');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                }
            });
        });

        counters.forEach(counter => {
            observer.observe(counter);
        });
    }

    function animateCounter(element) {
        const target = parseInt(element.textContent.replace(/\D/g, ''));
        if (isNaN(target)) return;

        const suffix = element.textContent.replace(/\d/g, '');
        let current = 0;
        const increment = target / 50;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            element.textContent = Math.floor(current) + suffix;
        }, 30);
    }

    // Effet parallax pour les sections hero
    function initParallaxEffect() {
        const heroSections = document.querySelectorAll('.hero, .establishment-hero, .page-hero');
        
        if (heroSections.length === 0) return;

        const handleScroll = debounce(() => {
            const scrolled = window.pageYOffset;
            heroSections.forEach(section => {
                const rate = scrolled * -0.3;
                section.style.transform = `translateY(${rate}px)`;
            });
        }, 10);

        window.addEventListener('scroll', handleScroll);
    }

    // ==========================================================================
    // GESTION DES FILTRES ET RECHERCHE
    // ==========================================================================
    
    function initSearchAndFilters() {
        const searchInput = document.getElementById('search-input');
        const typeFilter = document.getElementById('type-filter');
        const localityFilter = document.getElementById('locality-filter');
        const sortSelect = document.getElementById('sort-select');

        if (searchInput) {
            const debouncedSearch = debounce(performSearch, config.debounceDelay);
            searchInput.addEventListener('input', debouncedSearch);
        }

        if (typeFilter) {
            typeFilter.addEventListener('change', performFilter);
        }

        if (localityFilter) {
            localityFilter.addEventListener('change', performFilter);
        }

        if (sortSelect) {
            sortSelect.addEventListener('change', performSort);
        }
    }

    function performSearch() {
        const query = document.getElementById('search-input').value.toLowerCase();
        const cards = document.querySelectorAll('.establishment-card');
        let visibleCount = 0;

        cards.forEach(card => {
            const title = card.querySelector('.card-title').textContent.toLowerCase();
            const description = card.querySelector('.card-text').textContent.toLowerCase();
            const isVisible = title.includes(query) || description.includes(query);
            
            card.closest('.establishment-item').style.display = isVisible ? 'block' : 'none';
            if (isVisible) visibleCount++;
        });

        updateResultsCounter(visibleCount);
    }

    function performFilter() {
        const typeValue = document.getElementById('type-filter')?.value || '';
        const localityValue = document.getElementById('locality-filter')?.value || '';
        const cards = document.querySelectorAll('.establishment-card');
        let visibleCount = 0;

        cards.forEach(card => {
            const cardType = card.dataset.type || '';
            const cardLocality = card.dataset.locality || '';
            
            const typeMatch = !typeValue || cardType === typeValue;
            const localityMatch = !localityValue || cardLocality === localityValue;
            const isVisible = typeMatch && localityMatch;
            
            card.closest('.establishment-item').style.display = isVisible ? 'block' : 'none';
            if (isVisible) visibleCount++;
        });

        updateResultsCounter(visibleCount);
    }

    function performSort() {
        const sortValue = document.getElementById('sort-select').value;
        const container = document.getElementById('establishments-container');
        const items = Array.from(container.children);

        items.sort((a, b) => {
            const cardA = a.querySelector('.establishment-card');
            const cardB = b.querySelector('.establishment-card');
            
            switch(sortValue) {
                case 'name':
                    return cardA.querySelector('.card-title').textContent.localeCompare(
                        cardB.querySelector('.card-title').textContent
                    );
                case 'type':
                    return cardA.dataset.type.localeCompare(cardB.dataset.type);
                case 'locality':
                    return cardA.dataset.locality.localeCompare(cardB.dataset.locality);
                default:
                    return 0;
            }
        });

        items.forEach(item => container.appendChild(item));
    }

    function updateResultsCounter(count) {
        const counter = document.querySelector('.results-counter');
        if (counter) {
            const plural = count > 1 ? 's' : '';
            counter.textContent = `${count} établissement${plural} trouvé${plural}`;
        }
    }

    // ==========================================================================
    // VUES GRILLE / LISTE
    // ==========================================================================
    
    function initViewToggle() {
        const gridViewBtn = document.getElementById('grid-view');
        const listViewBtn = document.getElementById('list-view');
        const container = document.getElementById('establishments-container');

        if (!gridViewBtn || !listViewBtn || !container) return;

        gridViewBtn.addEventListener('click', () => switchView('grid', gridViewBtn, listViewBtn, container));
        listViewBtn.addEventListener('click', () => switchView('list', listViewBtn, gridViewBtn, container));

        // Sauvegarder la préférence
        const savedView = localStorage.getItem('establishments-view') || 'grid';
        if (savedView === 'list') {
            switchView('list', listViewBtn, gridViewBtn, container);
        }
    }

    function switchView(viewType, activeBtn, inactiveBtn, container) {
        // Mise à jour des classes CSS
        if (viewType === 'list') {
            container.classList.add('list-view');
        } else {
            container.classList.remove('list-view');
        }

        // Mise à jour des boutons
        activeBtn.classList.add('active');
        inactiveBtn.classList.remove('active');

        // Sauvegarder la préférence
        localStorage.setItem('establishments-view', viewType);

        // Animation de transition
        container.style.opacity = '0.5';
        setTimeout(() => {
            container.style.opacity = '1';
        }, 150);
    }

    // ==========================================================================
    // FONCTIONNALITÉS DE PARTAGE ET FAVORIS
    // ==========================================================================
    
    function initSharingFeatures() {
        // Bouton de partage
        const shareButtons = document.querySelectorAll('.btn-share');
        shareButtons.forEach(button => {
            button.addEventListener('click', handleShare);
        });

        // Boutons favoris
        const favoriteButtons = document.querySelectorAll('.btn-favorite');
        favoriteButtons.forEach(button => {
            button.addEventListener('click', handleFavorite);
        });

        // Charger les favoris sauvegardés
        loadFavorites();
    }

    async function handleShare(event) {
        event.preventDefault();
        const button = event.currentTarget;
        const url = button.dataset.url || window.location.href;
        const title = button.dataset.title || document.title;

        if (navigator.share) {
            try {
                await navigator.share({
                    title: title,
                    url: url
                });
                showToast('Partage effectué avec succès !', 'success');
            } catch (err) {
                if (err.name !== 'AbortError') {
                    fallbackShare(url, title);
                }
            }
        } else {
            fallbackShare(url, title);
        }
    }

    function fallbackShare(url, title) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(() => {
                showToast('Lien copié dans le presse-papier !', 'success');
            }).catch(() => {
                showToast('Impossible de copier le lien', 'error');
            });
        } else {
            // Fallback pour les navigateurs plus anciens
            const textArea = document.createElement('textarea');
            textArea.value = url;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                showToast('Lien copié dans le presse-papier !', 'success');
            } catch (err) {
                showToast('Impossible de copier le lien', 'error');
            }
            document.body.removeChild(textArea);
        }
    }

    function handleFavorite(event) {
        event.preventDefault();
        const button = event.currentTarget;
        const establishmentId = button.dataset.establishmentId;
        
        const favorites = JSON.parse(localStorage.getItem('establishment-favorites') || '[]');
        const index = favorites.indexOf(establishmentId);
        
        if (index > -1) {
            favorites.splice(index, 1);
            button.innerHTML = '<i class="far fa-heart"></i>';
            button.classList.remove('active');
            showToast('Retiré des favoris', 'info');
        } else {
            favorites.push(establishmentId);
            button.innerHTML = '<i class="fas fa-heart"></i>';
            button.classList.add('active');
            showToast('Ajouté aux favoris', 'success');
        }
        
        localStorage.setItem('establishment-favorites', JSON.stringify(favorites));
    }

    function loadFavorites() {
        const favorites = JSON.parse(localStorage.getItem('establishment-favorites') || '[]');
        favorites.forEach(id => {
            const button = document.querySelector(`[data-establishment-id="${id}"]`);
            if (button) {
                button.innerHTML = '<i class="fas fa-heart"></i>';
                button.classList.add('active');
            }
        });
    }

    // ==========================================================================
    // LAZY LOADING DES IMAGES
    // ==========================================================================
    
    function initLazyLoading() {
        const images = document.querySelectorAll('img[data-src]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                        
                        img.addEventListener('load', () => {
                            img.style.opacity = '1';
                        });
                    }
                });
            });

            images.forEach(img => {
                img.style.opacity = '0';
                img.style.transition = 'opacity 0.3s ease';
                imageObserver.observe(img);
            });
        } else {
            // Fallback pour les navigateurs plus anciens
            images.forEach(img => {
                img.src = img.dataset.src;
            });
        }
    }

    // ==========================================================================
    // GESTION DES ERREURS RÉSEAU
    // ==========================================================================
    
    function initErrorHandling() {
        // Gestion des images qui ne se chargent pas
        const images = document.querySelectorAll('img');
        images.forEach(img => {
            img.addEventListener('error', function() {
                this.style.display = 'none';
                const placeholder = document.createElement('div');
                placeholder.className = 'img-placeholder bg-light d-flex align-items-center justify-content-center';
                placeholder.style.cssText = `
                    width: ${this.offsetWidth || 200}px;
                    height: ${this.offsetHeight || 200}px;
                    color: #6c757d;
                    font-size: 2rem;
                `;
                placeholder.innerHTML = '<i class="fas fa-image"></i>';
                this.parentNode.insertBefore(placeholder, this);
            });
        });

        // Gestion des liens cassés
        const links = document.querySelectorAll('a[href^="http"]');
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                // Vérification basique de l'URL
                if (!this.href || this.href === 'http://' || this.href === 'https://') {
                    e.preventDefault();
                    showToast('Ce lien n\'est pas disponible', 'warning');
                }
            });
        });
    }

    // ==========================================================================
    // ACCESSIBILITÉ
    // ==========================================================================
    
    function initAccessibilityFeatures() {
        // Navigation au clavier
        const cards = document.querySelectorAll('.establishment-card');
        cards.forEach((card, index) => {
            card.setAttribute('tabindex', '0');
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const link = this.querySelector('.btn-primary');
                    if (link) link.click();
                }
            });
        });

        // Annonces ARIA pour les changements dynamiques
        const ariaLive = document.createElement('div');
        ariaLive.setAttribute('aria-live', 'polite');
        ariaLive.setAttribute('aria-atomic', 'true');
        ariaLive.className = 'sr-only';
        ariaLive.id = 'aria-announcements';
        document.body.appendChild(ariaLive);
    }

    function announceChange(message) {
        const announcer = document.getElementById('aria-announcements');
        if (announcer) {
            announcer.textContent = message;
        }
    }

    // ==========================================================================
    // INITIALISATION PRINCIPALE
    // ==========================================================================
    
    function initEstablishments() {
        try {
            initScrollAnimations();
            animateCounters();
            initParallaxEffect();
            initSearchAndFilters();
            initViewToggle();
            initSharingFeatures();
            initLazyLoading();
            initErrorHandling();
            initAccessibilityFeatures();
            
            // Ajouter la classe pour indiquer que JS est chargé
            document.body.classList.add('js-loaded');
            
            console.log('Establishments module initialized successfully');
        } catch (error) {
            console.error('Error initializing establishments module:', error);
            showToast('Une erreur est survenue lors du chargement', 'error');
        }
    }

    // Démarrage de l'initialisation
    initEstablishments();

    // Nettoyage lors du déchargement de la page
    window.addEventListener('beforeunload', function() {
        // Nettoyer les event listeners si nécessaire
        window.removeEventListener('scroll', initParallaxEffect);
    });
});

// ==========================================================================
// FONCTIONS GLOBALES UTILITAIRES
// ==========================================================================

// Fonction pour recharger dynamiquement la liste des établissements
window.refreshEstablishments = function() {
    const container = document.getElementById('establishments-container');
    if (container) {
        container.style.opacity = '0.5';
        // Ici vous pouvez ajouter un appel AJAX pour recharger les données
        setTimeout(() => {
            container.style.opacity = '1';
            showToast('Liste mise à jour', 'success');
        }, 1000);
    }
};

// Export pour utilisation dans d'autres modules
window.EstablishmentsModule = {
    showToast: function(message, type, duration) {
        // Réutiliser la fonction showToast définie plus haut
        const event = new CustomEvent('showToast', {
            detail: { message, type, duration }
        });
        document.dispatchEvent(event);
    },
    
    refreshView: function() {
        window.refreshEstablishments();
    },
    
    filterByType: function(typeId) {
        const typeFilter = document.getElementById('type-filter');
        if (typeFilter) {
            typeFilter.value = typeId;
            typeFilter.dispatchEvent(new Event('change'));
        }
    },
    
    filterByLocality: function(localityId) {
        const localityFilter = document.getElementById('locality-filter');
        if (localityFilter) {
            localityFilter.value = localityId;
            localityFilter.dispatchEvent(new Event('change'));
        }
    }
};

// ==========================================================================
// ÉVÉNEMENTS PERSONNALISÉS
// ==========================================================================

// Écouter les événements personnalisés
document.addEventListener('showToast', function(e) {
    const { message, type = 'info', duration = 3000 } = e.detail;
    showToast(message, type, duration);
});

// Événement pour mettre à jour les statistiques
document.addEventListener('updateStats', function(e) {
    const stats = e.detail;
    updateStatistics(stats);
});

function updateStatistics(stats) {
    Object.entries(stats).forEach(([key, value]) => {
        const element = document.querySelector(`[data-stat="${key}"]`);
        if (element) {
            animateCounter(element, value);
        }
    });
}

// ==========================================================================
// INTÉGRATIONS AVANCÉES
// ==========================================================================

// Intégration avec les Service Workers pour le cache
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registration successful');
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed: ', err);
            });
    });
}

// Gestion de la connectivité réseau
window.addEventListener('online', function() {
    showToast('Connexion rétablie', 'success');
    document.body.classList.remove('offline');
});

window.addEventListener('offline', function() {
    showToast('Connexion perdue - Mode hors ligne activé', 'warning', 5000);
    document.body.classList.add('offline');
});

// ==========================================================================
// ANALYTICS ET TRACKING
// ==========================================================================

function trackEvent(category, action, label = '', value = 0) {
    // Intégration avec Google Analytics ou autre solution de tracking
    if (typeof gtag !== 'undefined') {
        gtag('event', action, {
            event_category: category,
            event_label: label,
            value: value
        });
    }
    
    // Console log pour le développement
    console.log('Track Event:', { category, action, label, value });
}

// Tracking des interactions utilisateur
document.addEventListener('click', function(e) {
    const target = e.target.closest('.establishment-card, .btn-share, .btn-favorite');
    if (target) {
        if (target.classList.contains('establishment-card')) {
            const establishmentName = target.querySelector('.card-title').textContent;
            trackEvent('Establishments', 'View Card', establishmentName);
        } else if (target.classList.contains('btn-share')) {
            trackEvent('Establishments', 'Share', 'Establishment');
        } else if (target.classList.contains('btn-favorite')) {
            trackEvent('Establishments', 'Favorite Toggle', 'Establishment');
        }
    }
});

// ==========================================================================
// OPTIMISATIONS PERFORMANCE
// ==========================================================================

// Préchargement des ressources importantes
function preloadCriticalResources() {
    const criticalImages = document.querySelectorAll('img[data-preload="true"]');
    criticalImages.forEach(img => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = img.dataset.src || img.src;
        document.head.appendChild(link);
    });
}

// Optimisation des reflows/repaints
function optimizeRendering() {
    // Batching des changements DOM
    const domChanges = [];
    
    window.requestAnimationFrame = window.requestAnimationFrame || 
                                  window.webkitRequestAnimationFrame || 
                                  window.mozRequestAnimationFrame;
    
    function flushDOMChanges() {
        if (domChanges.length > 0) {
            domChanges.forEach(change => change());
            domChanges.length = 0;
        }
    }
    
    // Utiliser requestAnimationFrame pour les changements DOM
    setInterval(flushDOMChanges, 16); // ~60fps
}

// ==========================================================================
// FONCTIONNALITÉS AVANCÉES DE RECHERCHE
// ==========================================================================

// Recherche avancée avec suggestions
function initAdvancedSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;

    // Créer le conteneur de suggestions
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'search-suggestions';
    suggestionsContainer.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #ddd;
        border-top: none;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-height: 200px;
        overflow-y: auto;
        z-index: 1000;
        display: none;
    `;
    
    searchInput.parentElement.style.position = 'relative';
    searchInput.parentElement.appendChild(suggestionsContainer);

    // Données de suggestions (peut être chargé dynamiquement)
    const suggestions = [
        'Université', 'École primaire', 'Lycée', 'Centre de formation',
        'Ouagadougou', 'Bobo-Dioulasso', 'Koudougou', 'Ouahigouya'
    ];

    const debouncedSuggest = debounce((query) => {
        showSuggestions(query, suggestions, suggestionsContainer);
    }, 200);

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        if (query.length >= 2) {
            debouncedSuggest(query);
        } else {
            hideSuggestions(suggestionsContainer);
        }
    });

    // Gestion des touches
    searchInput.addEventListener('keydown', (e) => {
        const suggestions = suggestionsContainer.querySelectorAll('.suggestion-item');
        const active = suggestionsContainer.querySelector('.suggestion-item.active');
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                if (active) {
                    active.classList.remove('active');
                    const next = active.nextElementSibling;
                    if (next) next.classList.add('active');
                } else if (suggestions.length > 0) {
                    suggestions[0].classList.add('active');
                }
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                if (active) {
                    active.classList.remove('active');
                    const prev = active.previousElementSibling;
                    if (prev) prev.classList.add('active');
                }
                break;
                
            case 'Enter':
                if (active) {
                    e.preventDefault();
                    searchInput.value = active.textContent;
                    hideSuggestions(suggestionsContainer);
                    performSearch();
                }
                break;
                
            case 'Escape':
                hideSuggestions(suggestionsContainer);
                break;
        }
    });

    // Fermer les suggestions au clic extérieur
    document.addEventListener('click', (e) => {
        if (!searchInput.parentElement.contains(e.target)) {
            hideSuggestions(suggestionsContainer);
        }
    });
}

function showSuggestions(query, allSuggestions, container) {
    const filtered = allSuggestions.filter(suggestion =>
        suggestion.toLowerCase().includes(query.toLowerCase())
    );

    if (filtered.length === 0) {
        hideSuggestions(container);
        return;
    }

    container.innerHTML = filtered.map(suggestion => `
        <div class="suggestion-item" style="
            padding: 10px 15px;
            cursor: pointer;
            border-bottom: 1px solid #eee;
            transition: background-color 0.2s ease;
        " onmouseover="this.style.backgroundColor='#f8f9fa'" 
           onmouseout="this.style.backgroundColor='white'"
           onclick="document.getElementById('search-input').value='${suggestion}'; 
                    this.parentElement.style.display='none'; 
                    performSearch();">
            ${suggestion}
        </div>
    `).join('');

    container.style.display = 'block';
}

function hideSuggestions(container) {
    container.style.display = 'none';
}

// ==========================================================================
// RESPONSIVE ET MOBILE
// ==========================================================================

// Gestion spécifique mobile
function initMobileFeatures() {
    if (!isMobile()) return;

    // Touch gestures pour les cartes
    let startX, startY;
    
    document.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        if (!startX || !startY) return;
        
        const endX = e.changedTouches[0].clientX;
        const endY = e.changedTouches[0].clientY;
        
        const diffX = startX - endX;
        const diffY = startY - endY;
        
        // Swipe horizontal sur les cartes
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
            const card = e.target.closest('.establishment-card');
            if (card) {
                // Actions de swipe (favoris, partage, etc.)
                if (diffX > 0) {
                    // Swipe gauche - ajouter aux favoris
                    const favoriteBtn = card.querySelector('.btn-favorite');
                    if (favoriteBtn) favoriteBtn.click();
                } else {
                    // Swipe droite - partager
                    const shareBtn = card.querySelector('.btn-share');
                    if (shareBtn) shareBtn.click();
                }
            }
        }
        
        startX = startY = null;
    }, { passive: true });
}

function isMobile() {
    return window.innerWidth <= 768 || /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// ==========================================================================
// GESTION DES ERREURS GLOBALES
// ==========================================================================

window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
    // En production, vous pourriez envoyer ces erreurs à un service de monitoring
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled Promise Rejection:', e.reason);
    e.preventDefault(); // Empêche l'affichage de l'erreur dans la console
});

// ==========================================================================
// INITIALISATION FINALE
// ==========================================================================

// S'assurer que tout est initialisé après le chargement complet
window.addEventListener('load', function() {
    preloadCriticalResources();
    optimizeRendering();
    initAdvancedSearch();
    initMobileFeatures();
    
    // Masquer l'indicateur de chargement si présent
    const loader = document.querySelector('.loading-indicator');
    if (loader) {
        loader.style.opacity = '0';
        setTimeout(() => {
            if (loader.parentElement) {
                loader.parentElement.removeChild(loader);
            }
        }, 300);
    }
    
    // Animation finale pour indiquer que tout est prêt
    document.body.classList.add('fully-loaded');
});

// Debug en mode développement
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.EstablishmentsDebug = {
        showToast: (msg, type) => showToast(msg, type),
        trackEvent: trackEvent,
        refreshView: () => window.refreshEstablishments(),
        getStats: () => {
            return {
                totalCards: document.querySelectorAll('.establishment-card').length,
                visibleCards: document.querySelectorAll('.establishment-card:not([style*="display: none"])').length,
                favorites: JSON.parse(localStorage.getItem('establishment-favorites') || '[]').length
            };
        }
    };
    
    console.log('Establishments Debug Mode Active');
    console.log('Use EstablishmentsDebug object for testing');
}
