import hashlib
import hmac
import json
from typing import Any, Dict, List, Tuple, Union

from starlette.datastructures import Secret

from .log import logger


def validate_signature(
    secret: Union[str, Secret], request_body: bytes, signature: str
) -> bool:
    """
    See also:
        https://developer.github.com/webhooks/#delivery-headers
    for how GitHub creates the signature
    """
    if not signature:
        logger.debug("No signature value")
        return False

    try:
        digest = hmac.new(
            key=bytes(str(secret), "utf-8"), msg=request_body, digestmod=hashlib.sha1,
        )
        return hmac.compare_digest("sha1={}".format(digest.hexdigest()), signature)
    except (ValueError, TypeError) as e:
        logger.error(e)
        return False
    except Exception as e:  # pragma: nocover
        logger.critical(e)
        return False


def parse_webhook_payload(
    payload: Dict[str, Any], tracked_repositories: List[str]
) -> Tuple[str, str]:
    # Validate payload structure
    valid_structure = payload and all(
        [
            "deployment" in payload,
            "statuses_url" in payload.get("deployment", {}),
            "payload" in payload.get("deployment", {}),
            "digest" in payload.get("deployment", {}).get("payload", {}),
            "tag" in payload.get("deployment", {}).get("payload", {}),
            "image" in payload.get("deployment", {}).get("payload", {}),
            "repository" in payload,
            "full_name" in payload.get("repository", {}),
        ]
    )
    if not valid_structure:
        raise ValueError("Invalid GitHub payload")

    deployment_payload = json.loads(payload["deployment"]["payload"])
    image = deployment_payload["image"]
    if image not in tracked_repositories:
        raise ValueError("No image value")

    callback_url = payload["deployment"]["statuses_url"]
    if not callback_url.startswith("https://api.github.com/repos/"):
        raise ValueError("Invalid GitHub callback url: {}".format(callback_url))

    tag = deployment_payload["tag"]
    if not tag:
        raise ValueError("No tag value")

    # Format: <IMAGE>@<DIGEST> where DIGEST is prefixed with: 'sha256' expected
    digest = deployment_payload["digest"]
    if "@" not in digest:
        raise ValueError("Invalid digest value: {}".format(digest))
    digest = digest.split("@")[1]
    if not digest.startswith("sha256:"):
        raise ValueError("Invalid digest value: {}".format(digest))

    return f"{image}:{tag}@{digest}", callback_url
