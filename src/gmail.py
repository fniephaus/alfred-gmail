import datetime
import sys
from gmail_refresh import refresh_cache
from workflow import Workflow, PasswordNotFound, MATCH_SUBSTRING
from workflow.background import run_in_background, is_running


def main(wf):
    if len(wf.args):
        query = wf.args[0]
    else:
        query = None

    if not wf.cached_data_fresh('gmail_list', max_age=3600):
        refresh_cache()
    item_list = wf.cached_data('gmail_list', None, max_age=0)

    if item_list is not None:
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
                arg = '%s %s' % (item['threadId'], item['id'])

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
