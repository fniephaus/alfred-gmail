import argparse
import os
import sys
import httplib2

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run

from workflow import Workflow, PasswordNotFound

import config


def execute(wf):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--archive-conversation', dest='archive_conversation', action='store_true', default=None)
    parser.add_argument(
        '--trash-mail', dest='trash_message', action='store_true', default=None)
    parser.add_argument(
        '--trash-conversation', dest='trash_conversation', action='store_true', default=None)
    parser.add_argument(
        '--deauthorize', dest='deauthorize', action='store_true', default=None)
    parser.add_argument('query', nargs='?', default=None)
    args = parser.parse_args(wf.args)

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

        # Authorize the httplib2.Http object with our credentials
        http = credentials.authorize(http)
        # Build the Gmail service from discovery
        service = build('gmail', 'v1', http=http)
    except PasswordNotFound:
        wf.logger.error('Credentials not found')

    if args.query is not None:
        query = args.query.split()

        if args.deauthorize:
            wf.delete_password('gmail_credentials')
            print "Workflow deauthorized."
            return 0

        if len(query) < 2:
            return 0

        thread_id = query[0]
        message_id = query[1]

        if args.archive_conversation:
            print archive_conversation(thread_id, service)
            return 0
        elif args.trash_message:
            print trash_message(message_id, service)
            return 0
        elif args.trash_conversation:
            print trash_conversation(thread_id, service)
            return 0
        else:
            open_message(wf, message_id)
            return 0


def open_message(wf, message_id):
    url = 'https://mail.google.com/mail/u/0/?ui=2&pli=1#inbox/%s' % message_id
    wf.logger.debug(url)
    os.system('open "%s"' % url)


def archive_conversation(thread_id, service):
    try:
        # Archive conversation
        thread = service.users().threads().modify(
            userId='me', id=thread_id, body={'removeLabelIds': ['INBOX']}).execute()
        if all(u'labelIds' in message and u'INBOX' not in message['labelIds'] for message in thread['messages']):
            return 'Conversation archived.'
        else:
            return 'An error occurred.'
    except Exception:
        return 'Connection error'


def trash_message(message_id, service):
    try:
        # Trash message
        message = service.users().messages().trash(
            userId='me', id=message_id).execute()
        if u'labelIds' in message and u'TRASH' in message['labelIds']:
            return 'Mail moved to trash.'
        else:
            return 'An error occurred.'
    except Exception:
        return 'Connection error'


def trash_conversation(thread_id, service):
    try:
        # Trash conversation
        thread = service.users().threads().trash(
            userId='me', id=thread_id).execute()

        if all(u'labelIds' in message and u'TRASH' in message['labelIds'] for message in thread['messages']):
            return 'Conversation moved to trash.'
        else:
            return 'An error occurred.'
    except Exception:
        return 'Connection error'


if __name__ == '__main__':
    wf = Workflow()
    sys.exit(wf.run(execute))
