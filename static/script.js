document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('courseSearchForm');
    const resetBtn = document.getElementById('resetBtn');
    const subjectOrCollege = document.getElementById('subject_or_college');
    const classCodeContainer = document.getElementById('classCodeContainer');
    const primaryRow = document.querySelector('.form-section .row');
    const termField = document.getElementById('term');

    // Invalid values that should not show class code field
    const invalidValues = [
        '', '_', '── COLLEGES ──', '── SUBJECTS ──',
        'CBAC', 'COAH', 'CSHE', 'CEHS', 'all'
    ];
    
    function isValidSubject(value) {
        return value && 
               !invalidValues.includes(value) && 
               value.length <= 5 &&
               !value.includes('──');
    }

    // Prevent selection of disabled options
    function preventDividerSelection() {
        if (subjectOrCollege) {
            const selectedOption = subjectOrCollege.options[subjectOrCollege.selectedIndex];
            if (selectedOption && selectedOption.disabled) {
                // Reset to default if divider is somehow selected
                subjectOrCollege.value = '';
                updateClassCodeVisibility();
            }
        }
    }

    // Clear field errors and styling
    function clearFieldErrors(field) {
        if (!field) return;
        
        // Remove error styling
        field.classList.remove('is-invalid');
        
        // Remove error messages
        const errorContainer = field.parentNode.querySelector('.invalid-feedback');
        if (errorContainer) {
            errorContainer.remove();
        }
    }

    // Real-time validation for class code
    function validateClassCode() {
        const classCodeField = document.getElementById('class_code');
        if (!classCodeField) return;
        
        const value = classCodeField.value.trim();
        
        // Clear previous errors
        clearFieldErrors(classCodeField);
        
        // Validate length if there's a value
        if (value && (value.length < 3 || value.length > 4)) {
            classCodeField.classList.add('is-invalid');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Class code must be 3-4 characters';
            classCodeField.parentNode.appendChild(errorDiv);
        }
        
        // Validate subject selection if class code is provided
        if (value && (!subjectOrCollege.value || subjectOrCollege.value === '')) {
            subjectOrCollege.classList.add('is-invalid');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Select a subject when using class codes';
            subjectOrCollege.parentNode.appendChild(errorDiv);
        }
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
            
            // Clear all validation errors
            document.querySelectorAll('.is-invalid').forEach(field => {
                clearFieldErrors(field);
            });
        });
    }

    // Course type change handler
    const courseTypeField = document.getElementById('course_type');
    if (courseTypeField) {
        courseTypeField.addEventListener('change', function() {
            // Auto-reset subject/college if course type is selected
            if (courseTypeField.value && courseTypeField.value !== '') {
                subjectOrCollege.value = '';
                updateClassCodeVisibility();
                clearFieldErrors(subjectOrCollege);
            }
            
            // Clear any existing errors for this field
            clearFieldErrors(courseTypeField);
        });
    }

    // Class code real-time validation
    const classCodeField = document.getElementById('class_code');
    if (classCodeField) {
        classCodeField.addEventListener('input', validateClassCode);
        classCodeField.addEventListener('blur', validateClassCode);
    }

    // Term field real-time error clearing
    if (termField) {
        termField.addEventListener('change', function() {
            clearFieldErrors(termField);

            const termValue = termField.value.trim();
            const subjectOrCollegeValue = subjectOrCollege ? subjectOrCollege.value.trim() : "";
            const courseTypeValue = courseTypeField ? courseTypeField.value.trim() : "";
            const allOption = Array.from(subjectOrCollege.options).find(opt => opt.value === "all");

            if (
                termValue !== "" && 
                (!subjectOrCollegeValue || subjectOrCollegeValue === "") &&
                (!courseTypeValue || courseTypeValue === "")
            ) {
                if (allOption) {
                    subjectOrCollege.value = "all";
                    updateClassCodeVisibility();
                    clearFieldErrors(subjectOrCollege);
                }
            }
        });
    }

    // Subject/College change handler
    if (subjectOrCollege) {
        subjectOrCollege.addEventListener('change', function() {
            preventDividerSelection();
            updateClassCodeVisibility();
            
            // Auto-reset course type if subject/college is selected
            if (courseTypeField && subjectOrCollege.value && subjectOrCollege.value !== '') {
                courseTypeField.value = '';
                clearFieldErrors(courseTypeField);
            }
            
            // Clear any existing errors for this field
            clearFieldErrors(subjectOrCollege);
        });
        // Initialize on page load
        preventDividerSelection();
        updateClassCodeVisibility();
    }

    // Form submission validation
    form.addEventListener('submit', function(e) {
        validateClassCode();

        const subjectOrCollegeValue = subjectOrCollege ? subjectOrCollege.value.trim() : "";
        const termValue = termField ? termField.value.trim() : "";
        const courseTypeValue = courseTypeField ? courseTypeField.value.trim() : "";
        const allTermsValue = ""; 
        const allSubjectValue = "all"; 

        if (
            termValue === allTermsValue &&
            (subjectOrCollegeValue === "" || subjectOrCollegeValue === allSubjectValue) &&
            (!courseTypeValue || courseTypeValue === "")
        ) {
            const proceed = confirm("Showing all courses - apply filters to narrow results. Continue?");
            if (!proceed) {
                e.preventDefault();
                return;
            }
        }
        
        const subjectOrCollegeValue2 = subjectOrCollege ? subjectOrCollege.value.trim() : "";
        const courseTypeValue2 = courseTypeField ? courseTypeField.value.trim() : "";
        const termValue2 = termField ? termField.value.trim() : "";
        const allOption = Array.from(subjectOrCollege.options).find(opt => opt.value === "all");


        if (
            termValue2 && termValue2 !== "" && termValue2 !== termField.options[0].value &&
            (!subjectOrCollegeValue2 || subjectOrCollegeValue2 === "") &&
            (!courseTypeValue2 || courseTypeValue2 === "")
        ) {
            if (allOption) {
                subjectOrCollege.value = "all";
                updateClassCodeVisibility();
                clearFieldErrors(subjectOrCollege);
            }
        }
    });
});
