from enum import Enum


class KBSourceType(str, Enum):
    upload_pdf = "upload_pdf"
    upload_txt = "upload_txt"
    url = "url"
    text = "text"
    other = "other"


class KBStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
