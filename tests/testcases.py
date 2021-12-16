import contextlib
import json
import os
import re
from functools import partial
from io import StringIO
from itertools import chain, repeat
from random import randint
from unittest import mock

import asynctest
import httpx
import respx
from httpx.exceptions import ConnectTimeout


class KaptenTestCase(asynctest.TestCase):
    def setUp(self):
        # Mock logger
        self.logger_mock = mock.MagicMock()
        modules = ["cli", "tool", "slack", "server"]
        for module in modules:
            mocker = mock.patch(f"kapten.{module}.logger", self.logger_mock)
            mocker.start()
            self.addCleanup(mocker.stop)

        respx.start()

    def tearDown(self):
        respx.stop()

    def build_sys_args(self, services, *args):
        service_names = [name for name, _ in services]
        argv = list(chain(*zip(repeat("-s", len(service_names)), service_names)))
        argv.extend(args)
        return argv

    def build_service_response(self, service_name, image_with_digest):
        stack = service_name.rpartition("_")[0]
        labels = {"com.docker.stack.namespace": stack} if stack else {}
        return {
            "ID": str(randint(5555555555, 9999999999)),
            "Version": {"Index": randint(11111, 99999)},
            "Spec": {
                "Name": service_name,
                "TaskTemplate": {
                    "ContainerSpec": {"Image": image_with_digest, "Labels": labels}
                },
            },
        }

    def build_services_response(self, services):
        return [
            self.build_service_response(service_name, image_with_digest)
            for service_name, image_with_digest in reversed(services)
        ]

    def build_distribution_response(
        self, request, services=None, with_new_digest=True, image=None
    ):
        digest = "1234567890"
        if services and image:  # pragma: nocover
            service_image = [img for _, img in services if img.startswith(image)][0]
            _, digest = service_image.rsplit(":", 1)
            if with_new_digest:
                digest = str(int(digest) + 1)

        return {
            "Descriptor": {
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "digest": "sha256:" + digest,
                "size": 12345,
            },
            "Platforms": [{"architecture": "amd64", "os": "linux"}],
        }

    @contextlib.contextmanager
    def mock_docker(
        self,
        services=None,
        api_version="1.40",
        with_missing_services=False,
        with_missing_distribution=False,
        with_new_distribution=True,
        with_api_error=False,
        with_api_exception=False,
        with_auth_header=True,
    ):
        env = (
            {"DOCKER_USERNAME": "foo", "DOCKER_PASSWORD": "bar"}
            if with_auth_header
            else {}
        )
        services = services or []
        with mock.patch.dict(os.environ, env):
            error_message = {"message": "We've got problem"}

            # Mock version request
            respx.get(
                re.compile(r"^http://[^/]+/version$"),
                content={"ApiVersion": api_version},
                alias="version",
            )

            # Mock services request
            respx.get(
                re.compile(r"^http://[^/]+/services\??.*$"),
                content=(
                    ConnectTimeout()
                    if with_api_exception
                    else self.build_services_response(services)
                    if not with_missing_services
                    else []
                ),
                alias="version",
            )

            # Mock distribution request
            respx.get(
                re.compile(r"^http://[^/]+/distribution/(?P<image>.+/?.*)/json$"),
                status_code=(
                    httpx.codes.UNAUTHORIZED
                    if with_missing_distribution
                    else httpx.codes.OK
                ),
                content=(
                    error_message
                    if with_missing_distribution
                    else partial(
                        self.build_distribution_response,
                        services=services,
                        with_new_digest=with_new_distribution,
                    )
                ),
                alias="distribution",
            )

            # Mock service update request
            respx.post(
                re.compile(r"http://[^/]+/services/[0-9]+/update"),
                status_code=(
                    httpx.codes.SERVICE_UNAVAILABLE
                    if with_api_error
                    else httpx.codes.OK
                ),
                content=error_message if with_api_error else {"Warnings": []},
                alias="service_update",
            )

            yield respx.aliases

    @contextlib.contextmanager
    def mock_slack(self, text="ok", token="token"):
        slack_url = f"https://hooks.slack.com/services/{token}"
        respx.post(
            slack_url,
            content=text,
            status_code=200,
            content_type="text/html",
            alias="slack",
        )
        yield

    def get_all_request_bodies(self, alias):
        calls = respx.aliases[alias].calls
        return [json.loads(c[0].content.decode("utf-8")) for c in calls]

    def get_request_body(self, alias, call_number=1):
        calls = respx.aliases[alias].calls
        return json.loads(calls[call_number - 1][0].content.decode("utf-8"))

    def get_request_headers(self, alias, call_number=1):
        calls = respx.aliases[alias].calls
        return calls[call_number - 1][0].headers

    @contextlib.contextmanager
    def mock_stdout(self):
        with mock.patch("sys.stdout", StringIO()) as stdout:
            yield stdout

    @contextlib.contextmanager
    def mock_stderr(self):
        with mock.patch("sys.stderr", StringIO()) as stderr:
            yield stderr
