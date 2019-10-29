import contextlib
import unittest
from unittest import mock

from kapten import __version__
from kapten.tool import Kapten

from .fixtures import dockerhub_payload
from .testcases import SUPPORTS_SERVER_MODE, KaptenTestCase

if SUPPORTS_SERVER_MODE:
    from starlette.testclient import TestClient
    from kapten.server import app


@unittest.skipIf(not SUPPORTS_SERVER_MODE, "server mode not supported")
class ServerTestCase(KaptenTestCase):
    @contextlib.contextmanager
    def mock_server(self, services=None):
        services = services or []
        with self.mock_docker_api(services=services):
            client = Kapten([name for name, _ in services])
            with mock.patch("kapten.server.app.state.client", client):
                test_client = TestClient(app)
                yield test_client

    def test_version_endpoint(self):
        with self.mock_server() as client:
            response = client.get("/version")
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.json(), {"kapten": __version__})

    def test_dockerhub_endpoint(self):
        services = [("stack_app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_server(services) as client:
            response = client.post("/webhook/dockerhub", json=dockerhub_payload)
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(
                response.json(),
                {"image": "5monkeys/app:latest", "services": ["stack_app"]},
            )
