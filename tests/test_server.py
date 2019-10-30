import contextlib
import unittest
from unittest import mock

import kapten
from kapten import __version__
from kapten.tool import Kapten

from .testcases import KaptenTestCase

if kapten.supports_feature("server"):
    from starlette.testclient import TestClient
    from kapten.server import app
    from kapten import server


@unittest.skipIf(not kapten.supports_feature("server"), "server mode not supported")
class ServerTestCase(KaptenTestCase):
    @contextlib.contextmanager
    def mock_server(self, services=None, **kwargs):
        services = services or []
        with self.mock_docker_api(services=services, **kwargs):
            with mock.patch.dict("sys.modules", uvicorn=mock.MagicMock()):
                client = Kapten([name for name, _ in services])
                server.run(client)
                test_client = TestClient(app)
                yield test_client

    def get_dockerhub_payload(
        self,
        repository_url="https://registry.hub.docker.com/u/5monkeys/app/",
        repository_name=None,
        tag="latest",
    ):
        repo_name = repository_name or repository_url.split("/u/")[1].strip("/")
        owner, name = repo_name.split("/")
        return {
            "callback_url": "{}hook/2141b5bi5i5b02bec211i4eeih0242eg11000a/".format(
                repository_url
            ),
            "push_data": {
                "images": [
                    "27d47432a69bca5f2700e4dff7de0388ed65f9d3fb1ec645e2bc24c223dc1cc3",
                    "51a9c7c1f8bb2fa19bcd09789a34e63f35abb80044bc10196e304f6634cc582c",
                    "...",
                ],
                "pushed_at": 1.417566161e09,
                "pusher": "trustedbuilder",
                "tag": tag,
            },
            "repository": {
                "comment_count": 0,
                "date_created": 1.417494799e09,
                "description": "",
                "dockerfile": "FROM ...",
                "full_description": "Docker Hub based automated build from a GitHub repo",
                "is_official": False,
                "is_private": True,
                "is_trusted": True,
                "name": name,
                "namespace": owner,
                "owner": owner,
                "repo_name": repo_name,
                "repo_url": repository_url,
                "star_count": 0,
                "status": "Active",
            },
        }

    def test_version_endpoint(self):
        with self.mock_server() as client:
            response = client.get("/version")
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.json(), {"kapten": __version__})

    def test_dockerhub_endpoint(self):
        services = [
            ("stack_migrate", "5monkeys/app:latest@sha256:10001"),
            ("stack_app", "5monkeys/app:latest@sha256:10001"),
            ("stack_beta", "5monkeys/app:beta@sha256:20001"),
            ("stack_db", "5monkeys/db:latest@sha256:30001"),
        ]
        with self.mock_server(services) as client:
            payload = self.get_dockerhub_payload()
            response = client.post("/webhook/dockerhub", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertListEqual(
                response.json(),
                [
                    {
                        "service": "stack_migrate",
                        "image": "5monkeys/app:latest@sha256:10002",
                    },
                    {
                        "service": "stack_app",
                        "image": "5monkeys/app:latest@sha256:10002",
                    },
                ],
            )

    def test_dockerhub_endpoint_with_bad_payload(self):
        services = [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_server(services) as client:
            payload = {"foo": "bar"}
            response = client.post("/webhook/dockerhub", json=payload)
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_callback_url(self):
        services = [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_server(services) as client:
            payload = self.get_dockerhub_payload(
                repository_url="https://registry.hub.docker.com/u/5monkeys/unknown/"
            )
            response = client.post("/webhook/dockerhub", json=payload)
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_repository(self):
        services = [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_server(services) as client:
            payload = self.get_dockerhub_payload(repository_name="not/me")
            response = client.post("/webhook/dockerhub", json=payload)
            self.assertEqual(response.status_code, 400)

    def test_dockerhub_endpoint_with_non_matching_services(self):
        services = [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_server(services, with_new_digest=False) as client:
            payload = self.get_dockerhub_payload(tag="dev")
            response = client.post("/webhook/dockerhub", json=payload)
            self.assertEqual(response.status_code, 400)
