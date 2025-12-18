// Custom JavaScript for Event Scheduler Application

document.addEventListener('DOMContentLoaded', function() {
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-info):not(.alert-warning)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Form validation helpers
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Check datetime inputs for event forms
            const startTimeInput = form.querySelector('input[name="start_time"]');
            const endTimeInput = form.querySelector('input[name="end_time"]');
            
            if (startTimeInput && endTimeInput) {
                const startTime = new Date(startTimeInput.value);
                const endTime = new Date(endTimeInput.value);
                
                if (startTime >= endTime) {
                    e.preventDefault();
                    alert('Start time must be before end time!');
                    return false;
                }
            }
            
            // Check if at least one resource is selected in allocation form
            const resourceCheckboxes = form.querySelectorAll('input[name="resource_ids"]:checked');
            const eventSelect = form.querySelector('select[name="event_id"]');
            
            if (eventSelect && resourceCheckboxes.length === 0) {
                e.preventDefault();
                alert('Please select at least one resource to allocate!');
                return false;
            }
        });
    });

    // Add confirmation for delete actions
    const deleteForms = document.querySelectorAll('form[action*="delete"]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.hasAttribute('onsubmit')) {
                if (!confirm('Are you sure you want to delete this item?')) {
                    e.preventDefault();
                    return false;
                }
            }
        });
    });

    // Highlight current page in navigation
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
            link.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
            link.style.borderRadius = '5px';
        }
    });

    // Add smooth scrolling for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Date range validation for reports
    const reportForm = document.querySelector('form[action*="report"]');
    if (reportForm) {
        const startDateInput = reportForm.querySelector('input[name="start_date"]');
        const endDateInput = reportForm.querySelector('input[name="end_date"]');
        
        if (startDateInput && endDateInput) {
            // Set default dates if empty
            if (!startDateInput.value) {
                const today = new Date();
                today.setDate(today.getDate() - 7);
                startDateInput.value = today.toISOString().split('T')[0];
            }
            
            if (!endDateInput.value) {
                const today = new Date();
                endDateInput.value = today.toISOString().split('T')[0];
            }
            
            // Validate date range on submit
            reportForm.addEventListener('submit', function(e) {
                const startDate = new Date(startDateInput.value);
                const endDate = new Date(endDateInput.value);
                
                if (startDate > endDate) {
                    e.preventDefault();
                    alert('Start date must be before or equal to end date!');
                    return false;
                }
            });
        }
    }

    // Add tooltips to buttons (if Bootstrap tooltips are needed)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Dynamic event selection preview in allocation form
    const eventSelect = document.querySelector('select[name="event_id"]');
    if (eventSelect) {
        eventSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption.value) {
                console.log('Event selected:', selectedOption.text);
            }
        });
    }

    // Checkbox selection counter for resource allocation
    const resourceCheckboxes = document.querySelectorAll('input[name="resource_ids"]');
    if (resourceCheckboxes.length > 0) {
        const updateCounter = () => {
            const checkedCount = document.querySelectorAll('input[name="resource_ids"]:checked').length;
            let counter = document.querySelector('#resource-counter');
            
            if (!counter) {
                counter = document.createElement('div');
                counter.id = 'resource-counter';
                counter.className = 'alert alert-info mt-2';
                const form = document.querySelector('form[action*="allocate"]');
                if (form) {
                    const cardBody = form.querySelector('.card-body');
                    if (cardBody) {
                        cardBody.appendChild(counter);
                    }
                }
            }
            
            counter.textContent = `${checkedCount} resource(s) selected`;
            counter.style.display = checkedCount > 0 ? 'block' : 'none';
        };
        
        resourceCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateCounter);
        });
    }

    // Print button functionality for reports
    const reportCard = document.querySelector('.card-header.bg-success');
    if (reportCard) {
        const printButton = document.createElement('button');
        printButton.className = 'btn btn-light btn-sm float-end';
        printButton.innerHTML = '<i class="bi bi-printer"></i> Print Report';
        printButton.onclick = () => window.print();
        reportCard.appendChild(printButton);
    }

    console.log('Event Scheduler Application loaded successfully!');
});

// Helper function to format dates
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Helper function to calculate duration
function calculateDuration(startTime, endTime) {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const diff = end - start;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
}
