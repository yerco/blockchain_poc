import datetime
import pytz

from src.models import Block


class TestBlock:
    def test_bare_block(self):
        # Localize a naive datetime object to the US/Eastern timezone
        dt_eastern = pytz.timezone('US/Eastern').localize(datetime.datetime(2022, 4, 21, 14, 30, 0))
        # Convert the datetime object to the UTC time zone
        dt_utc = dt_eastern.astimezone(pytz.utc)
        test_block = Block(prev_hash='000000000', nonce=456, timestamp=dt_utc, data='some data')
        assert test_block.prev_hash == '000000000'
        assert test_block.nonce == 456
        assert test_block.timestamp == '2022-04-21T18:30:00Z'
        assert test_block.hash == 'non-hashed'
        assert test_block.data == 'some data'

    def test_encoded_block(self):
        # Localize a naive datetime object to the US/Eastern timezone
        dt_eastern = pytz.timezone('US/Eastern').localize(datetime.datetime(2022, 4, 21, 14, 30, 0))
        # Convert the datetime object to the UTC time zone
        dt_utc = dt_eastern.astimezone(pytz.utc)
        test_block = Block(timestamp=dt_utc, data='some data')
        test_block.encode_block()
        assert test_block.prev_hash == '000000000'
        assert test_block.nonce == 456
        assert test_block.timestamp == '2022-04-21T18:30:00Z'
        assert test_block.hash == 'a89d454457144b2cb92317db6ff5273d7b81d6f149a483afe3b421be8a45c828'
        assert test_block.data == 'some data'
