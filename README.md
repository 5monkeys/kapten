<img src="https://raw.githubusercontent.com/5monkeys/kapten/master/kapten-text.png" width="66%" />

# kapten

![](https://github.com/5monkeys/kapten/workflows/test/badge.svg)
[![codecov](https://codecov.io/gh/5monkeys/kapten/branch/master/graph/badge.svg)](https://codecov.io/gh/5monkeys/kapten)
[![PyPi Version](https://img.shields.io/pypi/v/kapten.svg)](https://pypi.org/project/kapten/)
[![Python Versions](https://img.shields.io/pypi/pyversions/kapten.svg)](https://pypi.org/project/kapten/)

Updates a Docker Swarm service when a new image is available.

### Usage
```console
$ kapten --help
usage: kapten [-h] [--version] [-s SERVICES] [-p PROJECT]
              [--slack-token SLACK_TOKEN] [--slack-channel SLACK_CHANNEL]
              [--check] [--force] [-v VERBOSITY]

Checks for new images and updates services if needed.

optional arguments:
  -h, --help            show this help message and exit
  --version             Show version and exit.
  -s SERVICES, --service SERVICES
                        Service to update.
  -p PROJECT, --project PROJECT
                        Optional project name.
  --slack-token SLACK_TOKEN
                        Slack token to use for notification.
  --slack-channel SLACK_CHANNEL
                        Optional Slack channel to use for notification.
  --check               Only check if service needs to be updated.
  --force               Force service update.
  -v VERBOSITY, --verbosity VERBOSITY
                        Level of verbosity.
```

### Example
```console
$ kapten --service app --slack-token T00ABCD0A/ABCDEFGHI/xYzabCDEfGh1aBCCd12abCde
Updating service app to repo/app:latest@sha256:123456789
```
