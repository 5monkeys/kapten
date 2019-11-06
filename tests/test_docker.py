import unittest
from unittest import mock

from kapten.docker import DockerAPIClient

from .testcases import KaptenTestCase


class DockerAPIClientTestCase(KaptenTestCase):
    @unittest.expectedFailure
    def test_auth_header(self):
        services = [("foobar", "foo/bar:baz@sha256:1")]
        with self.mock_docker(services) as api:
            with mock.patch.dict(
                "os.environ", DOCKER_USERNAME="foo", DOCKER_PASSWORD="bar"
            ):
                client = DockerAPIClient()
                dist = client.inspect_distribution("foo/bar:baz")

                self.assertIsInstance(dist, dict)
                self.assertTrue(api.inspect_distribution.called)
                _, call_kwargs = api.inspect_distribution.call_args_list[0]
                self.assertDictEqual(
                    call_kwargs, {"auth_config": {"username": "foo", "password": "bar"}}
                )

    @unittest.expectedFailure
    async def test_version(self):
        # TODO: Mock version request
        # api = DockerAPIClient()
        # version = await api.version()
        # self.assertDictEqual(version, {})
        self.assertTrue(False)

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

    @unittest.expectedFailure
    async def test_service_update(self):
        self.assertTrue(False)
