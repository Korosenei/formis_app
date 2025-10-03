// JavaScript pour le dashboard FORMIS

document.addEventListener("DOMContentLoaded", function () {
  initializeDashboard();
  setActiveNavLink();
});

function initializeDashboard() {
  // Initialisation des composants
  initSidebar();
  initNavbar();
  initDropdowns();
  initProgressCircles();
  initTodoList();
  initSearch();
  initMobileMenu();

  // Mise à jour périodique
  updateTimeElements();
  setInterval(updateTimeElements, 60000); // Mise à jour chaque minute
}

// ============ ACTIVE NAV LINK MANAGEMENT ============
function setActiveNavLink() {
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll(".nav-link");

  // Supprimer la classe active de tous les liens
  navLinks.forEach((link) => {
    link.classList.remove("active");
  });

  // Trouver et activer le lien correspondant à l'URL actuelle
  navLinks.forEach((link) => {
    const linkPath = new URL(link.href).pathname;

    // Correspondance exacte
    if (linkPath === currentPath) {
      link.classList.add("active");
      return;
    }

    // Correspondance partielle pour les sous-pages
    if (currentPath.startsWith(linkPath) && linkPath !== "/dashboard/") {
      link.classList.add("active");
      return;
    }

    // Cas spécial pour le tableau de bord principal
    if (
      linkPath === "/dashboard/" &&
      (currentPath === "/dashboard/" || currentPath === "/dashboard")
    ) {
      link.classList.add("active");
    }
  });
}

// Fonction avancée avec mapping des URLs pour une correspondance plus précise
function setActiveNavLinkAdvanced() {
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll(".nav-link");

  // Mapping des URLs pour une correspondance plus flexible
  const urlMapping = {
    // Étudiant
    "/dashboard/student/": ["/dashboard/", "/dashboard/student/"],
    "/dashboard/student-courses/": [
      "/dashboard/student-courses/",
      "/dashboard/courses/",
    ],
    "/dashboard/student-schedule/": [
      "/dashboard/student-schedule/",
      "/dashboard/schedule/",
    ],
    "/dashboard/student-evaluations/": [
      "/dashboard/student-evaluations/",
      "/dashboard/evaluations/",
    ],
    "/dashboard/student-resultats/": [
      "/dashboard/student-resultats/",
      "/dashboard/grades/",
      "/dashboard/results/",
    ],
    "/dashboard/student-attendances/": [
      "/dashboard/student-attendances/",
      "/dashboard/attendance/",
    ],
    "/dashboard/student-paiements/": [
      "/dashboard/student-paiements/",
      "/dashboard/payments/",
    ],
    "/dashboard/student-resources/": [
      "/dashboard/student-resources/",
      "/dashboard/resources/",
    ],
    "/dashboard/student-documents/": [
      "/dashboard/student-documents/",
      "/dashboard/documents/",
    ],

    // Enseignant
    "/dashboard/": ["/dashboard/"],
    "/dashboard/my-courses/": [
      "/dashboard/my-courses/",
      "/dashboard/teacher-courses/",
    ],
    "/dashboard/schedule/": [
      "/dashboard/schedule/",
      "/dashboard/teacher-schedule/",
    ],
    "/dashboard/logbook/": ["/dashboard/logbook/"],
    "/dashboard/evaluations/": [
      "/dashboard/evaluations/",
      "/dashboard/teacher-evaluations/",
    ],
    "/dashboard/grades/": ["/dashboard/grades/", "/dashboard/teacher-grades/"],
    "/dashboard/attendance/": [
      "/dashboard/attendance/",
      "/dashboard/teacher-attendance/",
    ],
    "/dashboard/students/": ["/dashboard/students/", "/dashboard/my-students/"],
    "/dashboard/resources/": [
      "/dashboard/resources/",
      "/dashboard/teacher-resources/",
    ],
    "/dashboard/reports/": [
      "/dashboard/reports/",
      "/dashboard/teacher-reports/",
    ],
  };

  // Supprimer la classe active de tous les liens
  navLinks.forEach((link) => {
    link.classList.remove("active");
  });

  // Chercher une correspondance
  let matchFound = false;

  navLinks.forEach((link) => {
    const linkPath = new URL(link.href).pathname;

    // Vérifier si ce lien correspond à l'URL actuelle
    for (const [targetPath, aliases] of Object.entries(urlMapping)) {
      if (
        linkPath === targetPath &&
        aliases.some((alias) => currentPath.startsWith(alias))
      ) {
        link.classList.add("active");
        matchFound = true;
        break;
      }
    }
  });

  // Si aucune correspondance trouvée, utiliser la méthode simple
  if (!matchFound) {
    setActiveNavLink();
  }
}

