from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import Length, Optional, ValidationError
from datetime import datetime

# College and subject choices for form dropdowns
COLLEGES = [
    ('', 'Select College or Subject'),
    ('', '── COLLEGES ──'),
    ('CBAC', 'College of Business, Analytics, & Communication'),
    ('COAH', 'College of Arts and Humanities'),
    ('CSHE', 'College of Science, Health, & the Environment'),
    ('CEHS', 'College of Education and Human Services')
]

SUBJECTS = [
    ('', '── SUBJECTS ──'),
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

YEAR_CHOICES = [('', 'All Years')] + [(str(year + 1), str(year)) for year in range(datetime.now().year, 2013, -1)]

COURSE_TYPES = [
    ('', 'Select Course Type'),
    ('lasc/1', 'Area 1 - Communication'),
    ('lasc/1a', 'Area 1A - Oral Communication'),
    ('lasc/1b', 'Area 1B - Written Communication'),
    ('lasc/2', 'Area 2 - Critical Thinking'),
    ('lasc/3', 'Area 3 - Natural Sciences'),
    ('lasc/3l', 'Area 3L - Natural Sciences with Lab'),
    ('lasc/4', 'Area 4 - Mathematical/Logical Reasoning'),
    ('lasc/5', 'Area 5 - History and Social Sciences'),
    ('lasc/6', 'Area 6 - Humanities and Fine Arts'),
    ('lasc/7', 'Area 7 - Human Diversity'),
    ('lasc/8', 'Area 8 - Global Perspective'),
    ('lasc/9', 'Area 9 - Ethical/Civic Responsibility'),
    ('lasc/10', 'Area 10 - People and the Environment'),
    ('wi', 'Writing Intensive (WI)'),
    ('18', '18-Online')
]


class SearchForm(FlaskForm):
    """Form for searching courses with various filters."""
    
    # Combined Subject/College dropdown
    subject_or_college = SelectField(
        'Subject or College',
        choices=COLLEGES + SUBJECTS,
        validators=[Optional()],
        default=COLLEGES[0][0] 
    )
    
    # Combined Course Type dropdown (LASC, WI, 18-Online)
    course_type = SelectField(
        'Course Type',
        choices=COURSE_TYPES,
        validators=[Optional()],
        default=''
    )
    
    # Class code field
    class_code = StringField(
        'Class Code',
        validators=[Optional(), Length(min=3, max=4, message="Class code must be 3-4 characters")],
        render_kw={"placeholder": "e.g., 241"}
    )
    
    # Time period fields
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
        
        # Mutual exclusion rule: cannot select both subject_or_college and course_type
        if self.subject_or_college.data and self.course_type.data:
            self.subject_or_college.errors.append('Cannot select both Subject/College and Course Type. Please choose one or the other.')
            self.course_type.errors.append('Cannot select both Subject/College and Course Type. Please choose one or the other.')
            return False
        
        # Class code validation: requires subject selection (not college)
        if self.class_code.data:
            if not self.subject_or_college.data:
                self.subject_or_college.errors.append('Select a subject when using class codes')
                return False
            
            # Check if selection is from subjects section (not colleges or headers)
            if self.subject_or_college.data in ['__COLLEGES__', '__SUBJECTS__']:
                self.subject_or_college.errors.append('Invalid selection. Please select a specific subject or college.')
                return False
            
            # Check if it's a college (not allowed with class codes)
            college_codes = [code for code, _ in COLLEGES]
            if self.subject_or_college.data in college_codes:
                self.subject_or_college.errors.append('Class codes require a subject selection, not a college')
                return False
        
        return True

    def has_filters(self):
        """Check if any meaningful filters are applied."""
        return any([
            self.subject_or_college.data,
            self.course_type.data,
            self.class_code.data,
            self.semester.data,
            self.year.data
        ])
