"""This module provides the blueprint for some basic API endpoints.

For more information please refer to the documentation on ReadTheDocs:
 - https://bigchaindb.readthedocs.io/en/latest/drivers-clients/http-client-server-api.html
"""

import flask
from flask import current_app, request, Blueprint

import bigchaindb
from bigchaindb import util
from bigchaindb.web.views.base import make_error

transaction_views = Blueprint('transaction_views', __name__)


# Unfortunately I cannot find a reference to this decorator.
# This answer on SO is quite useful tho:
# - http://stackoverflow.com/a/13432373/597097
@transaction_views.record
def record(state):
    """This function checks if the blueprint can be initialized
    with the provided state."""

    bigchain_pool = state.app.config.get('bigchain_pool')
    monitor = state.app.config.get('monitor')

    if bigchain_pool is None:
        raise Exception('This blueprint expects you to provide '
                        'a pool of Bigchain instances called `bigchain_pool`')

    if monitor is None:
        raise ValueError('This blueprint expects you to provide '
                         'a monitor instance to record system '
                         'performance.')


@transaction_views.route('/transactions/<tx_id>')
def get_transaction(tx_id):
    """API endpoint to get details about a transaction.

    Args:
        tx_id (str): the id of the transaction.

    Return:
        A JSON string containing the data about the transaction.
    """

    pool = current_app.config['bigchain_pool']

    with pool() as bigchain:
        tx = bigchain.get_transaction(tx_id)

    if not tx:
        return make_error(404)

    return flask.jsonify(**tx)


@transaction_views.route('/transactions/', methods=['POST'])
def create_transaction():
    """API endpoint to push transactions to the Federation.

    Return:
        A JSON string containing the data about the transaction.
    """
    pool = current_app.config['bigchain_pool']
    monitor = current_app.config['monitor']

    # `force` will try to format the body of the POST request even if the `content-type` header is not
    # set to `application/json`
    tx = request.get_json(force=True)

    with pool() as bigchain:
        if tx['transaction']['operation'] == 'CREATE':
            tx = util.transform_create(tx)
            tx = bigchain.consensus.sign_transaction(tx, private_key=bigchain.me_private)

        if not bigchain.is_valid_transaction(tx):
            return make_error(400, 'Invalid transaction')

        with monitor.timer('write_transaction', rate=bigchaindb.config['statsd']['rate']):
            bigchain.write_transaction(tx)

    return flask.jsonify(**tx)


@transaction_views.route('/transactions/<tx_id>/status')
def get_transaction_status(tx_id):
    """API endpoint to get details about the status of a transaction.

    Args:
        tx_id (str): the id of the transaction.

    Return:
        A JSON string containing the status of the transaction.
        Possible values: "valid", "invalid", "undecided", "backlog", None
    """

    pool = current_app.config['bigchain_pool']

    with pool() as bigchain:
        status = bigchain.get_status(tx_id, include_status=True)

    if not status:
        return make_error(404)

    return flask.jsonify({'status': status})
