import sys
import json
from gmail_refresh import refresh_cache
from workflow import Workflow, PasswordNotFound, MATCH_SUBSTRING
from workflow.background import run_in_background, is_running

import config

THREAD_DELIMITER = 't:'


def main(wf):
    if wf.update_available:
        wf.add_item("An update is available!", "Hit enter to upgrade.",
                    autocomplete='workflow:update', valid=False)

    if len(wf.args):
        query = wf.args[0]
    else:
        query = None

    if query and THREAD_DELIMITER in query:
        label = query.split()[0]
        thread_query = query[
            query.find(THREAD_DELIMITER) + len(THREAD_DELIMITER):].split()
        thread_id = thread_query[0]

        if len(thread_id) < 4:
            wf.add_item("Invalid Thread ID", valid=False)
            wf.send_feedback()
            return 0

        wf.logger.debug(thread_query)

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
            wf.add_item(message, subtitle, arg=arg, valid=valid)
        elif len(thread_query) > 1 and 'label' in thread_query[1]:
            label_list = wf.cached_data('gmail_labels', max_age=0)
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
                            'label': label
                        })
                        wf.add_item(
                            label['name'], "Hit enter to add this label", arg=arg, valid=True)
                else:
                    wf.add_item(
                        "No label found", "Please try again!", valid=False)
            else:
                wf.add_item(
                    "Could not fetch labels", "Please try again or file a bug report!", valid=False)
        else:
            wf.add_item("Mark As Read", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'mark_as_read',
                'query': query,
            }), valid=True)
            wf.add_item("Archive", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'archive_conversation',
            }), valid=True)
            if label != 'TRASH':
                wf.add_item("Move To Trash", "", arg=json.dumps({
                    'thread_id': thread_id,
                    'action': 'trash_conversation',
                }), valid=True)
            if label != 'INBOX':
                wf.add_item("Move To Inbox", "", arg=json.dumps({
                    'thread_id': thread_id,
                    'action': 'move_to_inbox',
                }), valid=True)
            wf.add_item("Mark As Unread", "", arg=json.dumps({
                'thread_id': thread_id,
                'action': 'mark_as_unread',
                'query': query,
            }), valid=True)

            wf.add_item("Quick Reply", "", autocomplete='%s reply ' %
                        query, valid=False)
            wf.add_item("Add label", "", autocomplete='%s label ' %
                        query, valid=False)
            # wf.add_item("Show Inbox", "", autocomplete=' ', valid=False)

        wf.send_feedback()
        return 0

    if query and any(query.startswith(label) for label in config.SYSTEM_LABELS):
        query = query.split()
        label = query[0]
        label_query = ' '.join(query[1:]) if len(query) > 0 else ''
        if not wf.cached_data_fresh('gmail_%s' % label.lower(), max_age=3600):
            refresh_cache(label)
        item_list = wf.cached_data('gmail_%s' % label.lower(), max_age=0)
        wf.logger.debug(item_list)

        if item_list is not None:
            if len(item_list) == 0:
                wf.add_item('No mails found!', valid=False)
            else:
                for index, item in enumerate(item_list):
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

                    title = title.decode('utf-8', 'ignore')
                    subtitle = subtitle.decode('utf-8', 'ignore')

                    if label_query.lower() in ' '.join([title, subtitle]).lower():
                        wf.add_item(
                            title, subtitle, autocomplete=autocomplete, valid=False)
        else:
            wf.add_item("Could receive your emails.",
                        "Please try again or file a bug report!", valid=False)

        wf.send_feedback()
        return 0

    for label, name in config.SYSTEM_LABELS.iteritems():
        wf.add_item(name, autocomplete='%s ' % label, valid=False)

    # Update list in background
    # if not wf.cached_data_fresh('gmail_list', max_age=30):
    #     background_refresh(wf)

    wf.send_feedback()


def background_refresh(wf):
    if not is_running('gmail_refresh'):
        cmd = ['/usr/bin/python', wf.workflowfile('gmail_refresh.py')]
        run_in_background('gmail_refresh', cmd)


if __name__ == '__main__':
    wf = Workflow(update_info={
        'github_slug': 'fniephaus/alfred-gmail',
        'version': 'v0.2',
    })
    sys.exit(wf.run(main))
