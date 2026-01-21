import enum


class KBSourceType(enum.Enum):
    upload_pdf = "upload_pdf"
    upload_txt = "upload_txt"
    url = "url"
    text = "text"
    other = "other"


class KBStatus(enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JobState(enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
