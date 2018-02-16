from .utils import min_digits, max_digits
from .message import Message

class Patient(Message):
    class Meta:
        schema = {
            # Sex
            #
            # Sex of patient.
            'sex': {
                'type': 'string',
                'allowed': ('M', 'F'),
                'required': True,
            },

            # Date of birth
            #
            # Patient's date of birth.
            'date_of_birth': {
                'type': 'date',
                'required': True,
            },

            # Patient's title
            #
            # (eg. "Mr")
            'title': {
                'type': 'string',
                'minlength': 1,
                'maxlength': 4,
                'required': False,
            },

            # Patient forename
            #
            # First forename.
            'forename': {
                'type': 'string',
                'minlength': 2,
                'maxlength': 20,
                'required': True,
            },

            # Patient surname
            #
            # Surname of patient.
            'surname': {
                'type': 'string',
                'minlength': 2,
                'maxlength': 20,
                'required': True,
            },

            # Previous surname
            #
            'previous_surname': {
                'type': 'string',
                'minlength': 2,
                'maxlength': 20,
                'required': False,
            },

            # NHS number
            #
            # The patient's unique new NHS number.
            'nhs_number': {
                'type': 'number',
                'minlength': min_digits(1),
                'maxlength': max_digits(17),
                'required': False,
            },

            # NI number
            #
            # The patient's unique National Insurance Number
            'national_insurance_number': {
                'type': 'number',
                'minlength': min_digits(1),
                'maxlength': max_digits(9),
                'required': False,
            },
        }
