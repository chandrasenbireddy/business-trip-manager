"""Secret Manager credential resolution (constitution Principle XIII).

Callers pass a Secret Manager *path*, never a credential value, across any
function/tool boundary. Resolution happens here, at the point of use, and the
resolved value MUST NOT be cached, logged, or returned to a caller that isn't
about to use it immediately.
"""

from functools import lru_cache

from google.cloud import secretmanager

_GCP_PROJECT = "humain-494919"


@lru_cache(maxsize=1)
def _client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


def resolve(secret_path: str, version: str = "latest") -> str:
    """Resolve a Secret Manager path like `{tenant_id}/{user_id}/google_calendar_token`
    or a platform-level path like `btm/transactional_email_api_key` to its value.

    ponytail: no in-process cache here — a cached OAuth token would violate
    Principle XII's "not held in memory beyond the request lifecycle."
    Resolve fresh on every call.
    """
    name = f"projects/{_GCP_PROJECT}/secrets/{secret_path.replace('/', '_')}/versions/{version}"
    response = _client().access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
