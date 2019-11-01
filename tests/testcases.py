import contextlib
import json
import unittest
from io import StringIO
from itertools import chain, repeat
from random import randint
from unittest import mock

import responses

import kapten


class KaptenTestCase(unittest.TestCase):
    def setUp(self):
        # Mock logger
        self.logger_mock = mock.MagicMock()
        modules = ["cli", "tool", "slack"]
        if kapten.supports_feature("server"):
            modules.append("server")
        for module in modules:
            mocker = mock.patch("kapten.{}.logger".format(module), self.logger_mock)
            mocker.start()
            self.addCleanup(mocker.stop)

    def build_sys_args(self, services, *args):
        service_names = [name for name, _ in services]
        argv = list(chain(*zip(repeat("-s", len(service_names)), service_names)))
        argv.extend(args)
        return argv

    def build_service_spec(self, service_name, image_name):
        stack = service_name.split("_")[0]
        return {
            "ID": str(randint(5555555555, 9999999999)),
            "Version": {"Index": randint(11111, 99999)},
            "Spec": {
                "Name": service_name,
                "TaskTemplate": {
                    "ContainerSpec": {
                        "Image": image_name,
                        "Labels": {"com.docker.stack.namespace": stack},
                    }
                },
            },
        }

    @contextlib.contextmanager
    def mock_docker_api(
        self,
        services=None,
        with_missing_services=False,
        with_missing_distribution=False,
        with_new_distribution=True,
    ):
        with mock.patch("kapten.tool.APIClient") as APIClient:
            # Client instance
            client = APIClient.return_value

            # Mock APIClient.services()
            specs = (
                [
                    self.build_service_spec(service_name, image_name)
                    for service_name, image_name in reversed(services)
                ]
                if not with_missing_services
                else []
            )
            client.services = mock.MagicMock(return_value=specs)

            # Mock APIClient.inspect_distribution()
            def inspect_distribution_mock(image_name, auth_config=None):
                image = [img for _, img in services if img.startswith(image_name)][0]
                _, digest = image.rsplit(":", 1)
                if with_new_distribution:
                    digest = str(int(digest) + 1)
                if with_missing_distribution:
                    return {}
                return {"Descriptor": {"digest": "sha256:" + digest}}

            client.inspect_distribution = mock.MagicMock(
                side_effect=inspect_distribution_mock
            )

            yield client

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
