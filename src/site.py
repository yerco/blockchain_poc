from flask import Blueprint, render_template, abort
from jinja2 import TemplateNotFound

site_blueprint = Blueprint('site', __name__, template_folder='templates')


@site_blueprint.route('/', defaults={'page': 'index'})
@site_blueprint.route('/<page>')
def show(page):
    try:
        return render_template(f'{page}.html')
    except TemplateNotFound:
        abort(404)
