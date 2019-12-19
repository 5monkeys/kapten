import socket
from typing import Any, Dict, List, Optional, Union

import requests

from .log import logger


def post(
    token: str,
    text: str,
    fields: Optional[List[Dict[str, Any]]] = None,
    fallback: Optional[str] = None,
    channel: Optional[str] = None,
) -> bool:
    logger.debug("Notifying Slack...")
    payload: Dict[str, Union[str, List[Dict]]] = {
        "username": "Kapten",
        "icon_url": "https://raw.githubusercontent.com/5monkeys/kapten/master/kapten.png",
        "text": text,
    }
    if channel:
        payload["channel"] = channel
    if fields:
        payload["attachments"] = [
            {"color": "#50ba32", "fallback": fallback or text, "fields": fields}
        ]

    response = requests.post(f"https://hooks.slack.com/services/{token}", json=payload)

    return response.text == "ok"


def notify(
    token: str,
    service_name: str,
    image_digest: str,
    channel: Optional[str] = None,
    **kwargs: Any,
) -> bool:
    project = kwargs.get("project", service_name)
    hostname = socket.gethostname()

    # Host:
    fields = [{"title": "Host", "value": hostname, "short": True}]

    # Stack:
    if "stack" in kwargs:
        fields.append({"title": "Stack", "value": kwargs["stack"], "short": True})

    # Image:
    if "image" in kwargs:
        fields.append({"title": "Image", "value": kwargs["image"], "short": True})

    # Service:
    fields.append(
        {
            "title": "Service",
            "value": kwargs.get("service_short_name", service_name),
            "short": True,
        }
    )

    # Digest:
    fields.append({"title": "Digest", "value": image_digest, "short": False})

    return post(
        token,
        channel=channel,
        text=f"Deployment of *{project}* has started.",
        fallback=f"Deploying {service_name}, {image_digest}",
        fields=fields,
    )
