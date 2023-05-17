import os

from dotenv import load_dotenv

load_dotenv()


def test_development_config(test_app):
    test_app.config.from_object('src.config.DevelopmentConfig')
    assert test_app.config['SECRET_KEY'] == 'this-is-a-great-secret-key'
    assert not test_app.config['TESTING']
    assert test_app.config['SQLALCHEMY_DATABASE_URI'] == os.environ.get('DATABASE_URL')


def test_testing_config(test_app):
    test_app.config.from_object('src.config.TestingConfig')
    assert test_app.config['SECRET_KEY'] == 'this-is-a-great-secret-key'
    assert test_app.config['TESTING']
    assert test_app.config['SQLALCHEMY_DATABASE_URI'] == os.environ.get('DATABASE_TEST_URL')


def test_production_config(test_app):
    test_app.config.from_object('src.config.ProductionConfig')
    assert test_app.config['SECRET_KEY'] == 'this-is-a-great-secret-key'
    assert not test_app.config['TESTING']
    assert test_app.config['SQLALCHEMY_DATABASE_URI'] == os.environ.get('DATABASE_URL')