// ============ SIDEBAR ============
function initSidebar() {
  const sidebar = document.getElementById("sidebar");
  const logo = document.getElementById("logo");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const mainContent = document.querySelector(".main-content");
  const navbar = document.querySelector(".navbar");
  const footer = document.querySelector(".dashboard-footer");

  if (logo) {
    logo.addEventListener("click", function () {
      toggleSidebar();
    });
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", function () {
      toggleSidebar();
    });
  }

  // MODIFICATION : Gestion des liens actifs avec navigation
  const navLinks = document.querySelectorAll(".nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", function (e) {
      // Ne pas empêcher la navigation
      // Petit délai pour laisser l'URL se mettre à jour
      setTimeout(() => {
        setActiveNavLink();
      }, 10);
    });
  });

  // Auto-collapse sur mobile
  if (window.innerWidth <= 768) {
    sidebar.classList.add("collapsed");
    mainContent.classList.add("sidebar-collapsed");
    navbar.classList.add("sidebar-collapsed");
    if (footer) footer.classList.add("sidebar-collapsed");
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const mainContent = document.querySelector(".main-content");
  const navbar = document.querySelector(".navbar");
  const footer = document.querySelector(".dashboard-footer");

  sidebar.classList.toggle("collapsed");
  mainContent.classList.toggle("sidebar-collapsed");
  navbar.classList.toggle("sidebar-collapsed");
  if (footer) footer.classList.toggle("sidebar-collapsed");

  // Sauvegarder l'état dans le localStorage
  localStorage.setItem(
    "sidebarCollapsed",
    sidebar.classList.contains("collapsed")
  );

  // Animation des icônes
  const toggleIcon = document.querySelector("#sidebarToggle i");
  if (toggleIcon) {
    toggleIcon.style.transform = sidebar.classList.contains("collapsed")
      ? "rotate(180deg)"
      : "rotate(0deg)";
  }
}

// ============ NAVBAR ============
function initNavbar() {
    // Gestion du breadcrumb dynamique
    updateBreadcrumb();

    // Animation de la navbar au scroll
    let lastScrollTop = 0;
    const navbar = document.querySelector('.navbar');

    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

        if (scrollTop > lastScrollTop && scrollTop > 100) {
            // Scroll vers le bas
            navbar.style.transform = 'translateY(-100%)';
        } else {
            // Scroll vers le haut
            navbar.style.transform = 'translateY(0)';
        }

        lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
    });
}

function updateBreadcrumb() {
    const breadcrumb = document.querySelector('.breadcrumb, .breadcrumb-item');
    const currentPath = window.location.pathname;

    // MODIFICATION : Mapping étendu des URL vers les titres
    const pathTitles = {
        // Pages principales
        '/dashboard/': 'Tableau de bord',

        // Étudiant
        '/dashboard/student/': 'Tableau de bord',
        '/dashboard/student-courses/': 'Mes Cours',
        '/dashboard/student-schedule/': 'Emploi du temps',
        '/dashboard/student-evaluations/': 'Évaluations',
        '/dashboard/student-resultats/': 'Notes & Résultats',
        '/dashboard/student-attendances/': 'Présences',
        '/dashboard/student-paiements/': 'Paiements',
        '/dashboard/student-resources/': 'Ressources',
        '/dashboard/student-documents/': 'Documents',

        // Enseignant
        '/dashboard/my-courses/': 'Mes Enseignements',
        '/dashboard/schedule/': 'Emploi du temps',
        '/dashboard/logbook/': 'Cahier de textes',
        '/dashboard/evaluations/': 'Évaluations',
        '/dashboard/grades/': 'Notes & Corrections',
        '/dashboard/attendance/': 'Présences',
        '/dashboard/students/': 'Mes Étudiants',
        '/dashboard/resources/': 'Ressources',
        '/dashboard/reports/': 'Rapports',

        // Autres pages possibles
        '/dashboard/courses/': 'Cours',
        '/dashboard/payments/': 'Paiements',
        '/dashboard/documents/': 'Documents'
    };

    if (breadcrumb) {
        // Chercher une correspondance exacte d'abord
        let title = pathTitles[currentPath];

        // Si pas de correspondance exacte, chercher une correspondance partielle
        if (!title) {
            for (const [path, titleText] of Object.entries(pathTitles)) {
                if (currentPath.startsWith(path) && path !== '/dashboard/') {
                    title = titleText;
                    break;
                }
            }
        }

        if (title) {
            breadcrumb.textContent = title;
        }
    }
}

