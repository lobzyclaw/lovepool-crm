// Love Pool Care CRM - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Confirm before closing deals
    const closeForms = document.querySelectorAll('.close-deal-form');
    closeForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!confirm('Are you sure you want to close this deal?')) {
                e.preventDefault();
            }
        });
    });

    // Stage change confirmation
    const stageSelects = document.querySelectorAll('.stage-select');
    stageSelects.forEach(select => {
        select.addEventListener('change', function() {
            const form = this.closest('form');
            if (form && this.dataset.confirm) {
                if (confirm('Change deal stage?')) {
                    form.submit();
                } else {
                    this.value = this.dataset.original;
                }
            }
        });
    });

    // Search debounce
    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        let timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                const form = this.closest('form');
                if (form && form.dataset.autoSubmit) {
                    form.submit();
                }
            }, 500);
        });
    });

    // Activity form toggle
    const activityToggle = document.querySelector('.activity-toggle');
    const activityForm = document.querySelector('.activity-form');
    if (activityToggle && activityForm) {
        activityToggle.addEventListener('click', function() {
            activityForm.classList.toggle('hidden');
        });
    }

    // Deal value formatting
    const valueInputs = document.querySelectorAll('input[name="value"]');
    valueInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = parseFloat(this.value);
            if (!isNaN(value)) {
                this.value = value.toFixed(2);
            }
        });
    });

    // Phone formatting
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length >= 10) {
                value = value.substring(0, 10);
                const formatted = `(${value.substring(0, 3)}) ${value.substring(3, 6)}-${value.substring(6)}`;
                e.target.value = formatted;
            }
        });
    });
});

// API helper functions
const CRM = {
    async searchContacts(query, limit = 20) {
        const response = await fetch(`/api/contacts/search?q=${encodeURIComponent(query)}&limit=${limit}`);
        return response.json();
    },

    async addActivity(data) {
        const response = await fetch('/api/activities', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    },

    async getReferenceData() {
        const response = await fetch('/api/reference');
        return response.json();
    },

    formatCurrency(value) {
        if (!value) return '—';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0
        }).format(value);
    },

    formatDate(dateString) {
        if (!dateString) return '—';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    }
};

// Drag and drop for kanban (future enhancement)
function initKanbanDragDrop() {
    const cards = document.querySelectorAll('.deal-card');
    const columns = document.querySelectorAll('.kanban-column');

    cards.forEach(card => {
        card.draggable = true;
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragend', handleDragEnd);
    });

    columns.forEach(column => {
        column.addEventListener('dragover', handleDragOver);
        column.addEventListener('drop', handleDrop);
    });
}

function handleDragStart(e) {
    e.dataTransfer.setData('text/plain', e.target.dataset.dealId);
    e.target.classList.add('dragging');
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
}

function handleDragOver(e) {
    e.preventDefault();
}

function handleDrop(e) {
    e.preventDefault();
    const dealId = e.dataTransfer.getData('text/plain');
    const newStage = e.currentTarget.dataset.stage;
    
    if (dealId && newStage) {
        // Submit form to update stage
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/deals/${dealId}/update_stage`;
        form.innerHTML = `<input type="hidden" name="stage" value="${newStage}">`;
        document.body.appendChild(form);
        form.submit();
    }
}

// Initialize kanban if on pipeline page
if (document.querySelector('.kanban-board')) {
    // initKanbanDragDrop(); // Uncomment when ready
}