document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('courseSearchForm');
    const resetBtn = document.getElementById('resetBtn');
    const subjectOrCollege = document.getElementById('subject_or_college');
    const classCodeContainer = document.getElementById('classCodeContainer');
    const primaryRow = document.getElementById('primaryRow');
    const termField = document.getElementById('term');
    const courseTypeField = document.getElementById('course_type');
    const subjectPanel = document.getElementById('subjectPanel');
    const courseTypePanel = document.getElementById('courseTypePanel');
    const modeRadios = document.querySelectorAll('input[name="search_mode"]');

    // Values that are NOT real course subject rubrics — selecting these should
    // not reveal the class-code input.
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

    // Returns which radio is currently checked ('subject' or 'course_type').
    function currentMode() {
        const checked = document.querySelector('input[name="search_mode"]:checked');
        return checked ? checked.value : 'subject';
    }

    // Removes the red border and all inline error messages from a field.
    function clearFieldErrors(field) {
        if (!field) return;
        field.classList.remove('is-invalid');
        field.parentNode.querySelectorAll('.invalid-feedback').forEach(el => el.remove());
    }

    // Resets the subject dropdown if keyboard navigation lands on a disabled
    // divider option (some browsers allow this).
    function preventDividerSelection() {
        if (subjectOrCollege) {
            const selectedOption = subjectOrCollege.options[subjectOrCollege.selectedIndex];
            if (selectedOption && selectedOption.disabled) {
                subjectOrCollege.value = '';
                updateClassCodeVisibility();
            }
        }
    }

    // Shows or hides the class-code input depending on whether a real subject
    // rubric (not a college or sentinel value) is selected.
    function updateClassCodeVisibility() {
        if (!subjectOrCollege || !classCodeContainer) return;
        const isValid = isValidSubject(subjectOrCollege.value);
        if (isValid) {
            classCodeContainer.classList.add('show');
            primaryRow.classList.add('has-class-code');
        } else {
            classCodeContainer.classList.remove('show');
            primaryRow.classList.remove('has-class-code');
            const classCodeField = document.getElementById('class_code');
            if (classCodeField) classCodeField.value = '';
        }
    }

    // Validates the class-code field: must be 3-4 characters, and a subject
    // must be selected if a code is entered.
    function validateClassCode() {
        const classCodeField = document.getElementById('class_code');
        if (!classCodeField) return;
        const value = classCodeField.value.trim();

        // Nothing entered — clear any stale errors and stop.
        if (!value) {
            clearFieldErrors(classCodeField);
            clearFieldErrors(subjectOrCollege);
            return;
        }

        clearFieldErrors(classCodeField);
        clearFieldErrors(subjectOrCollege);

        if (value.length < 3 || value.length > 4) {
            classCodeField.classList.add('is-invalid');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Class code must be 3-4 characters';
            classCodeField.parentNode.appendChild(errorDiv);
        }

        if (!subjectOrCollege.value || subjectOrCollege.value === '') {
            subjectOrCollege.classList.add('is-invalid');
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Select a subject when using class codes';
            subjectOrCollege.parentNode.appendChild(errorDiv);
        }
    }

    // Shows the active panel and hides the inactive one, clearing the hidden
    // panel's fields so stale values aren't submitted silently.
    function switchMode(mode) {
        if (mode === 'subject') {
            subjectPanel.classList.remove('search-mode-panel--hidden');
            courseTypePanel.classList.add('search-mode-panel--hidden');
            if (courseTypeField) {
                courseTypeField.value = '';
                clearFieldErrors(courseTypeField);
            }
        } else {
            courseTypePanel.classList.remove('search-mode-panel--hidden');
            subjectPanel.classList.add('search-mode-panel--hidden');
            if (subjectOrCollege) {
                subjectOrCollege.value = '';
                clearFieldErrors(subjectOrCollege);
            }
            const classCodeField = document.getElementById('class_code');
            if (classCodeField) {
                classCodeField.value = '';
                clearFieldErrors(classCodeField);
            }
            updateClassCodeVisibility();
        }
    }

    // Switch mode when a radio is clicked.
    modeRadios.forEach(function(radio) {
        radio.addEventListener('change', function() {
            switchMode(this.value);
        });
    });

    // Subject/College change handler.
    if (subjectOrCollege) {
        subjectOrCollege.addEventListener('change', function() {
            preventDividerSelection();
            updateClassCodeVisibility();
            clearFieldErrors(subjectOrCollege);
        });
        preventDividerSelection();
        updateClassCodeVisibility();
    }

    // Class code real-time validation.
    const classCodeField = document.getElementById('class_code');
    if (classCodeField) {
        classCodeField.addEventListener('input', validateClassCode);
        classCodeField.addEventListener('blur', validateClassCode);
    }

    // Term field: when a term is picked in subject mode with no subject
    // selected, auto-default to "All Subjects" so the query is valid.
    if (termField) {
        termField.addEventListener('change', function() {
            clearFieldErrors(termField);
            if (currentMode() !== 'subject') return;

            const termValue = termField.value.trim();
            const subjectOrCollegeValue = subjectOrCollege ? subjectOrCollege.value.trim() : "";
            const allOption = Array.from(subjectOrCollege.options).find(opt => opt.value === "all");

            if (termValue !== "" && (!subjectOrCollegeValue || subjectOrCollegeValue === "")) {
                if (allOption) {
                    subjectOrCollege.value = "all";
                    updateClassCodeVisibility();
                    clearFieldErrors(subjectOrCollege);
                }
            }
        });
    }

    // Reset button: form.reset() restores the radio to its default (subject),
    // so we call switchMode to sync the panels to match.
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            form.reset();
            switchMode('subject');
            updateClassCodeVisibility();
            document.querySelectorAll('.is-invalid').forEach(function(field) {
                clearFieldErrors(field);
            });
        });
    }

    // Form submission.
    form.addEventListener('submit', function(e) {
        // Only validate class code when the subject panel is active.
        if (currentMode() === 'subject') {
            validateClassCode();
        }

        const subjectOrCollegeValue = subjectOrCollege ? subjectOrCollege.value.trim() : "";
        const termValue = termField ? termField.value.trim() : "";
        const courseTypeValue = courseTypeField ? courseTypeField.value.trim() : "";

        // Warn before submitting a completely unfiltered query.
        if (
            termValue === "" &&
            (subjectOrCollegeValue === "" || subjectOrCollegeValue === "all") &&
            (!courseTypeValue || courseTypeValue === "")
        ) {
            const proceed = confirm("Showing all courses - apply filters to narrow results. Continue?");
            if (!proceed) {
                e.preventDefault();
                return;
            }
        }

        // In subject mode, auto-select "all" if a non-default term is chosen
        // but subject is still blank (handles submit without using the term
        // change handler, e.g. keyboard submit).
        if (currentMode() === 'subject') {
            const termValue2 = termField ? termField.value.trim() : "";
            const subjectOrCollegeValue2 = subjectOrCollege ? subjectOrCollege.value.trim() : "";
            const allOption = Array.from(subjectOrCollege.options).find(opt => opt.value === "all");

            if (
                termValue2 && termValue2 !== "" && termValue2 !== termField.options[0].value &&
                (!subjectOrCollegeValue2 || subjectOrCollegeValue2 === "")
            ) {
                if (allOption) {
                    subjectOrCollege.value = "all";
                    updateClassCodeVisibility();
                    clearFieldErrors(subjectOrCollege);
                }
            }
        }
    });

    // Initialize panels to match whichever radio is checked on page load.
    // This handles browser back-navigation restoring form state.
    switchMode(currentMode());
});

// Notice dismiss handler — uses event delegation so it works for notices
// injected into the DOM after page load (e.g. Flask flash messages).
document.addEventListener('click', function(e) {
    if (e.target.matches('[data-dismiss="notice"]')) {
        e.target.closest('.notice').remove();
    }
});
