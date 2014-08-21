from collections import OrderedDict

# Path to the client_secret.json file downloaded from the Developer Console
CLIENT_SECRET_FILE = 'client_secret.json'

# Check https://developers.google.com/gmail/api/auth/scopes for all
# available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/gmail.modify'

SYSTEM_LABELS = OrderedDict([
    ('INBOX', 'Inbox'),
    ('UNREAD', 'Unread'),
    ('STARRED', 'Starred'),
    ('DRAFT', 'Drafts'),
    ('SPAM', 'Spam'),
    ('TRASH', 'Trash'),
    ('SENT', 'Sent'),
    ('CATEGORY_UPDATES', 'Updates'),
    ('CATEGORY_PROMOTIONS', 'Promotions'),
    ('CATEGORY_SOCIAL', 'Social'),
    ('CATEGORY_PERSONAL', 'Personal'),
    ('CATEGORY_FORUMS', 'Forums'),
])
