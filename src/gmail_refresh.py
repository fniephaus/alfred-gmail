import httplib2

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run

from workflow import Workflow, PasswordNotFound

import config


class PseudoStorage():

    def put(self, value):
        pass


def get_list(wf, gmail_service):
    # Retrieve a page of threads
    threads = gmail_service.users().threads().list(
        userId='me', labelIds=['INBOX'], maxResults=50).execute()

    # Receive emails
    email_list = []
    if threads['threads']:
        for thread in threads['threads']:
            thread_details = gmail_service.users().threads().get(
                userId='me', id=thread['id']).execute()
            message = {
                'Date': None,
                'From': None,
                'id': None,
                'thread_id': thread['id'],
                'snippet': None,
                'Subject': None,
            }
            if 'messages' in thread_details and len(thread_details['messages']) > 0:
                if 'id' in thread_details['messages'][0]:
                    message['id'] = thread_details['messages'][0]['id']

                if 'snippet' in thread_details['messages'][0]:
                    message['snippet'] = thread_details[
                        'messages'][0]['snippet'].encode('ascii', 'xmlcharrefreplace')

                for header in thread_details['messages'][0]['payload']['headers']:
                    if header['name'] in message:
                        message[header['name']] = header[
                            'value'].encode('ascii', 'xmlcharrefreplace')

            email_list.append(message)

    return email_list


def refresh_cache():
    wf = Workflow()
    # Start the OAuth flow to retrieve credentials
    flow = flow_from_clientsecrets(
        config.CLIENT_SECRET_FILE, scope=config.OAUTH_SCOPE)
    http = httplib2.Http()

    try:
        credentials = OAuth2Credentials.from_json(
            wf.get_password('gmail_credentials'))
        if credentials is None or credentials.invalid:
            credentials = run(flow, PseudoStorage(), http=http)
            wf.save_password('gmail_credentials', credentials.to_json())
            wf.logger.debug('Credentials securely updated')

        # Authorize the httplib2.Http object with our credentials
        http = credentials.authorize(http)
        # Build the Gmail service from discovery
        gmail_service = build('gmail', 'v1', http=http)

        def wrapper():
            return get_list(wf, gmail_service)

        wf.cached_data('gmail_list', data_func=wrapper, max_age=30)

    except PasswordNotFound:
        wf.logger.debug('Credentials not found')
        credentials = run(flow, PseudoStorage(), http=http)
        wf.save_password('gmail_credentials', credentials.to_json())
        wf.logger.debug('New Credentials securely saved')

if __name__ == '__main__':
    refresh_cache()
