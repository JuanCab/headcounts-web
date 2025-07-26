document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('courseSearchForm');
    const resetBtn = document.getElementById('resetBtn');
    const subjectOrCollege = document.getElementById('subject_or_college');
    const classCodeContainer = document.getElementById('classCodeContainer');
    const primaryRow = document.querySelector('.form-section .row');
    const semesterField = document.getElementById('semester');
    const yearField = document.getElementById('year');

    // Invalid values that should not show class code field
    const invalidValues = [
        '', '_', '── COLLEGES ──', '── SUBJECTS ──',
        'CBAC', 'COAH', 'CSHE', 'CEHS'
    ];
    
    function isValidSubject(value) {
        return value && 
               !invalidValues.includes(value) && 
               value.length <= 5 &&
               !value.includes('──');
    }

    function updateClassCodeVisibility() {
        if (!subjectOrCollege || !classCodeContainer) return;
        
        const isValid = isValidSubject(subjectOrCollege.value);
        
        if (isValid) {
            classCodeContainer.classList.add('show');
            primaryRow.classList.add('has-class-code');
        } else {
            classCodeContainer.classList.remove('show');
            primaryRow.classList.remove('has-class-code');
            // Clear class code when hiding
            const classCodeField = document.getElementById('class_code');
            if (classCodeField) {
                classCodeField.value = '';
            }
        }
    }

    // Reset button functionality
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            form.reset();
            updateClassCodeVisibility();
            
            // Clear validation errors
            document.querySelectorAll('.is-invalid').forEach(field => {
                field.classList.remove('is-invalid');
            });
            document.querySelectorAll('.invalid-feedback').forEach(feedback => {
                feedback.remove();
            });
        });
    }

    // Subject/College change handler
    if (subjectOrCollege) {
        subjectOrCollege.addEventListener('change', updateClassCodeVisibility);
        // Initialize on page load
        updateClassCodeVisibility();
    }

    // Form submission validation
    form.addEventListener('submit', function(e) {
        // Apply time period rule only on form submission
        if (semesterField && yearField) {
            if (semesterField.value === '' || yearField.value === '') {
                semesterField.value = '';
                yearField.value = '';
            }
        }

        const hasAnyFilter = Array.from(form.elements).some(element => {
            if (element.type === 'checkbox') return element.checked;
            if (element.type === 'select-one' || element.type === 'text') return element.value.trim();
            return false;
        });

        if (!hasAnyFilter) {
            const proceed = confirm("Showing all courses - apply filters to narrow results. Continue?");
            if (!proceed) {
                e.preventDefault();
            }
        }
    });
});
