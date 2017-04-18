import json
from gmail_refresh import refresh_cache
from workflow import Workflow
from workflow.background import run_in_background, is_running

import config

# Set delimiter to be used in thread queries
THREAD_DELIMITER = 't:'
# GitHub repo for self-updating
GITHUB_UPDATE_CONF = {'github_slug': 'fniephaus/alfred-gmail'}
# GitHub Issues
HELP_URL = 'https://github.com/fniephaus/alfred-gmail/issues'

WF = Workflow(update_settings=GITHUB_UPDATE_CONF, help_url=HELP_URL)


def main():
    if WF.first_run:
        WF.clear_cache()

    register_magic_arguments()

    if WF.update_available:
        WF.add_item('An update is available!',
                    icon=get_icon('cloud-download'),
                    autocomplete='workflow:update',
                    valid=False
                    )

    # Get user input
    query = None
    if len(WF.args):
        query = WF.args[0]

    if query and THREAD_DELIMITER in query:
        label = query.split()[0]
        thread_query = query[
            query.find(THREAD_DELIMITER) + len(THREAD_DELIMITER):].split()
        if len(thread_query) == 0:
            WF.add_item(
                'Missing Thread ID', icon=get_icon('alert'), valid=False)
            WF.send_feedback()
            return 0

        thread_id = thread_query[0]
        label_threads = WF.cached_data('gmail_%s' % label.lower(), max_age=0)
        if label_threads is None:
            WF.add_item('Caching problem', icon=get_icon('alert'), valid=False)
            WF.send_feedback()
            return 0

        selected_thread = None
        for thread in label_threads:
            if thread['threadId'] == thread_id:
                selected_thread = thread

        if selected_thread is None:
            WF.add_item(
                'Invalid Thread ID', icon=get_icon('alert'), valid=False)
            WF.send_feedback()
            return 0

        if len(thread_query) > 1 and 'reply' in thread_query[1]:
            message = ' '.join(thread_query[2:])
            valid = len(message) > 0
            subtitle = ('Hit enter to send reply' if valid else
                        'Start typing your reply')
            arg = json.dumps({
                'thread_id': thread_id,
                'message_id': None,
                'action': 'reply',
                'message': message
            })
            WF.add_item(message,
                        subtitle,
                        icon=get_icon('pencil'),
                        arg=arg,
                        valid=valid
                        )
        elif len(thread_query) > 1 and 'label' in thread_query[1]:
            label_list = WF.cached_data('gmail_labels', max_age=0)
            if label_list:
                if len(thread_query) > 2:
                    label_list = [l for l in label_list
                                  if ' '.join(thread_query[2:]).lower() in
                                  l['name'].lower()]
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
                            label['name'],
                            'Hit enter to add this label',
                            icon=get_icon('tag'),
                            arg=arg,
                            valid=True)
                else:
                    WF.add_item(
                        'No label found',
                        'Please try again!',
                        icon=get_icon('alert'),
                        valid=False
                    )
            else:
                WF.add_item(
                    'Could not fetch labels',
                    'Please try again or file a bug report!',
                    icon=get_icon('alert'),
                    valid=False
                )
        else:
            add_mail_actions(
                thread_id,
                query,
                selected_thread['Subject'],
                selected_thread['snippet'],
                label
            )

        WF.send_feedback()
        return 0

    if query and any(query.startswith(l) for l in config.SYSTEM_LABELS):
        query = query.split()
        label = query[0]
        label_query = ' '.join(query[1:]) if len(query) > 0 else ''
        if not WF.cached_data_fresh('gmail_%s' % label.lower(), max_age=3600):
            refresh_cache([label])
        item_list = WF.cached_data('gmail_%s' % label.lower(), max_age=0)

        if item_list is not None:
            if len(item_list) == 0:
                WF.add_item(
                    'No mails found!',
                    icon=get_icon('alert'), autocomplete='', valid=False)
            else:
                add_mails(item_list, label, label_query)

            WF.add_item(
                '...',
                icon=get_icon('mail-reply'),
                autocomplete='',
                valid=False
            )
        else:
            WF.add_item('Could receive your emails.',
                        'Please try again or file a bug report!',
                        icon=get_icon('alert'),
                        valid=False
                        )

        WF.send_feedback()
        return 0

    for label, name in config.SYSTEM_LABELS.iteritems():
        if not query or query.lower() in name.lower():
            WF.add_item(
                name,
                icon=get_icon('inbox'),
                autocomplete='%s ' % label, valid=False)

    # Update list in background
    if not WF.cached_data_fresh('gmail_inbox', max_age=30):
        background_refresh()

    WF.send_feedback()


