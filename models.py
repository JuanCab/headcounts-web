from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField
from wtforms.validators import Length, Optional, ValidationError

# College and subject choices for form dropdowns
COLLEGES = [
    ('', 'Select a College'),
    ('CBAC', 'College of Business, Analytics, & Communication'),
    ('COAH', 'College of Arts and Humanities'),
    ('CSHE', 'College of Science, Health, & the Environment'),
    ('CEHS', 'College of Education and Human Services')
]

SUBJECTS = [
            ('', 'Select a Subject'),
            ('ACCT', 'Accounting'),
            ('AEM', 'Audio Production & Entertainment Management'),
            ('AMCS', 'American Multicultural Studies'),
            ('ANIM', 'Animation'),
            ('ANTH', 'Anthropology'),
            ('ART', 'Art'),
            ('AST', 'Astronomy'),
            ('AT', 'Athletic Training'),
            ('ATHL', 'Athletics'),
            ('BCBT', 'Biochemistry and Biotechnology'),
            ('BIOL', 'Biology'),
            ('BUS', 'Business'),
            ('CHEM', 'Chemistry'),
            ('CHIN', 'Chinese'),
            ('CJ', 'Criminal Justice'),
            ('CM', 'Construction Management'),
            ('CNSA', 'Counseling and Student Affairs'),
            ('COMM', 'Communication'),
            ('COUN', 'Counseling'),
            ('CSIS', 'Computer Science & Information Systems'),
            ('ECON', 'Economics'),
            ('ED', 'Education'),
            ('EECE', 'Elementary & Early Childhood Education'),
            ('EIT', 'Entertainment Industries & Technology'),
            ('ENG', 'Engineering'),
            ('ENGL', 'English'),
            ('ENTR', 'Entrepreneurship'),
            ('EXCH', 'Exchange'),
            ('EXS', 'Exercise Science'),
            ('FILM', 'Film Studies'),
            ('FINC', 'Finance'),
            ('FYE', 'First Year Experience'),
            ('GCOM', 'Graphic Communications'),
            ('GDES', 'Graphic Design'),
            ('GEOS', 'Geoscience'),
            ('GID', 'Graphic & Interactive Design'),
            ('HIST', 'History'),
            ('HLTH', 'Health'),
            ('HON', 'Honors'),
            ('HSAD', 'Health Services Administration'),
            ('HUM', 'Humanities'),
            ('INTL', 'International Studies'),
            ('JAPN', 'Japanese'),
            ('LANG', 'Languages'),
            ('LEAD', 'Leadership'),
            ('LIB', 'Library'),
            ('MATH', 'Mathematics'),
            ('MBA', 'Masters of Business Administration'),
            ('MGMT', 'Management'),
            ('MHA', 'Masters of Healthcare Administration'),
            ('MKTG', 'Marketing'),
            ('MUS', 'Music'),
            ('NURS', 'Nursing'),
            ('OM', 'Operations Management'),
            ('PARA', 'Paralegal'),
            ('PE', 'Physical Education'),
            ('PHIL', 'Philosophy'),
            ('PHO', 'Photography'),
            ('PHYS', 'Physics'),
            ('PMGT', 'Professional Management'),
            ('POL', 'Political Science'),
            ('PSCI', 'Physical Science'),
            ('PSY', 'Psychology'),
            ('SLHS', 'Speech/Language/Hearing Science'),
            ('SLP', 'Speech and Language Pathology'),
            ('SOC', 'Sociology'),
            ('SPAN', 'Spanish'),
            ('SPED', 'Special Education'),
            ('STL', 'School of Teaching and Learning'),
            ('SUST', 'Sustainability'),
            ('SW', 'Social Work'),
            ('TEFL', 'Teaching English as a Foreign Language'),
            ('TESL', 'Teaching English as a Second Language'),
            ('THTR', 'Theatre Arts'),
            ('UNIV', 'University Studies'),
            ('WS', 'Women\'s Studies')
        ]

# Year choices for the form (latest year first)
YEAR_CHOICES = [('', 'All Years')] + [(str(year + 1), str(year)) for year in range(2014, 2026)]
YEAR_CHOICES[1:] = YEAR_CHOICES[1:][::-1]

class SearchForm(FlaskForm):
    """Form for searching courses with various filters."""
    writing_intensive = BooleanField('Writing Intensive', default=False)
    online_18 = BooleanField('18 Online Courses', default=False)

    colleges = SelectField(
        'Colleges',
        choices=COLLEGES,
        validators=[Optional()],
        default=''
    )
    subjects = SelectField(
        'Subjects',
        choices=SUBJECTS,
        validators=[Optional()],
        default=''
    )
    class_code = StringField(
        'Class Code',
        validators=[Optional(), Length(min=3, max=4, message="Class code must be 3-4 characters")],
        render_kw={"placeholder": "e.g., 241"}
    )
    lasc_number = SelectField(
        'LASC Area',
        choices=[('', 'Select LASC Area')] + [(str(i), str(i)) for i in range(1, 11)],
        validators=[Optional()],
        default=''
    )
    
    # Time period fields (always active)
    semester = SelectField(
        'Semester',
        choices=[
            ('', 'All'),
            ('Fall', 'Fall'),
            ('Summer', 'Summer'),
            ('Spring', 'Spring')
        ],
        validators=[Optional()],
        default=''
    )
    year = SelectField(
        'Year',
        choices=YEAR_CHOICES,
        validators=[Optional()],
        default=''
    )

    def validate(self, extra_validators=None):
        """Custom validation for form fields."""
        if not super().validate(extra_validators):
            return False
        
        # Check for Spring 2014 - we don't have data for this
        if self.semester.data == 'Spring' and self.year.data == '2015':
            self.semester.errors.append('Spring 2014 data is not available. Data starts from Fall 2014.')
            return False
        
        # Class codes require subject selection
        if self.class_code.data and not self.subjects.data:
            self.subjects.errors.append('Select a subject when using class codes')
            return False
        return True

    def has_filters(self):
        """Check if any meaningful filters are applied."""
        return any([
            self.writing_intensive.data,
            self.online_18.data,
            self.colleges.data,
            self.subjects.data,
            self.class_code.data,
            self.lasc_number.data,
            self.semester.data,
            self.year.data
        ])

    def is_special_mode(self):
        """Check if special mode filters are active."""
        return self.writing_intensive.data or self.online_18.data