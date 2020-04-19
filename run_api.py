import os
import json

import plaid

from flask import request
from flask import jsonify
from flask_cors import CORS
from flask import Flask
from flask_restx import Api, Resource, fields

from werkzeug.exceptions import UnprocessableEntity

app = Flask(__name__)

api = Api(app,
          prefix='',
          version='1.0',
          title='PLAID',
          description='APIs to run processes in PLAID')

institutions_model = api.model('Institutions', {
    'count': fields.Integer(
        required=True,
        description="Integer between 0-500",
        example=10)
})

transactions_model = api.model('Transactions', {
    'access_token': fields.String(
        required=True,
        description="Access Token",
        example="access-sandbox-somesexynumber"),
    'start_date': fields.Date(
        required=True,
        description="start date",
        example="1950-01-01"),
    'end_date': fields.Date(
        required=True,
        description="end date",
        example="2020-01-01")
})

plaid_ns = api.namespace('v1', description='PLAID Processes')

CORS(app, resources={
    r"/*": {
        "origins": app.config.get('CORS_ORIGINS', '*')
    }
})

PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID')
PLAID_SECRET = os.getenv('PLAID_SECRET')
PLAID_PUBLIC_KEY = os.getenv('PLAID_PUBLIC_KEY')
PLAID_ENV = os.getenv('PLAID_ENV')
PLAID_PRODUCTS = os.getenv('PLAID_PRODUCTS')
PLAID_COUNTRY_CODES = os.getenv('PLAID_COUNTRY_CODES')

NAMESPACE_NAME = 'PLAID'

client = plaid.Client(client_id=PLAID_CLIENT_ID, secret=PLAID_SECRET,
                      public_key=PLAID_PUBLIC_KEY, environment=PLAID_ENV, api_version='2019-05-29')


#### Exceptions #####
class InvalidInputMessage(UnprocessableEntity):
    def __init__(self, message):
        super().__init__(message)
        self.data = {
            "ResponseOutput": {
                "Status": "Error",
                "Status Description": message
            }
        }


##### APIs #####
# Retrieve Transactions
@plaid_ns.route("/transactions")
class Transactions(Resource):
    @plaid_ns.expect(transactions_model)
    def post(self):
        args = request.get_json()
        start_date = args['start_date']
        end_date = args['end_date']
        access_token = args['access_token']
        try:
            transactions_response = transactions(access_token, start_date, end_date)
            return jsonify([transaction for transaction in transactions_response])
        except plaid.errors.PlaidError as e:
            return jsonify(format_error(e))


# Retrieve Institutions
@plaid_ns.route("/institutions")
class Institutions(Resource):
    @plaid_ns.expect(institutions_model)
    def post(self):
        args = request.get_json()
        if args['count'] > 500:
            raise InvalidInputMessage("Accepted range for count is between 0-500")
        num_institutions = args['count']

        try:
            institutions_response = institutions(num_institutions)
            return jsonify(institutions_response)
        except plaid.errors.PlaidError as e:
            return jsonify(format_error(e))


#### Api logic ####
MAX_TRANSACTIONS_PER_PAGE = 500


def transactions(access_token, start_date, end_date):
    response = client.Transactions.get(access_token,
                                       start_date,
                                       end_date)
    transactions = response['transactions']

    # Manipulate the count and offset parameters to paginate
    # transactions and retrieve all available data
    while len(transactions) < response['total_transactions']:
        response = client.Transactions.get(access_token,
                                           start_date,
                                           end_date,
                                           offset=len(transactions)
                                           )
        transactions.extend(response['transactions'])

    return transactions


def institutions(num_institutions):
    institute_list = []
    response = client.Institutions.get(num_institutions)
    institutes = response['institutions']
    while len(institutes) < response['total']:
        response = client.Institutions.get(num_institutions, offset=len(institutes))
        institutes.extend(response['institutions'])
    for institute_name in institutes:
        institute_list.append(institute_name['name'])
    return institute_list


#### Utils ####
def pretty_print_response(response):
    print(json.dumps(response, indent=2, sort_keys=True))


def format_error(e):
    return {'error': {'display_message': e.display_message, 'error_code': e.code, 'error_type': e.type,
                      'error_message': e.message}}


if __name__ == '__main__':
    app.run(port=os.getenv('PORT', 5000))
