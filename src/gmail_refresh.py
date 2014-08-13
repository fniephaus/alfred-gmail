import httplib2

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
# from oauth2client.file import Storage
from oauth2client.tools import run

from workflow import Workflow, PasswordNotFound

import config

# Path to the client_secret.json file downloaded from the Developer Console
CLIENT_SECRET_FILE = 'client_secret.json'

# Check https://developers.google.com/gmail/api/auth/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'


class PseudoStorage():

    def put(self, value):
        pass


def get_list(wf, gmail_service):
    # Retrieve a page of threads
    threads = gmail_service.users().threads().list(userId='me').execute()

    # Receive emails
    email_list = []
    if threads['threads']:
        i = 0
        for thread in threads['threads']:
            thread_details = gmail_service.users().threads().get(
                userId='me', id=thread['id']).execute()
            message = {
                'Date': None,
                'From': None,
                'id': None,
                'snippet': None,
                'Subject': None,
            }
            if 'messages' in thread_details and len(thread_details['messages']) > 0:
                if 'id' in thread_details['messages'][0]:
                    message['id'] = thread_details['messages'][0]['id']

                if 'snippet' in thread_details['messages'][0]:
                    message['snippet'] = thread_details[
                        'messages'][0]['snippet']

                for header in thread_details['messages'][0]['payload']['headers']:
                    if header['name'] in message:
                        message[header['name']] = header[
                            'value'].encode('utf-8')

            email_list.append(message)

            if i < 9:
                i += 1
            else:
                break

    return email_list

if __name__ == '__main__':
    wf = Workflow()

    # Start the OAuth flow to retrieve credentials
    flow = flow_from_clientsecrets(CLIENT_SECRET_FILE, scope=OAUTH_SCOPE)
    http = httplib2.Http()

    try:
        credentials = OAuth2Credentials.from_json(
            wf.get_password('gmail_credentials'))
        if credentials is None or credentials.invalid:
            credentials = run(flow, PseudoStorage(), http=http)
            wf.save_password('gmail_credentials', credentials.to_json())

        def wrapper():
            global http
            # Authorize the httplib2.Http object with our credentials
            http = credentials.authorize(http)
            # Build the Gmail service from discovery
            gmail_service = build('gmail', 'v1', http=http)
            return get_list(wf, gmail_service)

        wf.cached_data('gmail_list', data_func=wrapper, max_age=1)

    except PasswordNotFound:

        # Run the flow to generate credentials
        credentials = run(flow, PseudoStorage(), http=http)
        wf.save_password('gmail_credentials', credentials.to_json())
