import logging
import unittest
from unittest import mock
from unittest.mock import call

from kapten import __version__, cli

from .testcases import SUPPORTS_SERVER_MODE, KaptenTestCase


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

        with self.mock_docker_api(services) as client, self.mock_slack() as slack_mock:
            cli.command(argv)
            update_service_calls = client.update_service.mock_calls
            self.assertEqual(len(update_service_calls), 2)

            tpl1 = update_service_calls[0][2]["task_template"]
            self.assertEqual(
                tpl1["ContainerSpec"]["Image"],
                "repository/app_image:latest@sha256:10002",
            )

            tpl2 = update_service_calls[1][2]["task_template"]
            self.assertEqual(
                tpl2["ContainerSpec"]["Image"],
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
        with self.mock_docker_api(services):
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
        with self.mock_docker_api(services):
            with mock.patch("kapten.slack.notify") as notify:
                cli.command(argv)
                self.assertFalse(notify.called)

    def test_command_noop(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services)
        with self.mock_docker_api(services, with_new_digest=False) as client:
            cli.command(argv)
            self.assertFalse(client.update_service.called)

    def test_command_force(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services, "--force")
        with self.mock_docker_api(services, with_new_digest=False) as client:
            cli.command(argv)
            self.assertTrue(client.update_service.called)

    def test_command_only_check(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(services, "--check")

        with self.mock_docker_api(services) as client:
            cli.command(argv)
            update_service_calls = client.update_service.mock_calls
            self.assertEqual(len(update_service_calls), 0)

    def test_command_required_args(self):
        with self.assertRaises(SystemExit) as cm:
            with self.mock_stderr() as stderr:
                cli.command([])
        self.assertIn("Missing required", stderr.getvalue())
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

        with self.mock_docker_api(services, service_failure=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    def test_command_error_failing_service(self):
        services = [
            ("stack_app", "repository/app_image:latest@sha256:10001"),
            ("stack_db", "repository/db_image:latest@sha256:20001"),
        ]
        argv = self.build_sys_args(services)

        with self.mock_docker_api(services, registry_failure=True):
            with self.assertRaises(SystemExit) as cm:
                cli.command(argv)
            self.assertEqual(cm.exception.code, 666)

    @unittest.skipIf(not SUPPORTS_SERVER_MODE, "server mode not supported")
    def test_command_server(self):
        services = [("foo", "repo/foo:tag@sha256:0")]
        argv = self.build_sys_args(services, "--server")

        with mock.patch.dict("sys.modules", uvicorn=None):
            with self.assertRaises(SystemExit) as cm:
                with self.mock_stderr() as stderr:
                    cli.command(argv)

        self.assertIn("Unable to start server", stderr.getvalue())
        self.assertEqual(cm.exception.code, 2)

        with mock.patch.dict("sys.modules", uvicorn=mock.MagicMock()):
            with mock.patch("kapten.server.run") as run_mock:
                cli.command(argv)
                self.assertTrue(run_mock.called)
