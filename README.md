<img src="https://raw.githubusercontent.com/5monkeys/kapten/master/kapten.png" width="100" />

# kapten

![](https://github.com/5monkeys/kapten/workflows/Test/badge.svg)

Updates a Docker Swarm service when a new image is available.

**Usage:**
```sh
$ kapten --help
usage: kapten [-h] -s SERVICES [-p PROJECT] [--slack-token SLACK_TOKEN]
              [--slack-channel SLACK_CHANNEL] [--check] [--force]
              [-v VERBOSITY]

Checks for new images and updates services if needed.

optional arguments:
  -h, --help            show this help message and exit
  -s SERVICES, --service SERVICES
                        Service to update
  -p PROJECT, --project PROJECT
                        Optional project name
  --slack-token SLACK_TOKEN
                        Slack token to use for notification
  --slack-channel SLACK_CHANNEL
                        Optional Slack channel to use for notification
  --check               Only check if service needs to be updated
  --force               Force service update
  -v VERBOSITY, --verbosity VERBOSITY
                        Level of verbosity
```

**Example:**
```sh
$ kapten --service app --slack-token T00ABCD0A/ABCDEFGHI/xYzabCDEfGh1aBCCd12abCde
Updating service app to repo/app:latest@sha256:123456789
```
