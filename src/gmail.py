import sys
import json
from gmail_refresh import refresh_cache
from workflow import Workflow, PasswordNotFound, MATCH_SUBSTRING
from workflow.background import run_in_background, is_running

import config

THREAD_DELIMITER = 't:'
OPERATION_PREFIX = '> '

WF = Workflow(update_settings={
    'github_slug': 'fniephaus/alfred-gmail',
    'version': 'v0.3',
})

def main():
    if WF.update_available:
        subtitle = 'New: %s' % WF.update_info['body']
        WF.add_item("An update is available!", subtitle,
                    autocomplete='workflow:update', valid=False)

    if len(WF.args):
        query = WF.args[0]
    else:
        query = None

    if query and THREAD_DELIMITER in query:
        label = query.split()[0]
        thread_query = query[
            query.find(THREAD_DELIMITER) + len(THREAD_DELIMITER):].split()
        if len(thread_query) == 0:
            WF.add_item("Missing Thread ID", valid=False)
            WF.send_feedback()
            return 0

        thread_id = thread_query[0]
        label_threads = WF.cached_data('gmail_%s' % label.lower(), max_age = 0)
        if label_threads is None:
            WF.add_item("Caching problem", valid=False)
            WF.send_feedback()
            return 0
        selected_thread = None
        for thread in label_threads:
            if thread['threadId'] == thread_id:
                selected_thread = thread

        if selected_thread is None:
            WF.add_item("Invalid Thread ID", valid=False)
            WF.send_feedback()
            return 0

        if len(thread_query) > 1 and 'reply' in thread_query[1]:
            message = ' '.join(thread_query[2:])
            valid = len(message) > 0
            subtitle = "Hit enter to send reply" if valid else "Start typing your reply"
            arg = json.dumps({
                'thread_id': thread_id,
                'message_id': None,
                'action': 'reply',
                'message': message
            })
            WF.add_item(message, subtitle, arg=arg, valid=valid)
        elif len(thread_query) > 1 and 'label' in thread_query[1]:
            label_list = WF.cached_data('gmail_labels', max_age=0)
            if label_list:
                if len(thread_query) > 2:
                    label_list = [label for label in label_list
                                  if ' '.join(thread_query[2:]).lower() in label['name'].lower()]
                if len(label_list):
                    for label in label_list:
                        arg = json.dumps({
                            'thread_id': thread_id,
                            'message_id': None,
                            'action': 'label',
                            'label': label,
                            'query': query,
                        })
                        WF.add_item(
                            label['name'], "Hit enter to add this label", arg=arg, valid=True)
                else:
                    WF.add_item(
                        "No label found", "Please try again!", valid=False)
            else:
                WF.add_item(
                    "Could not fetch labels", "Please try again or file a bug report!", valid=False)
        else:
            email_title = selected_thread['Subject']
            email_snippet = selected_thread['snippet']
            WF.add_item(email_title, email_snippet, arg = json.dumps({
                'thread_id': thread_id,
                'action': 'open',
                'label': label,
            }), valid=True)

            WF.add_item(OPERATION_PREFIX + "Mark As Read", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'mark_as_read',
                'query': query,
            }), valid=True)

            WF.add_item(OPERATION_PREFIX + "Archive", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'archive_conversation',
                'label': label,
            }), valid=True)

            if label != 'TRASH':
                WF.add_item(OPERATION_PREFIX + "Move To Trash", "", arg=json.dumps({
                    'thread_id': thread_id,
                    'action': 'trash_conversation',
                    'label': label,
                }), valid=True)

            if label != 'INBOX':
                WF.add_item(OPERATION_PREFIX + "Move To Inbox", "", arg=json.dumps({
                    'thread_id': thread_id,
                    'action': 'move_to_inbox',
                    'label': label,
                }), valid=True)

            WF.add_item(OPERATION_PREFIX + "Mark As Unread", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'mark_as_unread',
                'query': query,
            }), valid=True)

            WF.add_item(OPERATION_PREFIX + "Quick Reply", "", autocomplete='%s reply ' %
                        query, valid=False)
            WF.add_item(OPERATION_PREFIX + "Add label", "", autocomplete='%s label ' %
                        query, valid=False)
            # WF.add_item("Show Inbox", "", autocomplete=' ', valid=False)

        WF.send_feedback()
        return 0

    if query and any(query.startswith(label) for label in config.SYSTEM_LABELS):
        query = query.split()
        label = query[0]
        label_query = ' '.join(query[1:]) if len(query) > 0 else ''
        if not WF.cached_data_fresh('gmail_%s' % label.lower(), max_age=3600):
            refresh_cache([label])
        item_list = WF.cached_data('gmail_%s' % label.lower(), max_age=0)

        if item_list is not None:
            if len(item_list) == 0:
                WF.add_item('No mails found!', valid=False)
            else:
                for index, item in enumerate(item_list):
                    name = 'Unknown'
                    if item['From']:
                        name = item['From'][
                            :item['From'].find("<") - 1].replace('"', '')
                    title = '%s (%s): %s' % (
                        name, item['messages_count'], item['Subject'])
                    if item['unread']:
                        title = '+ %s' % title
                    else:
                        title = '- %s' % title
                    subtitle = '%s - %s' % (item['Date'][:-6], item['snippet'])
                    autocomplete = '%s %s%s' % (label, THREAD_DELIMITER, item['threadId'])

                    if label_query.lower() in ' '.join([title, subtitle]).lower():
                        WF.add_item(
                            title, subtitle, autocomplete=autocomplete, valid=False)
        else:
            WF.add_item("Could receive your emails.",
                        "Please try again or file a bug report!", valid=False)

        WF.send_feedback()
        return 0

    for label, name in config.SYSTEM_LABELS.iteritems():
        if not query or query.lower() in name.lower():
            WF.add_item(name, autocomplete='%s ' % label, valid=False)

    # Update list in background
    if not WF.cached_data_fresh('gmail_list', max_age=30):
        background_refresh()

    WF.send_feedback()


def background_refresh():
    if not is_running('gmail_refresh'):
        cmd = ['/usr/bin/python', WF.workflowfile('gmail_refresh.py')]
        run_in_background('gmail_refresh', cmd)


if __name__ == '__main__':
    main()
