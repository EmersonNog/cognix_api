DEFAULT_STUDY_DAYS_PER_WEEK = 5
DEFAULT_MINUTES_PER_DAY = 60
DEFAULT_WEEKLY_QUESTIONS_GOAL = 80
DEFAULT_FOCUS_MODE = 'constancia'
DEFAULT_PREFERRED_PERIOD = 'flexivel'
MAX_PRIORITY_DISCIPLINES = 4

ALLOWED_FOCUS_MODES = (
    'constancia',
    'revisao',
    'desempenho',
)

ALLOWED_PREFERRED_PERIODS = (
    'manha',
    'tarde',
    'noite',
    'flexivel',
)

FOCUS_PROGRESS_WEIGHTS = {
    'constancia': {
        'days': 0.5,
        'minutes': 0.3,
        'questions': 0.2,
    },
    'revisao': {
        'days': 0.3,
        'minutes': 0.45,
        'questions': 0.25,
    },
    'desempenho': {
        'days': 0.2,
        'minutes': 0.3,
        'questions': 0.5,
    },
}
