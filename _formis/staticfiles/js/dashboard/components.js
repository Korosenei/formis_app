// Composants JavaScript réutilisables pour FORMIS

// ============ MODAL COMPONENT ============
class Modal {
    constructor(selector, options = {}) {
        this.modal = document.querySelector(selector);
        this.options = {
            closable: true,
            backdrop: true,
            ...options
        };
        
        if (this.modal) {
            this.init();
        }
    }
    
    init() {
        // Créer le backdrop si nécessaire
        if (this.options.backdrop) {
            this.createBackdrop();
        }
        
        // Event listeners
        this.bindEvents();
    }
    
    createBackdrop() {
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'modal-backdrop';
        this.backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 9999;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        `;
    }
    
    bindEvents() {
        // Boutons de fermeture
        const closeBtns = this.modal.querySelectorAll('[data-dismiss="modal"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', () => this.hide());
        });
        
        // Fermeture par backdrop
        if (this.backdrop && this.options.closable) {
            this.backdrop.addEventListener('click', () => this.hide());
        }
        
        // Fermeture par Escape
        if (this.options.closable) {
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isVisible()) {
                    this.hide();
                }
            });
        }
    }
    
    show() {
        if (this.backdrop) {
            document.body.appendChild(this.backdrop);
            this.backdrop.style.opacity = '1';
            this.backdrop.style.visibility = 'visible';
        }
        
        this.modal.style.display = 'block';
        this.modal.style.opacity = '0';
        this.modal.style.transform = 'scale(0.9) translateY(-20px)';
        
        // Animation d'entrée
        requestAnimationFrame(() => {
            this.modal.style.transition = 'all 0.3s ease';
            this.modal.style.opacity = '1';
            this.modal.style.transform = 'scale(1) translateY(0)';
        });
        
        // Empêcher le scroll du body
        document.body.style.overflow = 'hidden';
        
        // Émettre un événement
        this.modal.dispatchEvent(new CustomEvent('modal:show'));
    }
    
    hide() {
        this.modal.style.opacity = '0';
        this.modal.style.transform = 'scale(0.9) translateY(-20px)';
        
        if (this.backdrop) {
            this.backdrop.style.opacity = '0';
            this.backdrop.style.visibility = 'hidden';
        }
        
        setTimeout(() => {
            this.modal.style.display = 'none';
            if (this.backdrop && this.backdrop.parentNode) {
                this.backdrop.parentNode.removeChild(this.backdrop);
            }
            
            // Restaurer le scroll du body
            document.body.style.overflow = '';
            
            // Émettre un événement
            this.modal.dispatchEvent(new CustomEvent('modal:hide'));
        }, 300);
    }
    
    isVisible() {
        return this.modal.style.display === 'block';
    }
}

// ============ TABS COMPONENT ============
class Tabs {
    constructor(selector) {
        this.container = document.querySelector(selector);
        if (this.container) {
            this.init();
        }
    }
    
    init() {
        this.tabButtons = this.container.querySelectorAll('.tab-button');
        this.tabPanes = this.container.querySelectorAll('.tab-pane');
        
        this.bindEvents();
        this.activateFirstTab();
    }
    
    bindEvents() {
        this.tabButtons.forEach((button, index) => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.activateTab(index);
            });
        });
    }
    
    activateFirstTab() {
        if (this.tabButtons.length > 0) {
            this.activateTab(0);
        }
    }
    
    activateTab(index) {
        // Désactiver tous les onglets
        this.tabButtons.forEach(btn => btn.classList.remove('active'));
        this.tabPanes.forEach(pane => {
            pane.classList.remove('active');
            pane.style.opacity = '0';
        });
        
        // Activer l'onglet sélectionné
        this.tabButtons[index].classList.add('active');
        
        setTimeout(() => {
            this.tabPanes[index].classList.add('active');
            this.tabPanes[index].style.opacity = '1';
        }, 150);
        
        // Émettre un événement
        this.container.dispatchEvent(new CustomEvent('tab:change', {
            detail: { index, button: this.tabButtons[index], pane: this.tabPanes[index] }
        }));
    }
}

// ============ ACCORDION COMPONENT ============
class Accordion {
    constructor(selector) {
        this.accordion = document.querySelector(selector);
        if (this.accordion) {
            this.init();
        }
    }
    
    init() {
        this.items = this.accordion.querySelectorAll('.accordion-item');
        this.bindEvents();
    }
    
    bindEvents() {
        this.items.forEach(item => {
            const header = item.querySelector('.accordion-header');
            const content = item.querySelector('.accordion-content');
            
            header.addEventListener('click', () => {
                this.toggleItem(item);
            });
        });
    }
    
    toggleItem(item) {
        const content = item.querySelector('.accordion-content');
        const icon = item.querySelector('.accordion-icon');
        const isActive = item.classList.contains('active');
        
        if (isActive) {
            // Fermer
            item.classList.remove('active');
            content.style.maxHeight = '0';
            if (icon) icon.style.transform = 'rotate(0deg)';
        } else {
            // Fermer les autres (si accordion simple)
            if (this.accordion.dataset.multiple !== 'true') {
                this.items.forEach(otherItem => {
                    if (otherItem !== item) {
                        otherItem.classList.remove('active');
                        otherItem.querySelector('.accordion-content').style.maxHeight = '0';
                        const otherIcon = otherItem.querySelector('.accordion-icon');
                        if (otherIcon) otherIcon.style.transform = 'rotate(0deg)';
                    }
                });
            }
            
            // Ouvrir
            item.classList.add('active');
            content.style.maxHeight = content.scrollHeight + 'px';
            if (icon) icon.style.transform = 'rotate(180deg)';
        }
    }
}

// ============ TOOLTIP COMPONENT ============
class Tooltip {
    constructor() {
        this.init();
    }
    
    init() {
        this.createTooltipElement();
        this.bindEvents();
    }
    
    createTooltipElement() {
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'tooltip-element';
        this.tooltip.style.cssText = `
            position: absolute;
            background-color: var(--darker-blue);
            color: var(--white);
            padding: 8px 12px;
            border-radius: var(--border-radius);
            font-size: 14px;
            z-index: 10000;
            pointer-events: none;
            opacity: 0;
            transform: translateY(5px);
            transition: all 0.3s ease;
            box-shadow: var(--shadow-md);
            white-space: nowrap;
        `;
        document.body.appendChild(this.tooltip);
    }
    
    bindEvents() {
        document.addEventListener('mouseover', (e) => {
            const element = e.target.closest('[data-tooltip]');
            if (element) {
                this.show(element);
            }
        });
        
        document.addEventListener('mouseout', (e) => {
            const element = e.target.closest('[data-tooltip]');
            if (element) {
                this.hide();
            }
        });
    }
    
    show(element) {
        const text = element.getAttribute('data-tooltip');
        const position = element.getAttribute('data-tooltip-position') || 'top';
        
        this.tooltip.textContent = text;
        
        const rect = element.getBoundingClientRect();
        const tooltipRect = this.tooltip.getBoundingClientRect();
        
        let left, top;
        
        switch (position) {
            case 'top':
                left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
                top = rect.top - tooltipRect.height - 10;
                break;
            case 'bottom':
                left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
                top = rect.bottom + 10;
                break;
            case 'left':
                left = rect.left - tooltipRect.width - 10;
                top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
                break;
            case 'right':
                left = rect.right + 10;
                top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
                break;
        }
        
        this.tooltip.style.left = left + 'px';
        this.tooltip.style.top = top + 'px';
        this.tooltip.style.opacity = '1';
        this.tooltip.style.transform = 'translateY(0)';
    }
    
    hide() {
        this.tooltip.style.opacity = '0';
        this.tooltip.style.transform = 'translateY(5px)';
    }
}

// ============ LOADING SPINNER ============
class LoadingSpinner {
    constructor() {
        this.createSpinner();
    }
    
    createSpinner() {
        this.spinner = document.createElement('div');
        this.spinner.className = 'loading-spinner-overlay';
        this.spinner.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        `;
        
        const spinnerElement = document.createElement('div');
        spinnerElement.style.cssText = `
            width: 50px;
            height: 50px;
            border: 4px solid var(--gray);
            border-top: 4px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        `;
        
        // Ajouter l'animation CSS
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
        
        this.spinner.appendChild(spinnerElement);
        document.body.appendChild(this.spinner);
    }
    