// ============ NAVIGATION HANDLERS ============
// Écouter les changements d'URL (bouton retour/avancer du navigateur)
window.addEventListener('popstate', function() {
    setActiveNavLink();
    updateBreadcrumb();
});

// Pour les applications avec navigation AJAX/SPA
function handleNavigation(url) {
    // Si vous utilisez la navigation AJAX, appelez cette fonction après le changement d'URL
    history.pushState(null, null, url);
    setActiveNavLink();
    updateBreadcrumb();
}

// ============ DROPDOWNS ============
function initDropdowns() {
    const dropdowns = document.querySelectorAll('.dropdown');

    dropdowns.forEach(dropdown => {
        const trigger = dropdown.querySelector('.navbar-btn');
        const menu = dropdown.querySelector('.dropdown-menu');

        if (trigger && menu) {
            trigger.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                // Fermer tous les autres dropdowns
                dropdowns.forEach(d => {
                    if (d !== dropdown) {
                        d.classList.remove('active');
                    }
                });

                // Toggle le dropdown actuel
                dropdown.classList.toggle('active');
            });
        }
    });

    // Fermer les dropdowns en cliquant ailleurs
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            dropdowns.forEach(dropdown => {
                dropdown.classList.remove('active');
            });
        }
    });

    // Gestion spéciale pour les notifications
    initNotifications();
}

function initNotifications() {
    const markAllRead = document.querySelector('.mark-all-read');
    if (markAllRead) {
        markAllRead.addEventListener('click', function(e) {
            e.preventDefault();

            const notifications = document.querySelectorAll('.notification-item.unread');
            notifications.forEach(notification => {
                notification.classList.remove('unread');
            });

            // Mettre à jour le badge
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                badge.textContent = '0';
                badge.style.display = 'none';
            }

            // Animation de confirmation
            this.textContent = 'Marquées comme lues ✓';
            setTimeout(() => {
                this.textContent = 'Tout marquer comme lu';
            }, 2000);
        });
    }
}

// ============ PROGRESS CIRCLES ============
function initProgressCircles() {
    const progressCircles = document.querySelectorAll('.progress-circle');

    progressCircles.forEach(circle => {
        const progress = circle.getAttribute('data-progress') || 0;
        circle.style.setProperty('--progress', progress);

        // Animation d'entrée
        setTimeout(() => {
            circle.style.transition = 'background 1s ease-in-out';
        }, 100);
    });
}

// ============ TODO LIST ============
function initTodoList() {
    const todoCheckboxes = document.querySelectorAll('.todo-checkbox input');

    todoCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const todoItem = this.closest('.todo-item');
            const todoContent = todoItem.querySelector('.todo-content');
            const deadline = todoItem.querySelector('.todo-deadline');

            if (this.checked) {
                todoContent.classList.add('completed');
                if (deadline) {
                    deadline.textContent = 'Terminé';
                }

                // Animation de completion
                todoItem.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    todoItem.style.transform = 'scale(1)';
                }, 150);

            } else {
                todoContent.classList.remove('completed');
                // Restaurer le texte original de la deadline si nécessaire
            }
        });
    });
}

// ============ SEARCH ============
function initSearch() {
    const searchInput = document.querySelector('.search-input');
    const searchBtn = document.querySelector('.search-btn');

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();

            if (query.length > 2) {
                performSearch(query);
            }
        });

        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch(this.value);
            }
        });
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', function() {
            const query = searchInput.value;
            performSearch(query);
        });
    }
}

function performSearch(query) {
    console.log('Recherche:', query);
    // Ici, vous pouvez implémenter la logique de recherche
    // Par exemple, filtrer des éléments de la page ou faire une requête AJAX
}

// ============ MOBILE MENU ============
function initMobileMenu() {
    const mobileToggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');

    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', function() {
            sidebar.classList.toggle('mobile-open');

            // Overlay pour fermer le menu
            if (sidebar.classList.contains('mobile-open')) {
                createMobileOverlay();
            }
        });
    }
}

function createMobileOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'mobile-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: 999;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;

    document.body.appendChild(overlay);

    // Animation d'entrée
    setTimeout(() => {
        overlay.style.opacity = '1';
    }, 10);

    overlay.addEventListener('click', function() {
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.remove('mobile-open');

        // Animation de sortie
        overlay.style.opacity = '0';
        setTimeout(() => {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        }, 300);
    });
}

