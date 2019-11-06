import json
import re
from collections import defaultdict
from functools import partial
from unittest import mock

import asynctest
from httpx.models import AsyncResponse

GET = "GET"
POST = "POST"

istype = lambda t, o: isinstance(o, t)
isregex = partial(istype, type(re.compile("")))


class HTTPXMock:
    def __init__(self):
        self.pattern_map = defaultdict(list)
        self.patterns = {}
        self.calls = []

    def __enter__(self):
        mocked_dispatcher = mock.MagicMock()
        mocked_dispatcher.return_value.send = asynctest.CoroutineMock()
        mocked_dispatcher.return_value.send.side_effect = self.mocked_dispatcher_send
        self.patcher = mock.patch(
            "httpx.client.BaseClient._dispatcher_for_request", mocked_dispatcher
        )
        self.patcher.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.patcher.stop()

    def add(
        self,
        method,
        url,
        status_code=None,
        content=None,
        content_type="text/plain",
        alias=None,
        **kwargs
    ):
        pattern = mock.MagicMock(
            url=url,
            response={
                "status_code": status_code,
                "content": content,
                "content_type": content_type,
                **kwargs,
            },
        )
        self.pattern_map[method].append(pattern)
        if alias:
            self.patterns[alias] = pattern
        return pattern

    def match(self, request):
        for i, pattern in enumerate(list(self.pattern_map[request.method])):
            if isregex(pattern.url):
                match = pattern.url.match(str(request.url))
                if match:
                    return pattern, match.groupdict()

            elif pattern.url == str(request.url):
                return pattern, {}

        return None, {}

    def mocked_dispatcher_send(self, request, verify=None, cert=None, timeout=None):
        # Match request against added request patterns
        match, content_kwargs = self.match(request)
        _response = match.response if match is not None else {}

        # Get and encode content
        content = _response.get("content")
        if isinstance(content, Exception):
            raise content
        if callable(content):
            content = content(**content_kwargs)
        if content is not None and _response.get("content_type") == "application/json":
            content = json.dumps(content)
        content = content.encode("utf-8") if content else b""

        # Create response
        response = AsyncResponse(
            status_code=_response.get("status_code") or 200,
            http_version=_response.get("http_version"),
            headers=_response.get("headers"),
            content=content,
            request=request,
        )

        # Update call stats
        if match is not None:
            match(request=request, response=response)
            call = match.mock_calls[-1]
        else:
            call = mock.call(request=request, response=response)
        self.calls.append(call)

        return response
