PENDING_ACTIONS = {}
BROADCAST_DRAFTS = {}
PROFILE_DRAFTS = {}
CONSUMED_PENDING_MESSAGES = set()


def pending_message_key(message):
    return (
        getattr(getattr(message, "chat", None), "id", None),
        getattr(message, "message_id", None),
    )


def mark_pending_message_consumed(message):
    if len(CONSUMED_PENDING_MESSAGES) > 1000:
        CONSUMED_PENDING_MESSAGES.clear()

    CONSUMED_PENDING_MESSAGES.add(pending_message_key(message))


def is_pending_message_consumed(message):
    return pending_message_key(message) in CONSUMED_PENDING_MESSAGES
