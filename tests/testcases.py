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
import responses
import respx
from httpx.exceptions import ConnectTimeout


class KaptenTestCase(asynctest.TestCase):
    def setUp(self):
        # Mock logger
        self.logger_mock = mock.MagicMock()
        modules = ["cli", "tool", "slack", "server"]
        for module in modules:
            mocker = mock.patch("kapten.{}.logger".format(module), self.logger_mock)
            mocker.start()
            self.addCleanup(mocker.stop)

    def build_sys_args(self, services, *args):
        service_names = [name for name, _ in services]
        argv = list(chain(*zip(repeat("-s", len(service_names)), service_names)))
        argv.extend(args)
        return argv

    def build_services_response(self, services):
        def spec(service_name, image_with_digest):
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

        return [
            spec(service_name, image_with_digest)
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
        with_missing_services=False,
        with_missing_distribution=False,
        with_new_distribution=True,
        with_api_error=False,
        with_api_exception=False,
        with_auth_header=True,
        with_unsupported_api_version=False,
    ):
        env = (
            {"DOCKER_USERNAME": "foo", "DOCKER_PASSWORD": "bar"}
            if with_auth_header
            else {}
        )
        services = services or []
        with mock.patch.dict(os.environ, env), respx.mock(
            assert_all_called=False
        ) as httpx_mock:
            error_message = {"message": "We've got problem"}

            # Mock version request
            httpx_mock.get(
                re.compile(r"^http://[^/]+/version$"),
                content={
                    "ApiVersion": "1.23" if with_unsupported_api_version else "1.40"
                },
                alias="version",
            )

            # Mock services request
            httpx_mock.get(
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
            httpx_mock.get(
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
            httpx_mock.post(
                re.compile(r"http://[^/]+/services/[0-9]+/update"),
                status_code=(
                    httpx.codes.SERVICE_UNAVAILABLE
                    if with_api_error
                    else httpx.codes.OK
                ),
                content=error_message if with_api_error else [],
                alias="service_update",
            )

            yield httpx_mock

    @contextlib.contextmanager
    def mock_slack(self, response="ok", token="token"):
        slack_url = "https://hooks.slack.com/services/%s" % token
        with responses.RequestsMock() as mock_responses:
            mock_responses.add(
                responses.POST,
                slack_url,
                body=response,
                status=200,
                content_type="text/html",
            )
            yield mock_responses

    def get_request_body(self, requests_mock, call_number=1):
        return json.loads(
            requests_mock.calls[call_number - 1].request.body.decode("utf-8")
        )

    @contextlib.contextmanager
    def mock_stdout(self):
        with mock.patch("sys.stdout", StringIO()) as stdout:
            yield stdout

    @contextlib.contextmanager
    def mock_stderr(self):
        with mock.patch("sys.stderr", StringIO()) as stderr:
            yield stderr
