import sys
import json
from gmail_refresh import refresh_cache
from workflow import Workflow, PasswordNotFound, MATCH_SUBSTRING
from workflow.background import run_in_background, is_running


THREAD_DELIMITER = 'thread:'

def main(wf):
    if len(wf.args):
        query = wf.args[0]
    else:
        query = None

    if query and THREAD_DELIMITER in query:
        thread_query = query[query.find(THREAD_DELIMITER) + len(THREAD_DELIMITER):].split()
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
                'action': 'reply',
                'thread_id': thread_id,
                'message': message
            })
            wf.add_item(message, subtitle, arg=arg valid=valid)
        elif len(thread_query) > 1 and 'label' in thread_query[1]:
            label_list = wf.cached_data('gmail_labels')
            if label_list:
                if len(thread_query) > 2:
                    label_list = [label for label in label_list
                        if ' '.join(thread_query[2:]).lower() in label.lower()]
                if len(label_list):
                    for label in label_list:
                        wf.add_item(label, "Hit enter to add this label", valid=True)
                else:
                    wf.add_item("No label found", "Please try again!", valid=False)
            else:
                wf.add_item("Could not fetch labels", "Please try again or file a bug report!", valid=False)
        else:
            wf.add_item("Quick Reply", "", autocomplete='%s reply ' % query, valid=False)
            wf.add_item("Add label", "", autocomplete='%s label ' % query, valid=False)

        wf.send_feedback()
        return 0

    if not wf.cached_data_fresh('gmail_list', max_age=3600):
        refresh_cache()
    item_list = wf.cached_data('gmail_list')

    if item_list:
        if len(item_list) == 0:
            wf.add_item('Your Gmail inbox is empty!', valid=False)
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

                arg = json.dumps({
                    'thread_id': item['threadId'],
                    'message_id': item['id'],
                    'query': query
                })

                title = title.decode('utf-8', 'ignore')
                subtitle = subtitle.decode('utf-8', 'ignore')

                if not query or query.lower() in ' '.join([title, subtitle]).lower():
                    wf.add_item(title, subtitle, arg=arg, valid=True)
    else:
        wf.add_item("Could receive your emails.",
                    "Please try again or file a bug report!", valid=False)
    
    # Update list in background
    if not wf.cached_data_fresh('gmail_list', max_age=30):
        background_refresh(wf)

    wf.send_feedback()


def background_refresh(wf):
    if not is_running('gmail_refresh'):
        cmd = ['/usr/bin/python', wf.workflowfile('gmail_refresh.py')]
        run_in_background('gmail_refresh', cmd)


if __name__ == '__main__':
    wf = Workflow()
    sys.exit(wf.run(main))
