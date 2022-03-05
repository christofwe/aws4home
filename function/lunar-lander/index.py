import os
import boto3
import json
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

mqtt_topic = os.environ['MQTT_TOPIC']


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

  publish_to_iot(mqtt_topic, "lunar-lander", 600)


@tracer.capture_method
def publish_to_iot(topic, pattern, duration):

  try:
    iot = boto3.client("iot-data",verify = False)
    iot.publish(
      topic=topic,
      qos=0,
      payload=json.dumps(
        {
          "pattern": pattern,
          "duration": duration
        }
      ),
    )
  except ClientError as client_error:
    logger.error(client_error)