// ============ TIME UPDATES ============
function updateTimeElements() {
    const now = new Date();
    const timeElements = document.querySelectorAll('[data-time]');

    timeElements.forEach(element => {
        const timestamp = element.getAttribute('data-time');
        const relativeTime = getRelativeTime(new Date(timestamp), now);
        element.textContent = relativeTime;
    });

    // Mise à jour des indicateurs de statut en temps réel
    updateScheduleStatus();
}

function getRelativeTime(date, now) {
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (minutes < 1) return 'À l\'instant';
    if (minutes < 60) return `Il y a ${minutes} min`;
    if (hours < 24) return `Il y a ${hours}h`;
    if (days < 7) return `Il y a ${days} jour${days > 1 ? 's' : ''}`;

    return date.toLocaleDateString('fr-FR');
}

function updateScheduleStatus() {
    const scheduleItems = document.querySelectorAll('.schedule-item, .course-item');
    const now = new Date();

    scheduleItems.forEach(item => {
        const timeSlot = item.querySelector('.time-start, .time-slot');
        if (timeSlot) {
            const courseTime = parseTimeString(timeSlot.textContent);
            const status = getScheduleStatus(courseTime, now);

            // Mettre à jour les classes CSS et le texte de statut
            item.className = item.className.replace(/(current|upcoming|completed)/, '');
            item.classList.add(status.class);

            const statusElement = item.querySelector('.time-status, .status-badge');
            if (statusElement) {
                statusElement.textContent = status.text;
                statusElement.className = statusElement.className.replace(/(active|upcoming|completed)/, status.class);
            }
        }
    });
}

function parseTimeString(timeStr) {
    // Parse "08:00" ou "08:00 - 10:00"
    const time = timeStr.split(' - ')[0].split(':');
    const date = new Date();
    date.setHours(parseInt(time[0]), parseInt(time[1]), 0, 0);
    return date;
}

function getScheduleStatus(courseTime, now) {
    const diffMinutes = (courseTime - now) / 60000;

    if (diffMinutes < -120) { // Plus de 2h passé
        return { class: 'completed', text: 'Terminé' };
    } else if (diffMinutes < 0) { // En cours
        return { class: 'current', text: 'En cours' };
    } else if (diffMinutes < 30) { // Dans moins de 30 min
        return { class: 'upcoming', text: `Dans ${Math.round(diffMinutes)} min` };
    } else if (diffMinutes < 120) { // Dans moins de 2h
        return { class: 'upcoming', text: `Dans ${Math.round(diffMinutes / 60)}h` };
    } else {
        return { class: '', text: 'À venir' };
    }
}

// ============ UTILITIES ============
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 20px;
        background-color: var(--white);
        border-left: 4px solid var(--${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'}-color);
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        transform: translateX(400px);
        transition: transform 0.3s ease;
        max-width: 300px;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    // Animation d'entrée
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);

    // Auto-suppression
    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

function animateValue(element, start, end, duration = 1000) {
    const startTime = performance.now();
    const difference = end - start;

    function updateValue(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function
        const easeProgress = 1 - Math.pow(1 - progress, 3);

        const currentValue = Math.round(start + (difference * easeProgress));
        element.textContent = currentValue + (element.dataset.suffix || '');

        if (progress < 1) {
            requestAnimationFrame(updateValue);
        }
    }

    requestAnimationFrame(updateValue);
}

// ============ RESPONSIVE HANDLERS ============
window.addEventListener('resize', function() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    const navbar = document.querySelector('.navbar');
    const footer = document.querySelector('.dashboard-footer');

    if (window.innerWidth <= 768) {
        // Mode mobile
        if (!sidebar.classList.contains('collapsed')) {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('sidebar-collapsed');
            navbar.classList.add('sidebar-collapsed');
            if (footer) footer.classList.add('sidebar-collapsed');
        }
    } else {
        // Mode desktop - restaurer l'état sauvegardé
        const wasCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (wasCollapsed) {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('sidebar-collapsed');
            navbar.classList.add('sidebar-collapsed');
            if (footer) footer.classList.add('sidebar-collapsed');
        } else {
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('sidebar-collapsed');
            navbar.classList.remove('sidebar-collapsed');
            if (footer) footer.classList.remove('sidebar-collapsed');
        }
    }
});

// ============ EXPORT POUR UTILISATION GLOBALE ============
window.FORMIS = {
    showNotification,
    animateValue,
    toggleSidebar,
    updateTimeElements,
    setActiveNavLink,
    handleNavigation
};
