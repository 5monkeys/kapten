from itertools import chain, repeat

from kapten import cli

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
        argv = self.build_sys_args(services.keys(), "--slack", "token")

        with self.mock_docker_api(services) as client:
            with self.mock_slack():
                cli.command(argv)
                update_service_calls = client.update_service.mock_calls
                self.assertEqual(len(update_service_calls), 2)

                tpl1 = update_service_calls[0].kwargs["task_template"]
                self.assertTrue(tpl1["ContainerSpec"]["Image"].endswith("2"))

                tpl2 = update_service_calls[1].kwargs["task_template"]
                self.assertTrue(tpl2["ContainerSpec"]["Image"].endswith("2"))

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
