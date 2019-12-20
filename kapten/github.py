import hashlib
import hmac
import json
from typing import Any, Dict, List, Tuple, Union

import httpx
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
            "repository" in payload,
            "full_name" in payload.get("repository", {}),
        ]
    )
    if not valid_structure:
        raise ValueError("Invalid GitHub payload")

    try:
        deployment_payload = json.loads(payload["deployment"]["payload"])
    except json.JSONDecodeError:
        raise ValueError("Supplied deployment payload is not valid JSON")

    valid_deployment_payload_structure = deployment_payload and all(
        [
            "digest" in deployment_payload,
            "tag" in deployment_payload,
            "image" in deployment_payload,
            isinstance(deployment_payload["digest"], str),
            isinstance(deployment_payload["tag"], str),
            isinstance(deployment_payload["image"], str),
        ]
    )
    if not valid_deployment_payload_structure:
        raise ValueError("Invalid deployment payload")

    image = deployment_payload["image"]
    if image not in tracked_repositories:
        raise ValueError(f"Supplied image in deployment payload not tracked: {image}")

    callback_url = payload["deployment"]["statuses_url"]
    if not callback_url.startswith("https://api.github.com/repos/"):
        raise ValueError(f"Invalid GitHub callback URL: {callback_url}")

    tag = deployment_payload["tag"]
    if not tag:
        raise ValueError("Missing tag in deployment payload")

    # Format: <IMAGE>@<DIGEST> where DIGEST is prefixed with: 'sha256' expected
    _, separator, digest = deployment_payload["digest"].rpartition("@")
    if not separator or not digest.startswith("sha256:"):
        raise ValueError(
            "Invalid deployment payload digest value: {}".format(
                deployment_payload["digest"]
            )
        )

    return f"{image}:{tag}@{digest}", callback_url


async def callback(url: str, state: str, environment: str, description: str) -> bool:
    # TODO: Also accept: 'log_url', 'environment_url'
    # TODO: Authentication (token?) for GitHub API
    valid_states = {
        "error",
        "failure",
        "inactive",
        "in_progress",
        "queued",
        "pending",
        "success",
    }
    if state not in valid_states:
        raise ValueError(f"Invalid state: {state}")

    # Header required for state: "in_progress" and "queued" as well as
    # the "environment" parameter. See:
    #   https://developer.github.com/v3/repos/deployments/#create-a-deployment-status
    headers = {"Accept": "application/vnd.github.flash-preview+json"}
    data = {
        "state": state,
        "description": description,
        "environment": environment,
    }
    async with httpx.Client(headers=headers) as client:
        try:
            response = await client.request("POST", url, json=data)
        except Exception as e:  # pragma: nocover
            # TODO: Retry
            logger.critical(e)
            return False

        if response.is_error:
            error = response.json()
            logger.critical("Error response from GitHub: %r", error)
            return False

        return True
