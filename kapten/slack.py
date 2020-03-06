import asyncio
import socket
from itertools import groupby
from typing import Any, Dict, List, Optional, Union

import httpx

from .docker import Service
from .log import logger


async def post(
    token: str,
    text: str,
    fields: Optional[List[Dict[str, Any]]] = None,
    fallback: Optional[str] = None,
    channel: Optional[str] = None,
) -> bool:
    logger.debug("Notifying Slack...")

    channels: List[Optional[str]] = []

    if channel is not None:
        channels = [c.strip() for c in channel.split(",")]
    else:
        channels = [None]

    payload: Dict[str, Union[str, List[Dict]]] = {
        "username": "Kapten",
        "icon_url": "https://raw.githubusercontent.com/5monkeys/kapten/master/kapten.png",
        "text": text,
    }

    if fields:
        payload["attachments"] = [
            {"color": "#50ba32", "fallback": fallback or text, "fields": fields}
        ]

    posts = []
    for channel in channels:
        if channel:
            payload["channel"] = channel

        posts.append(
            httpx.post(f"https://hooks.slack.com/services/{token}", json=payload)
        )

        payload.pop("channels", None)

    responses = await asyncio.gather(*posts, return_exceptions=True)

    return all([response.text == "ok" for response in responses])


async def notify(
    token: str,
    services: List[Service],
    *,
    project: Optional[str] = None,
    channel: Optional[str] = None,
) -> bool:
    results = []

    # Host:
    hostname = socket.gethostname()

    digest_key = lambda s: s.digest
    grouped_services = groupby(sorted(services, key=digest_key), key=digest_key)

    for digest, digest_services in grouped_services:
        service_group = list(digest_services)
        service = service_group[0]
        digest_project = project or service.stack or service.short_name

        fields = [{"title": "Host", "value": hostname, "short": True}]

        # Stack:
        stack_names = sorted({s.stack or "(none)" for s in service_group})
        stack_list = "\n".join(f"\u2022 {name}" for name in stack_names)
        fields.append(
            {
                "title": "Stacks" if len(stack_names) > 1 else "Stack",
                "value": stack_list,
                "short": True,
            }
        )

        # Image:
        fields.append({"title": "Image", "value": service.image, "short": True})

        # Digest:
        fields.append({"title": "Digest", "value": digest, "short": False})

        # Service:
        service_names = sorted(s.short_name for s in service_group)
        service_list = "\n".join(f"\u2022 {name}" for name in service_names)
        fields.append(
            {
                "title": "Services" if len(service_group) > 1 else "Service",
                "value": service_list,
                "short": False,
            }
        )

        result = await post(
            token,
            channel=channel,
            text=f"Deployment of *{digest_project}* has started.",
            fallback=f"Deploying {digest_project}, {digest}",
            fields=fields,
        )
        results.append(result)

    return all(results)
