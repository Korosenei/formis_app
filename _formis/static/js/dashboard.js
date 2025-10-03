(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        initializeDashboard();
    });

    function initializeDashboard() {
        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        const menuToggle = document.getElementById('menu-toggle');
        const wrapper = document.getElementById('wrapper');

        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', function() {
                wrapper.classList.toggle('toggled');
                localStorage.setItem('sidebarToggled', wrapper.classList.contains('toggled'));
            });
        }

        if (menuToggle) {
            menuToggle.addEventListener('click', function() {
                document.body.classList.toggle('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', document.body.classList.contains('sidebar-collapsed'));
            });
        }

        // Restore sidebar state
        if (localStorage.getItem('sidebarToggled') === 'true') {
            wrapper.classList.add('toggled');
        }

        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            document.body.classList.add('sidebar-collapsed');
        }

        // Active menu item
        const currentPath = window.location.pathname;
        const menuLinks = document.querySelectorAll('#sidebar-menu .list-group-item');

        menuLinks.forEach(function(link) {
            if (link.getAttribute('href') === currentPath) {
                link.classList.add('active');
            }
        });

        // Initialize charts if Chart.js is available
        if (typeof Chart !== 'undefined') {
            initializeCharts();
        }

        // Auto-refresh data every 5 minutes
        setInterval(function() {
            refreshDashboardData();
        }, 300000);
    }

    function initializeCharts() {
        // Revenue Chart
        const revenueCtx = document.getElementById('revenueChart');
        if (revenueCtx) {
            new Chart(revenueCtx, {
                type: 'line',
                data: {
                    labels: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun'],
                    datasets: [{
                        label: 'Revenus',
                        data: [12000, 19000, 15000, 25000, 22000, 30000],
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }

        // Students Chart
        const studentsCtx = document.getElementById('studentsChart');
        if (studentsCtx) {
            new Chart(studentsCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Actifs', 'Suspendus', 'Diplômés'],
                    datasets: [{
                        data: [300, 25, 75],
                        backgroundColor: [
                            'rgb(54, 162, 235)',
                            'rgb(255, 205, 86)',
                            'rgb(75, 192, 192)'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
    }

    function refreshDashboardData() {
        // Refresh dashboard statistics
        fetch('/api/dashboard/stats/')
            .then(response => response.json())
            .then(data => {
                updateDashboardStats(data);
            })
            .catch(error => {
                console.error('Error refreshing dashboard:', error);
            });
    }

    function updateDashboardStats(data) {
        // Update stat widgets
        Object.keys(data).forEach(function(key) {
            const element = document.getElementById(key);
            if (element) {
                element.textContent = data[key];
            }
        });
    }

    // DataTables initialization
    window.initializeDataTable = function(tableId, options = {}) {
        const defaultOptions = {
            responsive: true,
            language: {
                url: '//cdn.datatables.net/plug-ins/1.11.5/i18n/fr-FR.json'
            },
            pageLength: 25,
            order: [[0, 'desc']]
        };

        const finalOptions = Object.assign(defaultOptions, options);

        return $('#' + tableId).DataTable(finalOptions);
    };

    // Modal helpers
    window.showModal = function(modalId, data = {}) {
        const modal = new bootstrap.Modal(document.getElementById(modalId));

        // Populate modal with data
        Object.keys(data).forEach(function(key) {
            const element = document.getElementById(key);
            if (element) {
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                    element.value = data[key];
                } else {
                    element.textContent = data[key];
                }
            }
        });

        modal.show();
    };

    // File upload preview
    window.previewFile = function(input, previewId) {
        const file = input.files[0];
        const preview = document.getElementById(previewId);

        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                if (file.type.startsWith('image/')) {
                    preview.innerHTML = `<img src="${e.target.result}" class="img-fluid" style="max-height: 200px;">`;
                } else {
                    preview.innerHTML = `<div class="alert alert-info"><i class="fas fa-file"></i> ${file.name}</div>`;
                }
            };
            reader.readAsDataURL(file);
        }
    };

    // Export functions
    window.exportTable = function(format, tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        if (format === 'csv') {
            exportToCSV(table);
        } else if (format === 'pdf') {
            exportToPDF(table);
        }
    };

    function exportToCSV(table) {
        const rows = Array.from(table.querySelectorAll('tr'));
        const csv = rows.map(row => {
            const cells = Array.from(row.querySelectorAll('td, th'));
            return cells.map(cell => cell.textContent.trim()).join(',');
        }).join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'export.csv';
        a.click();
        URL.revokeObjectURL(url);
    }

})();