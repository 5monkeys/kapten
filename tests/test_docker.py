import json
import os
from unittest import mock

from kapten.docker import DockerAPIClient

from .testcases import KaptenTestCase


class DockerAPIClientTestCase(KaptenTestCase):
    async def test_version(self):
        api = DockerAPIClient()
        with self.mock_docker():
            version = await api.version()
            self.assertIn("ApiVersion", version)

    async def test_services(self):
        api = DockerAPIClient()
        services = [("foobar", "foo/bar:baz@sha256:1")]
        with self.mock_docker(services=services):
            services = await api.services()
            self.assertEqual(len(services), 1)

    async def test_distribution(self):
        api = DockerAPIClient()
        services = [("foobar", "foo/bar:baz@sha256:1")]
        with self.mock_docker(services=services):
            image = await api.distribution("foo/bar:baz")
            self.assertEqual(image["Descriptor"]["digest"], "sha256:2")

    async def test_service_update(self):
        api = DockerAPIClient()

        services = [("foobar", "foo/bar:baz@sha256:1")]
        with self.mock_docker(services=services) as httpx_mock:
            service = self.build_service_response("foobar", "foo/bar:baz@sha256:1")
            service_id = service["ID"]
            service_version = service["Version"]["Index"]
            response = await api.service_update(
                id_or_name=service_id, version=service_version, spec=service["Spec"],
            )
            self.assertEqual(response, {"Warnings": []})
            request, response = httpx_mock["service_update"].calls[0]
            self.assertIn(service_id, request.url.path)
            self.assertEqual(request.url.query, f"version={service_version}")
            request_body = json.loads(request.content.decode("utf-8"))
            self.assertDictEqual(request_body, service["Spec"])

    async def test_auth_header(self):
        api = DockerAPIClient()
        services = [("foobar", "foo/bar:baz@sha256:1")]

        with self.mock_docker(services) as httpx_mock:
            await api.distribution("foo/bar:baz")
            request, _ = httpx_mock["distribution"].calls[0]
            self.assertIn("x-registry-auth", request.headers.keys())

        with self.mock_docker(services, with_auth_header=False) as httpx_mock:
            await api.distribution("foo/bar:baz")
            request, _ = httpx_mock["distribution"].calls[0]
            self.assertNotIn("x-registry-auth", request.headers.keys())

    async def test_tcp_host(self):
        with mock.patch.dict(os.environ, {"DOCKER_HOST": "tcp://localhost:2375"}):
            api = DockerAPIClient()
            with self.mock_docker():
                version = await api.version()
                self.assertIn("ApiVersion", version)
