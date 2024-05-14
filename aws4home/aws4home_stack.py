from aws_cdk import (
    BundlingOptions,
    DockerImage,
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_route53 as route53
)
from constructs import Construct

class Aws4HomeStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, params={}, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        deploy_account_id = params['DeployAccountId']
        deploy_region = params['DeployRegion']
        iss_prefix = params['IssPrefix']
        iss_url = params['IssUrl']
        iss_long = params['IssLongitude']
        iss_lat = params['IssLatitude']
        bond_prefix = params['BondPrefix']
        bond_url = params['BondUrl']
        lunar_prefix = params['LunarPrefix']
        domain_name = params['DomainName']
        mqtt_topic = params['MqttTopic']
        tz = params['TimeZone']
        powertools_layer_arn = params['Layers']['Powertools']
        garagedoor_shadow_prefix = params['GaragedoorShadowPrefix']

        hosted_zone = route53.HostedZone.from_lookup(
            self, 'HostedZone',
            domain_name=domain_name,
            private_zone=False
        )

        powertools = lambda_.LayerVersion.from_layer_version_arn(
            self,
            id="LayerPowertools",
            layer_version_arn=powertools_layer_arn
        )

        requests = lambda_.LayerVersion(
            self, 'LayerRequests',
            code=lambda_.Code.from_asset(
                'layer/requests',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "mkdir /asset-output/python && pip install -r requirements.txt -t /asset-output/python && cp -au . /asset-output"
                    ]
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.ARM_64]
        )

        pytz = lambda_.LayerVersion(
            self, 'LayerPytz',
            code=lambda_.Code.from_asset(
                'layer/pytz',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "mkdir /asset-output/python && pip install -r requirements.txt -t /asset-output/python && cp -au . /asset-output"
                    ]
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.ARM_64]
        )

        bs4 = lambda_.LayerVersion(
            self, 'LayerBs4',
            code=lambda_.Code.from_asset(
                'layer/bs4',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "mkdir /asset-output/python && pip install -r requirements.txt -t /asset-output/python && cp -au . /asset-output"
                    ]
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[
                lambda_.Architecture.ARM_64]
        )

        iss = lambda_.Function(
            self, 'FnIss',
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(
                'function/iss',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c","cp -au . /asset-output"
                    ]
                )
            ),
            handler="index.handler",
            layers=[powertools, pytz, requests],
            tracing=lambda_.Tracing.ACTIVE,
            timeout=Duration.seconds(60),
            memory_size=128,
            environment={
                "LOG_LEVEL": "DEBUG",
                "POWERTOOLS_SERVICE_NAME": iss_prefix,
                "HOSTED_ZONE_ID": hosted_zone.hosted_zone_id,
                "ISS_PREFIX": iss_prefix,
                "ISS_URL": iss_url,
                "LATITUDE": iss_lat,
                "LONGITUDE": iss_long,
                "TZ": tz,
                "MQTT_TOPIC": mqtt_topic
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "events:DisableRule",
                        "events:PutRule"
                    ],
                    resources=[
                        f"arn:aws:events:{deploy_region}:{deploy_account_id}:rule/{iss_prefix}*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Publish"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:topic/*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Connect"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:client/*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "route53:ChangeResourceRecordSets",
                        "route53:ListResourceRecordSets",
                        "route53:GetHostedZone"
                    ],
                    resources=[
                        f"arn:aws:route53:::hostedzone/{hosted_zone.hosted_zone_id}"
                    ]
                )
            ],
            log_retention=logs.RetentionDays.ONE_MONTH
        )
        rule_iss = events.Rule(
            self, 'RuleIss',
            description=f"Scheduled trigger for {iss.function_name}",
            schedule=events.Schedule.rate(Duration.minutes(15)),
            enabled=True,
            rule_name=iss_prefix
        )
        rule_iss.add_target(targets.LambdaFunction(iss))
        route53.RecordSet(
            self, 'RecordIssDuration',
            record_type=route53.RecordType.TXT,
            record_name=f"duration.{iss_prefix}.{domain_name}",
            target=route53.RecordTarget.from_values("\"0\""),
            zone=hosted_zone
        )


        bond = lambda_.Function(
            self, 'FnBond',
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(
                'function/bond',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c","cp -au . /asset-output"
                    ]
                )
            ),
            handler="index.handler",
            layers=[bs4, powertools, pytz, requests],
            tracing=lambda_.Tracing.ACTIVE,
            timeout=Duration.seconds(60),
            memory_size=128,
            environment={
                "LOG_LEVEL": "DEBUG",
                "POWERTOOLS_SERVICE_NAME": bond_prefix,
                "BOND_PREFIX": bond_prefix,
                "BOND_URL": bond_url,
                "TZ": tz,
                "MQTT_TOPIC": mqtt_topic
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "events:DisableRule",
                        "events:PutRule"
                    ],
                    resources=[
                        f"arn:aws:events:{deploy_region}:{deploy_account_id}:rule/{bond_prefix}*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Publish"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:topic/*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Connect"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:client/*"
                    ]
                )
            ],
            log_retention=logs.RetentionDays.ONE_MONTH
        )
        rule_bond = events.Rule(
            self, 'RuleBond',
            description=f"Scheduled trigger for {bond.function_name}",
            schedule=events.Schedule.rate(Duration.days(7)),
            enabled=True,
            rule_name=bond_prefix
        )
        rule_bond.add_target(targets.LambdaFunction(bond))

        lunar_lander = lambda_.Function(
            self, 'FnLunarLander',
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(
                'function/lunar-lander',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c","cp -au . /asset-output"
                    ]
                )
            ),
            handler="index.handler",
            layers=[powertools],
            tracing=lambda_.Tracing.ACTIVE,
            timeout=Duration.seconds(60),
            memory_size=128,
            environment={
                "LOG_LEVEL": "DEBUG",
                "POWERTOOLS_SERVICE_NAME": lunar_prefix,
                "MQTT_TOPIC": mqtt_topic
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Publish"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:topic/*"
                    ]
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:Connect"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:client/*"
                    ]
                )
            ],
            log_retention=logs.RetentionDays.ONE_MONTH
        )
        # rule_lunar_lander = events.Rule(
        #     self, 'RuleLunarLander',
        #     description=f"Scheduled trigger for {lunar_lander.function_name}",
        #     schedule=events.Schedule.cron(minute="17", hour="20"),
        #     enabled=True,
        #     rule_name=lunar_prefix
        # )
        # rule_lunar_lander.add_target(targets.LambdaFunction(lunar_lander))

        garagedoor_shadow = lambda_.Function(
            self, 'FnGaragedoorShadow',
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(
                'function/garagedoor-shadow',
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c","cp -au . /asset-output"
                    ]
                )
            ),
            handler="index.handler",
            layers=[powertools],
            tracing=lambda_.Tracing.ACTIVE,
            timeout=Duration.seconds(60),
            memory_size=128,
            environment={
                "LOG_LEVEL": "DEBUG",
                "POWERTOOLS_SERVICE_NAME": garagedoor_shadow_prefix,
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iot:UpdateThingShadow"
                    ],
                    resources=[
                        f"arn:aws:iot:{deploy_region}:{deploy_account_id}:thing/*"
                    ]
                )
            ],
            log_retention=logs.RetentionDays.ONE_MONTH
        )
        # rule_garagedoor_shadow = events.Rule(
        #     self, 'RuleGaragedoorShadow',
        #     description=f"Scheduled trigger for {garagedoor_shadow.function_name}",
        #     schedule=events.Schedule.cron(minute="17", hour="20"),
        #     enabled=True,
        #     rule_name=garagedoor_shadow_prefix
        # )
        # rule_garagedoor_shadow.add_target(targets.LambdaFunction(garagedoor_shadow))