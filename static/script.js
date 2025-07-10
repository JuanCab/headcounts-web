document.addEventListener('DOMContentLoaded', function() {
    const writingIntensiveCheckbox = document.getElementById('writingIntensive');
    const online18Checkbox = document.getElementById('online18');
    const mainFields = document.getElementById('mainFields');
    const additionalFilters = document.getElementById('additionalFilters');
    const specialModeInfo = document.getElementById('specialModeInfo');
    const specialModeText = document.getElementById('specialModeText');
    const resetBtn = document.getElementById('resetBtn');
    const form = document.getElementById('courseSearchForm');
    
    // Fields that get disabled in special modes
    const disableableFields = [
        'colleges', 'subjects', 'class_code', 'lasc_number'
    ];
    
    function updateFormState(event) {
        const isWritingIntensive = writingIntensiveCheckbox.checked;
        const isOnline18 = online18Checkbox.checked;
        
        // Mutually exclusive logic - only one special filter can be active
        if (isWritingIntensive && isOnline18) {
            // If both are checked, uncheck the other one (last one wins)
            if (event && event.target === writingIntensiveCheckbox) {
                online18Checkbox.checked = false;
            } else if (event && event.target === online18Checkbox) {
                writingIntensiveCheckbox.checked = false;
            }
        }
        
        const isSpecialMode = writingIntensiveCheckbox.checked || online18Checkbox.checked;
        
        if (isSpecialMode) {
            // Show special mode info
            specialModeInfo.style.display = 'block';
            
            // Update info text
            if (writingIntensiveCheckbox.checked) {
                specialModeText.textContent = 'Searching for Writing Intensive courses - other filters disabled.';
            } else {
                specialModeText.textContent = 'Searching for 18 Online courses - other filters disabled.';
            }
            
            // Disable and clear other fields
            disableableFields.forEach(fieldName => {
                const field = document.getElementById(fieldName) || document.querySelector(`[name="${fieldName}"]`);
                if (field) {
                    field.disabled = true;
                    if (field.tagName === 'SELECT') {
                        field.value = '';
                    } else {
                        field.value = '';
                    }
                }
            });
            
            // Add visual indication
            additionalFilters.classList.add('disabled');
            document.querySelector('.form-section').classList.add('disabled');
            
        } else {
            // Hide special mode info
            specialModeInfo.style.display = 'none';
            
            // Enable all fields
            disableableFields.forEach(fieldName => {
                const field = document.getElementById(fieldName) || document.querySelector(`[name="${fieldName}"]`);
                if (field) {
                    field.disabled = false;
                }
            });
            
            // Remove visual indication
            additionalFilters.classList.remove('disabled');
            document.querySelector('.form-section').classList.remove('disabled');
        }
    }
    
    // Add event listeners for special mode checkboxes with event parameter
    writingIntensiveCheckbox.addEventListener('change', function(event) {
        updateFormState(event);
    });
    online18Checkbox.addEventListener('change', function(event) {
        updateFormState(event);
    });
    
    // Class code validation - require subject selection
    const classCodeField = document.querySelector('[name="class_code"]');
    const subjectsField = document.querySelector('[name="subjects"]');
    
    if (classCodeField && subjectsField) {
        classCodeField.addEventListener('input', function() {
            if (this.value && !subjectsField.value) {
                this.classList.add('is-invalid');
                let feedback = this.parentNode.querySelector('.invalid-feedback');
                if (!feedback) {
                    feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    this.parentNode.appendChild(feedback);
                }
                feedback.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Select a subject when using class codes';
            } else {
                this.classList.remove('is-invalid');
                const feedback = this.parentNode.querySelector('.invalid-feedback');
                if (feedback) {
                    feedback.remove();
                }
            }
        });
    }
    
    // Reset button functionality
    resetBtn.addEventListener('click', function() {
        form.reset();
        
        // Reset to default values
        document.querySelector('[name="semester"]').value = '';
        document.querySelector('[name="year"]').value = '';
        
        updateFormState();
        
        // Clear any validation errors
        document.querySelectorAll('.is-invalid').forEach(field => {
            field.classList.remove('is-invalid');
        });
        document.querySelectorAll('.invalid-feedback').forEach(feedback => {
            feedback.remove();
        });
    });
    
    // Initialize form state
    updateFormState();
    
    form.addEventListener('submit', function(e) {
        // Get values of main filters
        const college = form.colleges ? form.colleges.value : '';
        const subject = form.subjects ? form.subjects.value : '';
        const classCode = form.class_code ? form.class_code.value : '';
        const lasc = form.lasc_number ? form.lasc_number.value : '';
        const semester = form.semester ? form.semester.value : '';
        const year = form.year ? form.year.value : '';
        const writingIntensive = form.writing_intensive ? form.writing_intensive.checked : false;
        const online18 = form.online_18 ? form.online_18.checked : false;

        // If no filters are selected (customize as needed)
        if (
            !college && !subject && !classCode && !lasc &&
            !semester && !year &&
            !writingIntensive && !online18
        ) {
            const proceed = confirm("Showing all courses - apply filters to narrow results. Continue?");
            if (!proceed) {
                e.preventDefault();
            }
        }
    });
});