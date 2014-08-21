import argparse
import os
import subprocess
import sys
import json
import httplib2

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run

from workflow import Workflow, PasswordNotFound
from gmail_refresh import refresh_cache

import config


def execute(wf):
    if len(wf.args):
        query = json.loads(wf.args[0])

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
            return 0

        try:
            thread_id = query['thread_id']
            message_id = query['message_id']
        except KeyError:
            return 0

        target = None
        if 'action' in query:
            if query['action'] == 'deauthorize':
                wf.delete_password('gmail_credentials')
                print "Workflow deauthorized."
                return 0
            elif query['action'] == 'mark_as_read':
                print mark_conversation_as_read(service, thread_id)
                target = query['query']
            elif query['action'] == 'archive_conversation':
                print archive_conversation(service, thread_id)
            elif query['action'] == 'trash_message':
                print trash_message(service, message_id)
            elif query['action'] == 'trash_conversation':
                print trash_conversation(service, thread_id)
            elif query['action'] == 'reply':
                if 'message' in query:
                    print send_reply(thread_id, query['message'])
                else:
                    print 'No message found.'
            elif query['action'] == 'label':
                if 'label' in query:
                    print add_label(service, thread_id, query['label'])
                else:
                    print 'No label found.'
        else:
            open_message(wf, message_id)
            refresh_cache()
            return 0
        refresh_cache()
        open_alfred(target)


def open_message(wf, message_id):
    url = 'https://mail.google.com/mail/u/0/?ui=2&pli=1#inbox/%s' % message_id
    subprocess.call(['open', url])


def mark_conversation_as_read(service, thread_id):
    try:
        # Archive conversation
        thread = service.users().threads().modify(
            userId='me', id=thread_id, body={'removeLabelIds': ['UNREAD']}).execute()
        if all(u'labelIds' in message and u'UNREAD' not in message['labelIds'] for message in thread['messages']):
            return 'Conversation marked as read.'
        else:
            return 'An error occurred.'
    except Exception:
        return 'Connection error'


def archive_conversation(service, thread_id):
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


def trash_message(service, message_id):
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


def trash_conversation(service, thread_id):
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


def send_reply(thread_id, message):
    pass


def add_label(service, thread_id, label):
    try:
        thread = service.users().threads().modify(
            userId='me', id=thread_id, body={'addLabelIds': [label['id']]}).execute()
        if all(u'labelIds' in message and label['id'] in message['labelIds'] for message in thread['messages']):
            return 'Labeled with %s.' % label['name']
        else:
            return 'An error occurred.'
    except KeyError:
        return 'Connection error'


def open_alfred(query=None):
    query = query or ''
    os.system(
        """ osascript -e 'tell application "Alfred 2" to search "gmail %s"' """ %
        query)


if __name__ == '__main__':
    wf = Workflow()
    sys.exit(wf.run(execute))
