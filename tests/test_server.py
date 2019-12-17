import contextlib
import hashlib
import hmac
import json
import re
import unittest
import uuid
from unittest import mock

import respx
from starlette.testclient import TestClient

from kapten import __version__, server
from kapten.tool import Kapten

from .testcases import KaptenTestCase


class ServerTestCase(KaptenTestCase):
    def setUp(self):
        super().setUp()
        self.token = "MY-TOKEN"

    @contextlib.contextmanager
    def mock_server(self, services=None, **kwargs):
        services = services or [("app", "5monkeys/app:latest@sha256:10001")]
        with self.mock_docker(services=services, **kwargs):
            with mock.patch.dict("sys.modules", uvicorn=mock.MagicMock()):
                client = Kapten([name for name, _ in services])
                server.run(client, self.token)
                with TestClient(server.app) as test_client:
                    yield test_client

    @contextlib.contextmanager
    def mock_dockerhub(
        self,
        repository_url="https://registry.hub.docker.com/u/5monkeys/app/",
        repository_name=None,
        tag="latest",
        assert_callback=True,
        callback_failure=False,
    ):
        callback_url = f"{repository_url}hook/2141b5bi5i5b02bec211i4eeih0242eg11000a/"
        repo_name = repository_name or repository_url.split("/u/")[1].strip("/")
        owner, name = repo_name.split("/")

        respx.post(
            callback_url,
            status_code=200 if not callback_failure else 444,
            content_type="text/html",
            alias="dockerhub",
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

    @contextlib.contextmanager
    def mock_github(
        self,
        repository_url="https://github.com/5monkeys/app",
        repository_name=None,
        tag="latest",
        assert_callback=True,
        callback_failure=False,
        token=None,
        digest="5monkeys/app@sha256:10002",
        image=None,
        statuses_url=None,
    ):
        repo_name = repository_name or repository_url.split("github.com/")[1].strip("/")
        deployment_url = f"https://api.github.com/repos/{repo_name}/deployments/123456"
        statuses_url = statuses_url or f"{deployment_url}/statuses"
        payload = {
            "deployment": {
                "url": deployment_url,
                "payload": json.dumps(
                    {"digest": digest, "tag": tag, "image": image or repo_name}
                ),
                "environment": "development",
                "statuses_url": statuses_url,
            },
            "repository": {"url": repository_url, "full_name": repo_name},
        }
        respx.post(
            re.compile(r"^https://api\.github\.com/repos/.*/deployments/.*/statuses$"),
            status_code=200,
            content={},
            alias="github",
        )
        yield payload, self.sign_payload(payload, token)

    def sign_payload(self, payload, token=None):
        return "sha1={}".format(
            hmac.new(
                key=bytes(token or self.token, "utf-8"),
                msg=bytes(json.dumps(payload), "utf-8"),
                digestmod=hashlib.sha1,
            ).hexdigest()
        )

    def test_version_endpoint(self):
        with self.mock_server() as http:
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
        with self.mock_server(services) as http:
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
        with self.mock_server() as http:
            response = http.post("/webhook/dockerhub/INVALID", json={})
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_bad_payload(self):
        with self.mock_server() as http:
            payload = {"foo": "bar"}
            response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
            self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_callback_url(self):
        with self.mock_server() as http:
            with self.mock_dockerhub(
                repository_url="https://registry.hub.docker.com/u/5monkeys/unknown/",
                repository_name="5monkeys/app",
                assert_callback=False,
            ) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_invalid_repository(self):
        with self.mock_server() as http:
            with self.mock_dockerhub(
                repository_name="not/me", assert_callback=False
            ) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 404)

    def test_dockerhub_endpoint_with_failing_callback(self):
        with self.mock_server() as http:
            with self.mock_dockerhub(callback_failure=True) as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_dockerhub_endpoint_with_non_matching_services(self):
        with self.mock_server(with_new_distribution=False) as http:
            with self.mock_dockerhub(tag="dev") as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertListEqual(response.json(), [])

    def test_dockerhub_endpoint_with_client_error(self):
        with self.mock_server(with_api_error=True) as http:
            with self.mock_dockerhub() as payload:
                response = http.post("/webhook/dockerhub/MY-TOKEN", json=payload)
                self.assertEqual(response.status_code, 503)

    @unittest.expectedFailure
    def test_github_endpoint(self):
        services = [
            ("stack_migrate", "5monkeys/app:latest@sha256:10001"),
            ("stack_app", "5monkeys/app:latest@sha256:10001"),
            ("stack_beta", "5monkeys/app:beta@sha256:20001"),
            ("stack_db", "5monkeys/db:latest@sha256:30001"),
        ]
        with self.mock_server(services) as http:
            with self.mock_github(
                image="5monkeys/app", tag="latest", digest="5monkeys/app@sha256:10002",
            ) as (payload, signature):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "Deployment",
                    },
                )
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
                github_requests = respx.aliases["github"]
                # On successful deploy we post 2 deployment statuses: 'in_progress' and 'success'
                self.assertEqual(len(github_requests.calls), 2)
                in_progress_request, in_progress_response = github_requests.calls[0]
                self.assertEqual(
                    json.loads(in_progress_request.content.decode("utf-8")),
                    {
                        "state": "in_progress",
                        "description": "Deployment has started",
                        "environment": "dev",
                    },
                )
                success_request, success_response = github_requests.calls[1]
                self.assertEqual(
                    json.loads(success_request.content.decode("utf-8")),
                    {
                        "state": "success",
                        "description": "Deployment finished successfully. 2 services updated.",
                        "environment": "dev",
                    },
                )

    def test_github_ping_webhook(self):
        with self.mock_server() as http:
            payload = {
                "zen": uuid.uuid4().hex,
                "hook_id": "12345",
                "hook": {
                    "type": "App",
                    "id": 123,
                    "active": "true",
                    "events": ["deployment"],
                    "app_id": 456,
                },
            }
            response = http.post(
                "/webhook/github",
                json=payload,
                headers={
                    "X-Hub-Signature": self.sign_payload(payload),
                    "X-GitHub-Event": "ping",
                },
            )
            self.assertEqual(response.status_code, 202)

    def test_github_webhook_without_signature(self):
        with self.mock_server() as http:
            payload = {"some": "data"}
            response = http.post(
                "/webhook/github",
                json=payload,
                headers={"X-GitHub-Event": "Deployment"},
            )
            self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_signature(self):
        with self.mock_server() as http:
            with self.mock_github(
                image="5monkeys/app", tag="latest", digest="5monkeys/app@sha256:10002",
            ) as (payload, signature):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": self.sign_payload({"invalid": "payload"}),
                        "X-GitHub-Event": "Deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": self.sign_payload(payload, token="invalid"),
                        "X-GitHub-Event": "Deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_payload(self):
        with self.mock_server() as http:
            payload = {
                "zen": uuid.uuid4().hex,
                "hook_id": "12345",
                "hook": {
                    "type": "App",
                    "id": 123,
                    "active": "true",
                    "events": ["deployment"],
                    "app_id": 456,
                },
            }
            response = http.post(
                "/webhook/github",
                json=payload,
                headers={
                    "X-Hub-Signature": self.sign_payload(payload),
                    "X-GitHub-Event": "deployment",
                },
            )
            self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_image(self):
        with self.mock_server() as http:
            with self.mock_github(image="5monkeys/invalid") as (
                payload,
                signature,
            ):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_callback_url(self):
        with self.mock_server() as http:
            with self.mock_github(statuses_url="https://api.github.com/invalid/",) as (
                payload,
                signature,
            ):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_tag(self):
        with self.mock_server() as http:
            with self.mock_github(tag="") as (payload, signature):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_invalid_digest1(self):
        """
        Invalid digest prefix
        """
        with self.mock_server() as http:
            with self.mock_github(digest="5monkeys/app@invalid:10002") as (
                payload,
                signature,
            ):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_wehbook_with_invalid_digest2(self):
        """
        Missing digest value
        """
        with self.mock_server() as http:
            with self.mock_github(digest="5monkeys/app:latest") as (
                payload,
                signature,
            ):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "deployment",
                    },
                )
                self.assertEqual(response.status_code, 404)

    def test_github_webhook_with_non_matching_services(self):
        with self.mock_server(with_new_distribution=False) as http:
            with self.mock_github(
                image="5monkeys/app",
                tag="unknown",
                digest="5monkeys/unknown@sha256:10002",
            ) as (payload, signature):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "Deployment",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertListEqual(response.json(), [])

    @unittest.expectedFailure
    def test_github_webhook_with_client_error(self):
        with self.mock_server(with_api_error=True) as http:
            with self.mock_github() as (payload, signature):
                response = http.post(
                    "/webhook/github",
                    json=payload,
                    headers={
                        "X-Hub-Signature": signature,
                        "X-GitHub-Event": "Deployment",
                    },
                )
                self.assertEqual(response.status_code, 200)
                github_requests = respx.aliases["github"]
                # On failure we post 2 deployment statuses: 'in_progress' and 'error'
                self.assertEqual(len(github_requests.calls), 2)
                in_progress_request, in_progress_response = github_requests.calls[0]
                self.assertEqual(
                    json.loads(in_progress_request.content.decode("utf-8")),
                    {
                        "state": "in_progress",
                        "description": "Deployment has started",
                        "environment": "dev",
                    },
                )
                error_request, error_response = github_requests.calls[1]
                self.assertEqual(
                    json.loads(error_request.content.decode("utf-8")),
                    {
                        "state": "error",
                        "description": "Deployment failed with an ucaught error",
                        "environment": "dev",
                    },
                )
