import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

load_dotenv()
# instantiate the db
db = SQLAlchemy()


def create_app():
    # instantiate the app
    app = Flask(__name__)

    # set config
    app_settings = os.getenv('APP_SETTINGS')
    app.config.from_object(app_settings)
    os.environ['FLASK_RUN_PORT'] = app.config['FLASK_RUN_PORT']

    db.init_app(app)

    # register blueprints
    from src.site import site_blueprint
    app.register_blueprint(site_blueprint, url_prefix='/')
    from src.api import api_blueprint
    app.register_blueprint(api_blueprint)
    CORS(app)

    # shell context for flask cli
    @app.shell_context_processor
    def ctx():
        return {'app': app, 'db': db}

    return app
