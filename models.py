from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import Length, Optional, ValidationError
from config_terms import SEMESTERS_LIST

# College and subject choices for form dropdowns
COLLEGES = [
    ("", "Select College or Subject"),
    ("all", "All"),  
    ("_", "── COLLEGES ──", {"disabled": True}),
    ("CBAC", "College of Business, Analytics, & Communication"),
    ("COAH", "College of Arts and Humanities"),
    ("CSHE", "College of Science, Health, & the Environment"),
    ("CEHS", "College of Education and Human Services"),
]

SUBJECTS = [
    ("_", "── SUBJECTS ──", {"disabled": True}),
    ("ACCT", "Accounting"),
    ("AEM", "Audio Production & Entertainment Management"),
    ("AMCS", "American Multicultural Studies"),
    ("ANIM", "Animation"),
    ("ANTH", "Anthropology"),
    ("ART", "Art"),
    ("AST", "Astronomy"),
    ("AT", "Athletic Training"),
    ("ATHL", "Athletics"),
    ("BCBT", "Biochemistry and Biotechnology"),
    ("BIOL", "Biology"),
    ("BUS", "Business"),
    ("CHEM", "Chemistry"),
    ("CHIN", "Chinese"),
    ("CJ", "Criminal Justice"),
    ("CM", "Construction Management"),
    ("CNSA", "Counseling and Student Affairs"),
    ("COMM", "Communication"),
    ("COUN", "Counseling"),
    ("CSIS", "Computer Science & Information Systems"),
    ("ECON", "Economics"),
    ("ED", "Education"),
    ("EECE", "Elementary & Early Childhood Education"),
    ("EIT", "Entertainment Industries & Technology"),
    ("ENG", "Engineering"),
    ("ENGL", "English"),
    ("ENTR", "Entrepreneurship"),
    ("EXCH", "Exchange"),
    ("EXS", "Exercise Science"),
    ("FILM", "Film Studies"),
    ("FINC", "Finance"),
    ("FYE", "First Year Experience"),
    ("GCOM", "Graphic Communications"),
    ("GDES", "Graphic Design"),
    ("GEOS", "Geoscience"),
    ("GID", "Graphic & Interactive Design"),
    ("HIST", "History"),
    ("HLTH", "Health"),
    ("HON", "Honors"),
    ("HSAD", "Health Services Administration"),
    ("HUM", "Humanities"),
    ("INTL", "International Studies"),
    ("JAPN", "Japanese"),
    ("LANG", "Languages"),
    ("LEAD", "Leadership"),
    ("LIB", "Library"),
    ("MATH", "Mathematics"),
    ("MBA", "Masters of Business Administration"),
    ("MGMT", "Management"),
    ("MHA", "Masters of Healthcare Administration"),
    ("MKTG", "Marketing"),
    ("MUS", "Music"),
    ("NURS", "Nursing"),
    ("OM", "Operations Management"),
    ("PARA", "Paralegal"),
    ("PE", "Physical Education"),
    ("PHIL", "Philosophy"),
    ("PHO", "Photography"),
    ("PHYS", "Physics"),
    ("PMGT", "Professional Management"),
    ("POL", "Political Science"),
    ("PSCI", "Physical Science"),
    ("PSY", "Psychology"),
    ("SLHS", "Speech/Language/Hearing Science"),
    ("SLP", "Speech and Language Pathology"),
    ("SOC", "Sociology"),
    ("SPAN", "Spanish"),
    ("SPED", "Special Education"),
    ("STL", "School of Teaching and Learning"),
    ("SUST", "Sustainability"),
    ("SW", "Social Work"),
    ("TEFL", "Teaching English as a Foreign Language"),
    ("TESL", "Teaching English as a Second Language"),
    ("THTR", "Theatre Arts"),
    ("UNIV", "University Studies"),
    ("WS", "Women's Studies"),
]


# LASC Area 7A and 7B are to be recently added. When added, uncomment them. 
COURSE_TYPES = [
    ("", "Select Course Type"),
    ("lasc", "All LASC Areas"),
    ("lasc/1", "Area 1 - Communication"),
    ("lasc/1a", "Area 1A - Oral Communication"),
    ("lasc/1b", "Area 1B - Written Communication"),
    ("lasc/2", "Area 2 - Critical Thinking"),
    ("lasc/3", "Area 3 - Natural Sciences"),
    ("lasc/3l", "Area 3L - Natural Sciences with Lab"),
    ("lasc/4", "Area 4 - Mathematical/Logical Reasoning"),
    ("lasc/5", "Area 5 - History and Social Sciences"),
    ("lasc/6", "Area 6 - Humanities and Fine Arts"),
    ("lasc/7", "Area 7 - Human Diversity"),
    # ("lasc/7a", "Area 7A - Human Diversity"),
    # ("lasc/7b", "Area 7B - Race/Power/Justice"),
    ("lasc/8", "Area 8 - Global Perspective"),
    ("lasc/9", "Area 9 - Ethical/Civic Responsibility"),
    ("lasc/10", "Area 10 - People and the Environment"),
    ("wi", "Writing Intensive (WI)"),
    ("18online", "18-Online"),
]


class SearchForm(FlaskForm):
    """Form for searching courses with various filters."""

    # Combined Subject/College dropdown
    subject_or_college = SelectField(
        "Subject or College",
        choices=COLLEGES + SUBJECTS,
        validators=[Optional()],
        default=COLLEGES[0],
    )

    # Combined Course Type dropdown (LASC, WI, 18-Online)
    course_type = SelectField(
        "Course Type (LASC/WI/18-Online)",
        choices=COURSE_TYPES,
        validators=[Optional()],
        default="",
    )

    # Class code field
    class_code = StringField(
        "Class Code",
        validators=[
            Optional(),
            Length(min=3, max=4, message="Class code must be 3-4 characters"),
        ],
        render_kw={"placeholder": "e.g., 241"},
    )

    term = SelectField(
        "Term",
        choices= [("", "All Terms")] + SEMESTERS_LIST,
        validators=[Optional()],
        default=SEMESTERS_LIST[0][0],
    )

    def validate(self, extra_validators=None):
        """Custom validation for form fields."""
        if not super().validate(extra_validators):
            return False

        # If selected subject_or_college is a divider (shouldn't happen with disabled options, but good to check)
        if self.subject_or_college.data == "_":
            self.subject_or_college.errors.append(
                "Please select a valid subject or college, not a divider."
            )
            return False

        # Mutual exclusion rule: cannot select both subject_or_college and course_type
        # (This should be handled by frontend auto-reset, but keep as fallback)
        if self.subject_or_college.data and self.course_type.data:
            # Auto-reset course_type to favor subject/college selection
            self.course_type.data = ""

        # Class code validation: requires subject selection (not college)
        if self.class_code.data:
            if not self.subject_or_college.data:
                self.subject_or_college.errors.append(
                    "Select a subject when using class codes"
                )
                return False

            # Check if selection is a divider (shouldn't happen with disabled options, but good to check)
            if self.subject_or_college.data == "_":
                self.subject_or_college.errors.append(
                    "Invalid selection. Please select a specific subject or college, not a divider."
                )
                return False

            # Check if it's a college (not allowed with class codes)
            college_codes = [c[0] for c in COLLEGES]
            if self.subject_or_college.data in college_codes:
                self.subject_or_college.errors.append(
                    "Class codes require a subject selection, not a college"
                )
                return False
        return True

    def has_filters(self):
        """Check if any meaningful filters are applied."""
        return any(
            [
                self.subject_or_college.data,
                self.course_type.data,
                self.class_code.data,
                self.term.data,
            ]
        )