def add_mails(item_list, label, label_query):
    for index, item in enumerate(item_list):
        name = 'Unknown'
        if item['From']:
            name = item['From'][
                :item['From'].find('<') - 1].replace('"', '')
        if item['messages_count'] > 1:
            title = '%s (%s): %s' % (
                name, item['messages_count'], item['Subject'])
        else:
            title = '%s: %s' % (
                name, item['Subject'])
        icon = get_icon('mail') if item[
            'unread'] else get_icon('mail-read')
        subtitle = '%s - %s' % (item['Date'], item['snippet'])
        autocomplete = '%s %s%s' % (
            label, THREAD_DELIMITER, item['threadId'])

        if label_query.lower() in ' '.join([title, subtitle]).lower():
            WF.add_item(
                title,
                subtitle,
                icon=icon,
                autocomplete=autocomplete,
                valid=False
            )


def add_mail_actions(thread_id, query, title, snippet, label):
    WF.add_item(title, snippet, icon=get_icon('info'), arg=json.dumps({
        'thread_id': thread_id,
        'action': 'open',
        'label': label,
    }), valid=True)

    WF.add_item('Mark As Read', icon=get_icon('mail-read'), arg=json.dumps({
        'thread_id': thread_id,
        'action': 'mark_as_read',
        'query': query,
    }), valid=True)

    WF.add_item('Archive', icon=get_icon('package'), arg=json.dumps({
        'thread_id': thread_id,
        'action': 'archive_conversation',
        'label': label,
    }), valid=True)

    if label != 'TRASH':
        WF.add_item('Move To Trash', icon=get_icon('trashcan'),
                    arg=json.dumps({
                        'thread_id': thread_id,
                        'action': 'trash_conversation',
                        'label': label,
                    }), valid=True)

    if label != 'INBOX':
        WF.add_item('Move To Inbox', icon=get_icon('inbox'), arg=json.dumps({
            'thread_id': thread_id,
            'action': 'move_to_inbox',
            'label': label,
        }), valid=True)

    WF.add_item('Mark As Unread', icon=get_icon('mail'), arg=json.dumps({
        'thread_id': thread_id,
        'action': 'mark_as_unread',
        'query': query,
    }), valid=True)

    WF.add_item('Quick Reply', icon=get_icon('pencil'),
                autocomplete='%s reply ' % query, valid=False)
    WF.add_item('Add label', icon=get_icon('tag'),
                autocomplete='%s label ' % query, valid=False)
    WF.add_item(
        '...', icon=get_icon('mail-reply'), autocomplete=label, valid=False)


def get_icon(name):
    name = '%s-dark' % name if is_dark() else name
    return 'icons/%s.png' % name


def is_dark():
    rgb = [int(x) for x in WF.alfred_env['theme_background'][5:-6].split(',')]
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255 < 0.5


def register_magic_arguments():
    WF.magic_prefix = 'wf:'

    def delete_access_token():
        WF.delete_password('gmail_credentials')
        return 'Access token has been deleted successfully.'
    WF.magic_arguments['deauth'] = delete_access_token


def background_refresh():
    if not is_running('gmail_refresh'):
        cmd = ['/usr/bin/python', WF.workflowfile('gmail_refresh.py')]
        run_in_background('gmail_refresh', cmd)


if __name__ == '__main__':
    main()
