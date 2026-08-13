"""One vocabulary for chore state, shared by every page that shows a chore.

The pages disagreed before this existed. The same overdue chore read "Overdue" on My
Chores, "To Do" in the Chore Reports picker and "in_progress" in the RA task table, so
comparing two residents' pages meant comparing two different naming schemes.

Anything that puts a chore's state in front of a user should get it from here.
"""

from datetime import date
from email.utils import parsedate_to_datetime

# Mirrors the ENUM on Tasks.status
STATUS_LABELS = {
    'todo': 'To Do',
    'in_progress': 'In Progress',
    'done': 'Done',
    'missed': 'Missed',
}

STATUS_COLORS = {
    'todo': 'gray',
    'in_progress': 'blue',
    'done': 'green',
    'missed': 'red',
}

OVERDUE_LABEL = 'Overdue'
OVERDUE_COLOR = 'red'

# Room_Reports.Status and Requests.Status are separate vocabularies from a chore's, and
# they used to live as private dicts on the two pages that render them -- where 'open'
# was red for a report and blue for a request. They sit here so a resident reading two
# pages is reading one colour scheme.
REPORT_STATUS_BADGES = {
    'open': ('Open', 'red'),
    'reviewed': ('Reviewed', 'blue'),
    'closed': ('Closed', 'green'),
}

INTERVENTION_STATUS_BADGES = {
    'pending': ('Pending', 'orange'),
    'active': ('Active', 'blue'),
    'closed': ('Closed', 'green'),
}

REQUEST_STATUS_COLORS = {
    'open': 'orange',
    'in_progress': 'blue',
    'resolved': 'green',
    'rejected': 'red',
}

# A request that has been picked up is still waiting on someone, so both statuses count
# as in flight. Splitting them was why "Mine still open" plus resolved plus rejected did
# not add up to "Requests I've filed".
REQUEST_IN_FLIGHT = ('open', 'in_progress')


def status_label(status):
    """The display name for a raw status value. Unknown values fall back to a readable
    form of themselves rather than disappearing."""
    return STATUS_LABELS.get(status, str(status).replace('_', ' ').title())


def to_due_date(task):
    """Flask serializes DATE columns as RFC 2822, e.g. 'Wed, 13 Aug 2026 00:00:00 GMT'."""
    raw = task.get('due_date')
    return parsedate_to_datetime(raw).date() if raw else None


def is_overdue(task, today=None):
    """Past its deadline with the work still outstanding.

    'missed' is not overdue: the chore has already been marked down, so it reads as
    Missed. A finished chore is never overdue whatever its date says.
    """
    if task['status'] in ('done', 'missed'):
        return False
    due = to_due_date(task)
    return due is not None and due < (today or date.today())


def is_reportable(task, today=None):
    """Whether a roommate could file a report about this chore.

    A report says the chore was skipped, so it needs a deadline that has passed -- or a
    chore already marked missed, which is that judgement having been made. Mirrors the
    rules POST /room_report/room_reports enforces, minus the ones about who is asking.
    """
    if task['status'] == 'done':
        return False
    return task['status'] == 'missed' or is_overdue(task, today)


def chore_state(task, today=None):
    """The (label, colour) pair for a chore. Overdue outranks the raw status because a
    blown deadline is the thing that matters about a chore that is still open."""
    if is_overdue(task, today):
        return OVERDUE_LABEL, OVERDUE_COLOR
    return status_label(task['status']), STATUS_COLORS.get(task['status'], 'gray')


# The order chores are read in: what is coming, what is late, what was written off, what
# is finished.
BUCKETS = ('upcoming', 'overdue', 'missed', 'completed')


def bucket_chores(tasks, today=None):
    """Split a resident's chores into the four buckets, each chore landing in exactly one.

    Every page used to draw its own line through the same rows. My Chores asked the API
    four separate questions, one of which -- 'created' -- answered about a different set
    of people entirely, so the tab counts did not add up to anything. The others each
    re-derived overdue locally, or forgot to.

    Pass the chores assigned to one resident and the four counts add up to that list.
    """
    buckets = {name: [] for name in BUCKETS}
    for task in tasks:
        status = task['status']
        if status == 'done':
            buckets['completed'].append(task)
        elif status == 'missed':
            buckets['missed'].append(task)
        elif is_overdue(task, today):
            buckets['overdue'].append(task)
        else:
            buckets['upcoming'].append(task)
    return buckets


def by_due_date(tasks, reverse=False):
    """Chores in deadline order. Undated ones sort last either way -- they have no
    deadline to be early or late for, and dropping them silently hid live chores."""
    dated = sorted((t for t in tasks if to_due_date(t)),
                   key=to_due_date, reverse=reverse)
    return dated + [t for t in tasks if not to_due_date(t)]
