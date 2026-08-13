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


def chore_state(task, today=None):
    """The (label, colour) pair for a chore. Overdue outranks the raw status because a
    blown deadline is the thing that matters about a chore that is still open."""
    if is_overdue(task, today):
        return OVERDUE_LABEL, OVERDUE_COLOR
    return status_label(task['status']), STATUS_COLORS.get(task['status'], 'gray')