    show() {
        this.spinner.style.opacity = '1';
        this.spinner.style.visibility = 'visible';
    }
    
    hide() {
        this.spinner.style.opacity = '0';
        this.spinner.style.visibility = 'hidden';
    }
}

// ============ DATA TABLE COMPONENT ============
class DataTable {
    constructor(selector, options = {}) {
        this.table = document.querySelector(selector);
        this.options = {
            sortable: true,
            filterable: true,
            pagination: true,
            pageSize: 10,
            ...options
        };
        
        if (this.table) {
            this.init();
        }
    }
    
    init() {
        this.data = this.extractData();
        this.currentPage = 1;
        this.sortColumn = null;
        this.sortDirection = 'asc';
        this.filterValue = '';
        
        this.createControls();
        this.bindEvents();
        this.render();
    }
    
    extractData() {
        const rows = Array.from(this.table.querySelectorAll('tbody tr'));
        return rows.map(row => {
            const cells = Array.from(row.querySelectorAll('td'));
            return cells.map(cell => cell.textContent.trim());
        });
    }
    
    createControls() {
        const container = document.createElement('div');
        container.className = 'datatable-controls';
        container.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        `;
        
        // Filtre
        if (this.options.filterable) {
            const filterContainer = document.createElement('div');
            filterContainer.innerHTML = `
                <input type="text" placeholder="Rechercher..." class="table-filter" style="
                    padding: 8px 12px;
                    border: 2px solid var(--border-color);
                    border-radius: var(--border-radius);
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.3s ease;
                ">
            `;
            container.appendChild(filterContainer);
        }
        
        // Pagination info
        if (this.options.pagination) {
            const paginationInfo = document.createElement('div');
            paginationInfo.className = 'pagination-info';
            paginationInfo.style.fontSize = '14px';
            paginationInfo.style.color = 'var(--text-light)';
            container.appendChild(paginationInfo);
        }
        
        this.table.parentNode.insertBefore(container, this.table);
        this.controls = container;
    }
    
    bindEvents() {
        // Tri par clic sur les headers
        if (this.options.sortable) {
            const headers = this.table.querySelectorAll('thead th');
            headers.forEach((header, index) => {
                header.style.cursor = 'pointer';
                header.style.userSelect = 'none';
                header.addEventListener('click', () => {
                    this.sort(index);
                });
            });
        }
        
        // Filtre
        if (this.options.filterable) {
            const filterInput = this.controls.querySelector('.table-filter');
            filterInput.addEventListener('input', (e) => {
                this.filterValue = e.target.value.toLowerCase();
                this.currentPage = 1;
                this.render();
            });
        }
    }
    
    sort(columnIndex) {
        if (this.sortColumn === columnIndex) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortColumn = columnIndex;
            this.sortDirection = 'asc';
        }
        
        this.data.sort((a, b) => {
            const aValue = a[columnIndex];
            const bValue = b[columnIndex];
            
            // Essayer de convertir en nombre si possible
            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);
            
            let comparison = 0;
            if (!isNaN(aNum) && !isNaN(bNum)) {
                comparison = aNum - bNum;
            } else {
                comparison = aValue.localeCompare(bValue);
            }
            
            return this.sortDirection === 'asc' ? comparison : -comparison;
        });
        
        this.updateSortIndicators();
        this.render();
    }
    
    updateSortIndicators() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            // Supprimer les anciens indicateurs
            const existingIndicator = header.querySelector('.sort-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Ajouter le nouvel indicateur si nécessaire
            if (index === this.sortColumn) {
                const indicator = document.createElement('span');
                indicator.className = 'sort-indicator';
                indicator.innerHTML = this.sortDirection === 'asc' ? ' ↑' : ' ↓';
                indicator.style.color = 'var(--primary-color)';
                header.appendChild(indicator);
            }
        });
    }
    
    getFilteredData() {
        if (!this.filterValue) {
            return this.data;
        }
        
        return this.data.filter(row => {
            return row.some(cell => 
                cell.toLowerCase().includes(this.filterValue)
            );
        });
    }
    
    getPaginatedData() {
        const filteredData = this.getFilteredData();
        
        if (!this.options.pagination) {
            return filteredData;
        }
        
        const startIndex = (this.currentPage - 1) * this.options.pageSize;
        const endIndex = startIndex + this.options.pageSize;
        
        return filteredData.slice(startIndex, endIndex);
    }
    
    render() {
        const tbody = this.table.querySelector('tbody');
        const paginatedData = this.getPaginatedData();
        
        // Vider le tbody
        tbody.innerHTML = '';
        
        // Ajouter les nouvelles lignes
        paginatedData.forEach(rowData => {
            const row = document.createElement('tr');
            rowData.forEach(cellData => {
                const cell = document.createElement('td');
                cell.textContent = cellData;
                row.appendChild(cell);
            });
            tbody.appendChild(row);
        });
        
        // Mettre à jour les contrôles de pagination
        this.updatePaginationInfo();
        this.createPaginationControls();
    }
    
    updatePaginationInfo() {
        if (!this.options.pagination) return;
        
        const info = this.controls.querySelector('.pagination-info');
        const filteredData = this.getFilteredData();
        const totalItems = filteredData.length;
        const startItem = (this.currentPage - 1) * this.options.pageSize + 1;
        const endItem = Math.min(this.currentPage * this.options.pageSize, totalItems);
        
        info.textContent = `Affichage de ${startItem} à ${endItem} sur ${totalItems} éléments`;
    }
    
    createPaginationControls() {
        if (!this.options.pagination) return;
        
        // Supprimer les anciens contrôles
        const existingControls = this.table.parentNode.querySelector('.pagination-controls');
        if (existingControls) {
            existingControls.remove();
        }
        
        const filteredData = this.getFilteredData();
        const totalPages = Math.ceil(filteredData.length / this.options.pageSize);
        
        if (totalPages <= 1) return;
        
        const paginationControls = document.createElement('div');
        paginationControls.className = 'pagination-controls';
        paginationControls.style.cssText = `
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
        `;
        
        // Bouton précédent
        const prevBtn = this.createPaginationButton('‹ Précédent', this.currentPage > 1, () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.render();
            }
        });
        paginationControls.appendChild(prevBtn);
        
        // Numéros de pages
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                const pageBtn = this.createPaginationButton(i.toString(), true, () => {
                    this.currentPage = i;
                    this.render();
                });
                
                if (i === this.currentPage) {
                    pageBtn.style.backgroundColor = 'var(--primary-color)';
                    pageBtn.style.color = 'var(--white)';
                }
                
                paginationControls.appendChild(pageBtn);
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '8px';
                paginationControls.appendChild(ellipsis);
            }
        }
        
        // Bouton suivant
        const nextBtn = this.createPaginationButton('Suivant ›', this.currentPage < totalPages, () => {
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.render();
            }
        });
        paginationControls.appendChild(nextBtn);
        
        this.table.parentNode.appendChild(paginationControls);
    }
    
    createPaginationButton(text, enabled, onClick) {
        const button = document.createElement('button');
        button.textContent = text;
        button.style.cssText = `
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            background-color: var(--white);
            color: var(--text-dark);
            border-radius: var(--border-radius);
            cursor: ${enabled ? 'pointer' : 'not-allowed'};
            transition: all 0.3s ease;
            opacity: ${enabled ? '1' : '0.5'};
        `;
        
        if (enabled) {
            button.addEventListener('click', onClick);
            button.addEventListener('mouseover', () => {
                button.style.backgroundColor = 'var(--light-gray)';
            });
            button.addEventListener('mouseout', () => {
                button.style.backgroundColor = 'var(--white)';
            });
        }
        
        return button;
    }
}

// ============ FORM VALIDATOR ============
class FormValidator {
    constructor(formSelector, rules = {}) {
        this.form = document.querySelector(formSelector);
        this.rules = rules;
        
        if (this.form) {
            this.init();
        }
    }
    
    init() {
        this.bindEvents();
    }
    
    bindEvents() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (this.validate()) {
                this.form.dispatchEvent(new CustomEvent('form:valid'));
            }
        });
        
        // Validation en temps réel
        Object.keys(this.rules).forEach(fieldName => {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.addEventListener('blur', () => {
                    this.validateField(fieldName);
                });
            }
        });
    }
    
    validate() {
        let isValid = true;
        
        Object.keys(this.rules).forEach(fieldName => {
            if (!this.validateField(fieldName)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    validateField(fieldName) {
        const field = this.form.querySelector(`[name="${fieldName}"]`);
        const rules = this.rules[fieldName];
        
        if (!field || !rules) return true;
        
        const value = field.value.trim();
        let isValid = true;
        let errorMessage = '';
        
        // Required
        if (rules.required && !value) {
            isValid = false;
            errorMessage = 'Ce champ est requis';
        }
        
        // Min length
        if (isValid && rules.minLength && value.length < rules.minLength) {
            isValid = false;
            errorMessage = `Minimum ${rules.minLength} caractères requis`;
        }
        
        // Max length
        if (isValid && rules.maxLength && value.length > rules.maxLength) {
            isValid = false;
            errorMessage = `Maximum ${rules.maxLength} caractères autorisés`;
        }
        
        // Email
        if (isValid && rules.email && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                errorMessage = 'Format email invalide';
            }
        }
        
        // Pattern
        if (isValid && rules.pattern && value) {
            const regex = new RegExp(rules.pattern);
            if (!regex.test(value)) {
                isValid = false;
                errorMessage = rules.patternMessage || 'Format invalide';
            }
        }
        
        // Custom validator
        if (isValid && rules.custom) {
            const result = rules.custom(value, field);
            if (result !== true) {
                isValid = false;
                errorMessage = result || 'Valeur invalide';
            }
        }
        
        this.showFieldError(field, isValid ? null : errorMessage);
        
        return isValid;
    }
    
    showFieldError(field, errorMessage) {
        // Supprimer l'ancien message d'erreur
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
        
        // Supprimer la classe d'erreur
        field.classList.remove('field-error');
        
        if (errorMessage) {
            // Ajouter la classe d'erreur
            field.classList.add('field-error');
            
            // Créer le message d'erreur
            const errorElement = document.createElement('div');
            errorElement.className = 'field-error';
            errorElement.textContent = errorMessage;
            errorElement.style.cssText = `
                color: var(--danger-color);
                font-size: 12px;
                margin-top: 4px;
            `;
            
            field.parentNode.appendChild(errorElement);
        }
    }
}

// ============ INITIALISATION ============
document.addEventListener('DOMContentLoaded', function() {
    // Initialiser les composants automatiquement
    
    // Tooltips
    new Tooltip();
    
    // Loading spinner global
    window.loadingSpinner = new LoadingSpinner();
    
    // Tabs
    document.querySelectorAll('.tabs').forEach(tabsElement => {
        new Tabs('.' + Array.from(tabsElement.classList).join('.'));
    });
    
    // Accordions
    document.querySelectorAll('.accordion').forEach(accordionElement => {
        new Accordion('.' + Array.from(accordionElement.classList).join('.'));
    });
    
    // Data tables
    document.querySelectorAll('.data-table').forEach(tableElement => {
        new DataTable('.' + Array.from(tableElement.classList).join('.'));
    });
});

// Export des classes pour utilisation globale
window.FORMIS = {
    ...window.FORMIS,
    Modal,
    Tabs,
    Accordion,
    Tooltip,
    LoadingSpinner,
    DataTable,
    FormValidator
};