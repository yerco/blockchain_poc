import json
import os
import uuid

from fastecdsa.keys import import_key
from freezegun import freeze_time

from src.models import Transaction


class TestTransaction:
    @freeze_time("2012-01-01")
    def test_create_transaction_object(self, monkeypatch):
        # Define the fixed UUID value that we want to mock
        fixed_uuid = uuid.UUID('00000000-0000-0000-0000-000000000000')
        # Define a function that always returns the fixed UUID value
        def mock_uuid4():
            return fixed_uuid
        # Monkeypatch the uuid.uuid4 function to use our mock function instead
        monkeypatch.setattr(uuid, 'uuid4', mock_uuid4)

        # get the path of the current file
        current_file_path = __file__
        # get the directory path
        current_directory_path = os.path.dirname(os.path.abspath(current_file_path))
        private_key, public_key = import_key(f'{current_directory_path}/../../../keys/private_key.pem')
        data = {
            'full_names': 'fullNames Test String',
            'practice_number': '1234567890',
            'notes': 'notes Test String',
        }
        transaction_object = Transaction(public_key=public_key, private_key=private_key, data=data)
        transaction_data_dictionary = json.loads(transaction_object.transaction_data_string)
        assert transaction_data_dictionary['transaction_id'] == '00000000000000000000000000000000'
        assert transaction_data_dictionary['timestamp'] == '2012-01-01T00:00:00Z'
        assert transaction_data_dictionary['data'] == data
        assert transaction_object.valid is True
