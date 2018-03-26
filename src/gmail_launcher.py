import os
import subprocess
import sys
import json
import httplib2
import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient import errors
from oauth2client.client import flow_from_clientsecrets, OAuth2Credentials
from oauth2client.tools import run_flow

from workflow import Workflow, PasswordNotFound
from gmail_refresh import refresh_cache, PseudoStorage

import config

OPEN_MESSAGE_BASE_URL = 'https://mail.google.com/mail/u/0/?ui=2&pli=1#inbox/%s'
OPEN_ALFRED_OSA_TEMPLATE = """\
osascript -e 'tell application "Alfred 3" to run trigger "open" in workflow \
"com.fniephaus.gmail" with argument "%s"'"""


def execute(wf):
    if len(wf.args):
        if 'reopen' in wf.args[0]:
            open_alfred()
            return 0

        query = json.loads(wf.args[0])

        # Start the OAuth flow to retrieve credentials
        flow = flow_from_clientsecrets(
            config.CLIENT_SECRET_FILE, scope=config.OAUTH_SCOPE)
        http = httplib2.Http()

        try:
            credentials = OAuth2Credentials.from_json(
                wf.get_password('gmail_credentials'))
            if credentials is None or credentials.invalid:
                credentials = run_flow(flow, PseudoStorage(), http=http)
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
        except KeyError:
            return 0
        message_id = query.get('message_id')

        target = None
        if 'action' in query:
            if query['action'] == 'deauthorize':
                wf.delete_password('gmail_credentials')
                wf.clear_cache()
                print "Workflow deauthorized."
                return 0
            elif query['action'] == 'mark_as_read':
                mark_conversation_as_read(service, thread_id)
                target = query.get('query')
            elif query['action'] == 'mark_as_unread':
                mark_conversation_as_unread(service, thread_id)
                target = query.get('query')
            elif query['action'] == 'archive_conversation':
                refresh_cache(archive_conversation(service, thread_id))
            elif query['action'] == 'trash_message':
                refresh_cache(trash_message(service, message_id))
                target = query.get('label')
            elif query['action'] == 'move_to_inbox':
                refresh_cache(move_to_inbox(service, message_id))
                target = query.get('label')
            elif query['action'] == 'trash_conversation':
                refresh_cache(trash_conversation(service, thread_id))
                target = query.get('label')
            elif query['action'] == 'reply':
                if 'message' in query:
                    send_reply(wf, service, thread_id, query['message'])
                else:
                    print 'No message found.'
                target = query.get('query')
            elif query['action'] == 'label':
                if 'label' in query:
                    add_label(service, thread_id, query['label'])
                else:
                    print 'No label found.'
                target = query.get('query')
            elif query['action'] == 'open':
                open_message(wf, thread_id)
                if 'label_id' in query:
                    refresh_cache([query['label_id']])
                return 0
        else:
            wf.logger.debug('No action defined')
            return 0

        open_alfred(target)


def open_message(wf, message_id):
    if message_id:
        url = OPEN_MESSAGE_BASE_URL % message_id
        subprocess.call(['open', url])


def mark_conversation_as_read(service, thread_id):
    try:
        # Mark conversation as read
        thread = service.users().threads().modify(
            userId='me', id=thread_id,
            body={'removeLabelIds': ['UNREAD']}).execute()
        if all((u'labelIds' in message and
                u'UNREAD' not in message['labelIds'])
                for message in thread['messages']):
            print 'Conversation marked as read.'
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except KeyError:
        print 'Connection error'
    return []


def mark_conversation_as_unread(service, thread_id):
    try:
        # Mark conversation as unread
        thread = service.users().threads().modify(
            userId='me', id=thread_id,
            body={'addLabelIds': ['UNREAD']}).execute()
        if all((u'labelIds' in message and
                u'UNREAD' in message['labelIds'])
                for message in thread['messages']):
            print 'Conversation marked as unread.'
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except KeyError:
        print 'Connection error'
    return []


def move_to_inbox(service, thread_id):
    try:
        thread = service.users().threads().modify(
            userId='me', id=thread_id,
            body={'addLabelIds': ['INBOX']}).execute()
        if all((u'labelIds' in message and
                u'INBOX' in message['labelIds'])
                for message in thread['messages']):
            print 'Conversation moved to inbox.'
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except KeyError:
        print 'Connection error'
    return []


def archive_conversation(service, thread_id):
    try:
        # Archive conversation
        thread = service.users().threads().modify(
            userId='me', id=thread_id,
            body={'removeLabelIds': ['INBOX']}).execute()
        if all((u'labelIds' in message and
                u'INBOX' not in message['labelIds'])
                for message in thread['messages']):
            print 'Conversation archived.'
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except Exception:
        print 'Connection error'
    return []


def trash_message(service, message_id):
    if message_id:
        try:
            # Trash message
            message = service.users().messages().trash(
                userId='me', id=message_id).execute()
            if u'labelIds' in message and u'TRASH' in message['labelIds']:
                print 'Mail moved to trash.'
                return message['labelIds']
            else:
                print 'An error occurred.'
        except Exception:
            print 'Connection error'
    return []


def trash_conversation(service, thread_id):
    try:
        # Trash conversation
        thread = service.users().threads().trash(
            userId='me', id=thread_id).execute()

        if all((u'labelIds' in message and
                u'TRASH' in message['labelIds'])
                for message in thread['messages']):
            print 'Conversation moved to trash.'
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except Exception:
        print 'Connection error'
    return []


def send_reply(wf, service, thread_id, message):
    try:
        thread = service.users().threads().get(
            userId='me', id=thread_id,
            fields='messages/payload/headers,messages/labelIds').execute()
        header_from = None
        header_delivered_to = None
        header_subject = None
        for header in thread['messages'][-1]['payload']['headers']:
            if header['name'] == 'From':
                header_from = header['value']
            if header['name'] == 'Delivered-To':
                header_delivered_to = header['value']
            if header['name'] == 'Subject':
                header_subject = header['value']

        if any(not x for x in
               [header_from, header_delivered_to, header_subject]):
            print 'An error occurred.'
            return []

        message_body = create_message(
            header_delivered_to, header_from, header_subject, message)

        service.users().messages().send(
            userId='me', body=message_body).execute()
        print 'Reply sent.'
        return thread['messages'][-1]['labelIds']
    except errors.HttpError, error:
        print 'An error occurred: %s' % error
        return []


def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_string())}


def add_label(service, thread_id, label):
    try:
        thread = service.users().threads().modify(
            userId='me', id=thread_id,
            body={'addLabelIds': [label['id']]}).execute()
        if all((u'labelIds' in message and label['id'] in message['labelIds'])
                for message in thread['messages']):
            print 'Labeled with %s.' % label['name']
            return thread['messages'][-1]['labelIds']
        else:
            print 'An error occurred.'
    except KeyError:
        print 'Connection error'
    return []


def open_alfred(query=None):
    os.system(OPEN_ALFRED_OSA_TEMPLATE % (query or ''))


if __name__ == '__main__':
    wf = Workflow()
    sys.exit(wf.run(execute))
