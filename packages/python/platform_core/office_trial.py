"""Bounded unpaid trial: one expiring in-memory DOCX per allowlisted owner."""

import time
from dataclasses import dataclass, replace
from threading import Lock
from uuid import uuid4

from platform_core.office_docx import DocxArtifact, OfficeBlock, OfficeDocument, render_docx

MAX_TRIAL_TEXT = 4000
MAX_TRIAL_OWNERS = 20
MAX_CACHE_BYTES = 8 * 1024 * 1024


class TrialRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TrialPolicy:
    enabled: bool = False
    allowed_users: frozenset[int] = frozenset()
    ttl_seconds: int = 900


@dataclass(frozen=True)
class TrialFile:
    token: str
    owner_id: int
    request_id: int
    expires_at: float
    artifact: DocxArtifact
    delivery_state: str = "pending"
    delivered_message_id: int | None = None


def _authorize(owner_id: int, policy: TrialPolicy) -> None:
    if (type(owner_id) is not int or owner_id <= 0 or not policy.enabled
            or owner_id not in policy.allowed_users):
        raise TrialRejected("trial_unavailable")
    if (not 1 <= len(policy.allowed_users) <= MAX_TRIAL_OWNERS
            or type(policy.ttl_seconds) is not int or not 60 <= policy.ttl_seconds <= 3600):
        raise TrialRejected("invalid_trial_policy")


def parse_trial_text(payload: str) -> OfficeDocument:
    if not isinstance(payload, str) or not 1 <= len(payload) <= MAX_TRIAL_TEXT:
        raise TrialRejected("trial_text_limit")
    title, separator, body = payload.replace("\r\n", "\n").replace("\r", "\n").partition("\n")
    if not separator or not title.strip() or not body.strip():
        raise TrialRejected("trial_title_and_body_required")
    return OfficeDocument(title.strip(), tuple(OfficeBlock(p) for p in body.split("\n\n")))


class OfficeTrial:
    """Single-process cache, not durable orders, storage, financial or jobs state."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = Lock()
        self._files: dict[int, TrialFile] = {}
        # Bounded message tombstones prevent an expired/replaced request replay
        # from creating a new file. All state disappears on process restart.
        self._last_requests: dict[int, int] = {}

    @staticmethod
    def require_access(owner_id: int, policy: TrialPolicy) -> None:
        _authorize(owner_id, policy)

    def _purge_locked(self) -> None:
        now = self._clock()
        for owner in list(self._files):
            if self._files[owner].expires_at <= now:
                del self._files[owner]

    def purge_expired(self) -> None:
        with self._lock:
            self._purge_locked()

    def create(self, owner_id: int, request_id: int, payload: str,
               policy: TrialPolicy) -> TrialFile:
        _authorize(owner_id, policy)
        if type(request_id) is not int or request_id <= 0:
            raise TrialRejected("invalid_trial_request")
        with self._lock:
            self._purge_locked()
            last = self._last_requests.get(owner_id, 0)
            if request_id <= last:
                cached = self._files.get(owner_id)
                if request_id == last and cached is not None:
                    return cached
                raise TrialRejected("trial_request_replayed")
            current = self._files.get(owner_id)
            if current is not None and current.delivery_state == "sending":
                raise TrialRejected("trial_delivery_busy")
            if owner_id not in self._last_requests and len(self._last_requests) >= MAX_TRIAL_OWNERS:
                raise TrialRejected("trial_capacity")
            artifact = render_docx(parse_trial_text(payload))
            retained = sum(len(f.artifact.content) for owner, f in self._files.items()
                           if owner != owner_id)
            if retained + len(artifact.content) > MAX_CACHE_BYTES:
                raise TrialRejected("trial_capacity")
            result = TrialFile(uuid4().hex, owner_id, request_id,
                               self._clock() + policy.ttl_seconds, artifact)
            self._files[owner_id] = result
            self._last_requests[owner_id] = request_id
            return result

    def _get_locked(self, owner_id: int, token: str) -> TrialFile:
        self._purge_locked()
        result = self._files.get(owner_id)
        if result is None or result.token != token:
            # Wrong owner, stale token and expiry share one non-disclosing code.
            raise TrialRejected("trial_file_unavailable")
        return result

    def get(self, owner_id: int, token: str, policy: TrialPolicy) -> TrialFile:
        _authorize(owner_id, policy)
        with self._lock:
            return self._get_locked(owner_id, token)

    def acknowledge(self, owner_id: int, token: str, chat_id: int, message_id: int,
                    policy: TrialPolicy) -> None:
        _authorize(owner_id, policy)
        if chat_id != owner_id or type(message_id) is not int or message_id <= 0:
            raise TrialRejected("invalid_trial_receipt")
        with self._lock:
            result = self._get_locked(owner_id, token)
            if result.delivery_state != "sending":
                raise TrialRejected("invalid_trial_receipt")
            self._files[owner_id] = replace(result, delivery_state="delivered",
                                            delivered_message_id=message_id)

    def claim_delivery(self, owner_id: int, token: str, policy: TrialPolicy,
                       explicit_retry: bool = False) -> TrialFile | None:
        _authorize(owner_id, policy)
        with self._lock:
            result = self._get_locked(owner_id, token)
            if result.delivery_state == "sending":
                raise TrialRejected("trial_delivery_busy")
            if result.delivery_state != "pending" and not explicit_retry:
                return None
            claimed = replace(result, delivery_state="sending")
            self._files[owner_id] = claimed
            return claimed

    def release_delivery(self, owner_id: int, token: str, policy: TrialPolicy) -> None:
        _authorize(owner_id, policy)
        with self._lock:
            result = self._get_locked(owner_id, token)
            if result.delivery_state == "sending":
                self._files[owner_id] = replace(result, delivery_state="uncertain")
