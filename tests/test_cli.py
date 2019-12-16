import json
import logging
from unittest import mock
from unittest.mock import call

from kapten import __version__, cli

from .testcases import KaptenTestCase


class CLICommandTestCase(KaptenTestCase):
    def test_command(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(
            services,
            "--slack-token",
            "token",
            "--slack-channel",
            "deploy",
            "--project",
            "apa",
        )

        with self.mock_docker(services) as httpx_mock, self.mock_slack() as slack_mock:
            cli.command(argv)

            service_update_request = httpx_mock["service_update"]
            self.assertEqual(len(service_update_request.calls), 2)

            request1, _ = service_update_request.calls[0]
            content1 = json.loads(request1.content.decode("utf-8"))
            self.assertEqual(
                content1["TaskTemplate"]["ContainerSpec"]["Image"],
                "repository/app_image:latest@sha256:10002",
            )

            request2, _ = service_update_request.calls[1]
            content2 = json.loads(request2.content.decode("utf-8"))
            self.assertEqual(
                content2["TaskTemplate"]["ContainerSpec"]["Image"],
                "repository/db_image:latest@sha256:20002",
            )

            for i, expected_digest in enumerate(["sha256:10002", "sha256:20002"], 1):
                slack_body = self.get_request_body(slack_mock, call_number=i)
                self.assertEqual(slack_body["text"], "Deployment of *apa* has started.")
                self.assertEqual(slack_body["channel"], "deploy")
                fields = slack_body["attachments"][0]["fields"]
                digest_field = [f["value"] for f in fields if f["title"] == "Digest"][0]
                self.assertEqual(digest_field, expected_digest)

    def test_command_verbosity(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        with self.mock_docker(services):
            cli.command(self.build_sys_args(services, "-v", "0"))
            cli.command(self.build_sys_args(services, "-v", "1"))
            cli.command(self.build_sys_args(services, "-v", "2"))

        self.assertListEqual(
            self.logger_mock.setLevel.call_args_list,
            [call(logging.CRITICAL), call(logging.INFO), call(logging.DEBUG)],
        )

    def test_command_without_slack(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services)
        with self.mock_docker(services):
            with mock.patch("kapten.slack.notify") as notify:
                cli.command(argv)
                self.assertFalse(notify.called)

    def test_command_noop(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services)
        with self.mock_docker(services, with_new_distribution=False) as httpx_mock:
            cli.command(argv)
            self.assertFalse(httpx_mock["service_update"].called)

    def test_command_force(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services, "--force")
        with self.mock_docker(services, with_new_distribution=False) as httpx_mock:
            cli.command(argv)
            self.assertTrue(httpx_mock["service_update"].called)

    def test_command_only_check(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(services, "--check")

        with self.mock_docker(services) as httpx_mock:
            cli.command(argv)
            self.assertFalse(httpx_mock["service_update"].called)

    def test_command_required_args(self):
        with self.assertRaises(SystemExit) as cm:
            with self.mock_stderr() as stderr:
                cli.command([])
        self.assertIn("SERVICES", stderr.getvalue())
        self.assertEqual(cm.exception.code, 2)

    def test_command_version(self):
        argv = ["kapten", "--version"]
        with self.assertRaises(SystemExit) as cm:
            with mock.patch("sys.argv", argv), self.mock_stdout() as stdout:
                cli.command()
        self.assertIn(__version__, stdout.getvalue())
        self.assertEqual(cm.exception.code, 0)

    def test_command_error_missing_services(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(services)

        with self.mock_docker(services, with_missing_services=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    def test_command_error_failing_service(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(services)

        with self.mock_docker(services, with_missing_distribution=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    def test_command_docker_api_error(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services)

        with self.mock_docker(services, with_api_exception=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

        with self.mock_docker(services, with_api_error=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    def test_healthcheck_failure(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services, "--check")

        with self.mock_docker(api_version="1.23"):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    def test_command_server_not_supported(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(
            services, "--server", "--host", "1.2.3.4", "--port", "8888"
        )
        with mock.patch.dict("sys.modules", uvicorn=None):
            with self.assertRaises(SystemExit) as cm:
                with self.mock_stderr() as stderr:
                    cli.command(argv)

        self.assertIn("unrecognized arguments: --server", stderr.getvalue())
        self.assertEqual(cm.exception.code, 2)

    def test_command_server(self):
        from kapten.server import app

        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(
            services, "--server", "--host", "1.2.3.4", "--port", "8888"
        )
        uvicorn = mock.MagicMock()
        with mock.patch.dict("sys.modules", uvicorn=uvicorn):
            with self.mock_docker(services):
                with self.assertRaises(SystemExit) as cm:
                    with self.mock_stderr() as stderr:
                        cli.command(argv)
                self.assertIn("WEBHOOK_TOKEN", stderr.getvalue())
                self.assertEqual(cm.exception.code, 2)

                cli.command(argv + ["--webhook-token", "my-secret-token"])
                self.assertTrue(uvicorn.run.called)
                self.assertEqual(
                    uvicorn.run.mock_calls[0],
                    call(app, host="1.2.3.4", port=8888, proxy_headers=True),
                )
