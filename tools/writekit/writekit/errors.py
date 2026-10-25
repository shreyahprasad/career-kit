"""
Why a change was not made. The message says why in your words, and the page shows it as is;
create_writer() turns each into its HTTP status.
"""


class Refused(Exception):
    """The change cannot be made as asked, given what is saved now. 409."""


class NotFound(Exception):
    """The thing to change is not there. 404."""


class Rejected(Exception):
    """What was sent is not something that can be saved, whatever is saved now. 400."""
