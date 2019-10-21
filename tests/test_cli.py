from itertools import chain, repeat

from kapten import __version__, cli

from .testcases import KaptenTestCase


class CLICommandTestCase(KaptenTestCase):
    def build_sys_args(self, service_names, *args):
        argv = list(chain(*zip(repeat("-s", len(service_names)), service_names)))
        argv.extend(args)
        return argv

    def test_command(self):
        services = {
            "stack_app": "repository/app_image:latest@sha256:10001",
            "stack_db": "repository/db_image:latest@sha256:20001",
        }
        argv = self.build_sys_args(
            services.keys(),
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
            self.assertTrue(tpl1["ContainerSpec"]["Image"].endswith("2"))

            tpl2 = update_service_calls[1][2]["task_template"]
            self.assertTrue(tpl2["ContainerSpec"]["Image"].endswith("2"))

            slack_body = self.get_request_body(slack_mock)
            self.assertEqual(slack_body["text"], "Deployment of *apa* has started.")
            self.assertEqual(slack_body["channel"], "deploy")
            fields = slack_body["attachments"][0]["fields"]
            digest_field = [f["value"] for f in fields if f["title"] == "Digest"][0]
            self.assertTrue(digest_field.endswith("2"))

    def test_command_only_check(self):
        services = {
            "stack_app": "repository/app_image:latest@sha256:10001",
            "stack_db": "repository/db_image:latest@sha256:20001",
        }
        argv = self.build_sys_args(services.keys(), "--check")

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
        with self.assertRaises(SystemExit) as cm:
            with self.mock_stdout() as stdout:
                cli.command(["--version"])
        self.assertIn(__version__, stdout.getvalue())
        self.assertEqual(cm.exception.code, 0)
