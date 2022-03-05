#!/usr/bin/env python3
import json

import aws_cdk as cdk

from aws4home.aws4home_stack import Aws4HomeStack

# Load Config Files
with open('./config/config.json') as json_file:
  config = json.load(json_file)

# Set Environment
env = cdk.Environment(
  account=config['DeployAccountId'],
  region=config['DeployRegion']
)

app = cdk.App()
Aws4HomeStack(app, "Aws4HomeStack", env=env, params=config)

app.synth()
