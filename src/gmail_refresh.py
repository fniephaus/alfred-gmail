import httplib2

from apiclient.discovery import build
from apiclient.http import BatchHttpRequest
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run

from workflow import Workflow, PasswordNotFound

import config

EMAIL_LIST = []


class PseudoStorage():

    def put(self, value):
        pass


def list_threads(request_id, response, exception):
    if exception is None:
        thread = {
            'Date': None,
            'From': None,
            'id': None,
            'messages_count': None,
            'snippet': None,
            'Subject': None,
            'threadId': None,
            'unread': None,
        }
        if 'messages' in response and len(response['messages']) > 0:
            if 'id' in response['messages'][-1]:
                thread['id'] = response['messages'][-1]['id']

            if 'threadId' in response['messages'][-1]:
                thread['threadId'] = response['messages'][-1]['threadId']

            if 'snippet' in response['messages'][-1]:
                thread['snippet'] = response[
                    'messages'][-1]['snippet'].encode('utf-8')

            for header in response['messages'][-1]['payload']['headers']:
                if header['name'] in thread:
                    thread[header['name']] = header[
                        'value'].encode('utf-8')

            thread['messages_count'] = len(response['messages'])
            thread['unread'] = 'UNREAD' in response['messages'][-1]['labelIds']

        EMAIL_LIST.append(thread)


def get_list(wf, http, service):
    # Retrieve a page of threads
    threads = service.users().threads().list(
        userId='me', labelIds=['INBOX'], maxResults=100).execute()

    batch = BatchHttpRequest()
    if 'threads' in threads and len(threads['threads']) > 0:
        fields = 'messages/id,messages/threadId,messages/labelIds,messages/snippet,messages/payload/headers'
        for thread in threads['threads']:
            batch.add(service.users().threads().get(
                userId='me', id=thread['id'], fields=fields), callback=list_threads)

        batch.execute(http=http)

    return EMAIL_LIST


def get_labels(wf, service):
    try:
        response = service.users().labels().list(userId='me').execute()
        return [label['name'] for label in response['labels']]
    except errors.HttpError, error:
        wf.logger.debug('An error occurred: %s' % error)
        return []


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

        wf.cache_data('gmail_list', get_list(wf, http, gmail_service))
        wf.cache_data('gmail_labels', get_labels(wf, gmail_service))

    except PasswordNotFound:
        wf.logger.debug('Credentials not found')
        credentials = run(flow, PseudoStorage(), http=http)
        wf.save_password('gmail_credentials', credentials.to_json())
        wf.logger.debug('New Credentials securely saved')

if __name__ == '__main__':
    refresh_cache()
