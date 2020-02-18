from kapten import slack
from kapten.docker import Service

from .testcases import KaptenTestCase


class SlackTestCase(KaptenTestCase):
    async def test_notify(self):
        services = [
            Service(
                self.build_service_response("foo_bar", "repo/foo:tag@sha256:123456789")
            ),
            Service(
                self.build_service_response("baz", "repo/foo:tag@sha256:123456789")
            ),
        ]
        with self.mock_slack(token="token"):
            success = await slack.notify(
                "token", services, project="myapp", channel="kapten-deploy"
            )
            self.assertTrue(success)
            body = self.get_request_body("slack")
            self.assertEqual(body["text"], "Deployment of *myapp* has started.")
            self.assertEqual(body["channel"], "kapten-deploy")

            fields = body["attachments"][0]["fields"]
            self.assertIsNotNone(fields[0]["value"])
            self.assertEqual(fields[1]["value"], "\u2022 (none)\n\u2022 foo")
            self.assertEqual(fields[2]["value"], "repo/foo:tag")
            self.assertEqual(fields[3]["value"], "sha256:123456789")
            self.assertEqual(fields[4]["value"], "\u2022 bar\n\u2022 baz")

    async def test_multichannel_notify(self):
        services = [
            Service(
                self.build_service_response("baz", "repo/foo:tag@sha256:123456789")
            ),
        ]
        channels = []

        with self.mock_slack(token="token"):
            success = await slack.notify(
                "token",
                services,
                project="myapp",
                channel="deploy,kapten-deploy,general",
            )
            self.assertTrue(success)
            # Two requests, one for each channel
            bodies = self.get_all_request_bodies("slack")

            self.assertEqual(len(bodies), 3)

            channels = [b["channel"] for b in bodies]

            self.assertListEqual(channels, channels)

    async def test_notify_missing_details(self):
        service = Service(
            self.build_service_response("foo_bar", "repo/foo:tag@sha256:123456789")
        )
        with self.mock_slack(token="token"):
            success = await slack.notify("token", [service])
            self.assertTrue(success)
            body = self.get_request_body("slack")
            self.assertEqual(body["text"], "Deployment of *foo* has started.")
            self.assertNotIn("channel", body)

    async def test_post_without_fields(self):
        with self.mock_slack(token="token"):
            success = await slack.post("token", "Hello world")
            self.assertTrue(success)
            body = self.get_request_body("slack")
            self.assertNotIn("attachments", body)
