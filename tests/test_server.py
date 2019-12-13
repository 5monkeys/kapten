import contextlib
import unittest
from unittest import mock

import responses
from starlette.testclient import TestClient

from kapten import __version__, server
from kapten.tool import Kapten

from .testcases import KaptenTestCase


class ServerTestCase(KaptenTestCase):
    @contextlib.contextmanager
    def mock_server(self, services=None, **kwargs):
        services = services or [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_docker(services=services, **kwargs) as httpx_mock:
            with mock.patch.dict("sys.modules", uvicorn=mock.MagicMock()):
                client = Kapten([name for name, _ in services])
                server.run(client, "MY-TOKEN")
                with TestClient(server.app) as test_client:
                    yield test_client, httpx_mock

    @contextlib.contextmanager
    def mock_dockerhub(
        self,
        repository_url="https://registry.hub.docker.com/u/5monkeys/app/",
        repository_name=None,
        tag="latest",
        assert_callback=True,
        callback_failure=False,
    ):
        callback_url = "{}hook/2141b5bi5i5b02bec211i4eeih0242eg11000a/".format(
            repository_url
        )
        repo_name = repository_name or repository_url.split("/u/")[1].strip("/")
        owner, name = repo_name.split("/")

        with responses.RequestsMock(
            assert_all_requests_are_fired=assert_callback
        ) as mock_responses:
            mock_responses.add(
                responses.POST,
                callback_url,
                status=200 if not callback_failure else 444,
                content_type="text/html",
            )
            yield {
                "callback_url": callback_url,
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
        with self.mock_server() as (http, _):
            response = http.get("/version")
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.json(), {"kapten": __version__})

    def test_dockerhub_endpoint(self):
        services = [
            ("stack_migrate", "5monkeys/app:latest@sha256:10001"),
            ("stack_app", "5monkeys/app:latest@sha256:10001"),
            ("stack_beta", "5monkeys/app:beta@sha256:20001"),
            ("stack_db", "5monkeys/db:latest@sha256:30001"),
        ]
        with self.mock_server(services) as (http, _):
            with self.mock_dockerhub() as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
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

    def test_dockerhub_endpoint_with_bad_token(self):
        with self.mock_server() as (http, _):
            response = http.post("/webhook/dockerhub/INVALID", json={})
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_bad_payload(self):
        with self.mock_server() as (http, _):
            payload = {"foo": "bar"}
            response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_callback_url(self):
        with self.mock_server() as (http, _):
            with self.mock_dockerhub(
                repository_url="https://registry.hub.docker.com/u/5monkeys/unknown/",
                repository_name="5monkeys/app",
                assert_callback=False,
            ) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_repository(self):
        with self.mock_server() as (http, _):
            with self.mock_dockerhub(
                repository_name="not/me", assert_callback=False
            ) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_failing_callback(self):
        with self.mock_server() as (http, _):
            with self.mock_dockerhub(callback_failure=True) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_dockerhub_endpoint_with_non_matching_services(self):
        with self.mock_server(with_new_distribution=False) as (http, _):
            with self.mock_dockerhub(tag="dev") as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertListEqual(response.json(), [])

    def test_dockerhub_endpoint_with_client_error(self):
        with self.mock_server(with_api_error=True) as (http, api):
            with self.mock_dockerhub() as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 503)
