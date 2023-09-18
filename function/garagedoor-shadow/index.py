import os
import boto3
import json
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

mqtt_topic = os.environ['MQTT_TOPIC']

client = boto3.client('iot-data',verify = False)

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    logger.debug(event)
    
    payload = {
      "state":{
        "reported":{
          "garagedoor":event}
      }
    }

    client.update_thing_shadow(
      thingName='garagedoor',
      shadowName='garagedoor_1',
      payload=bytes(json.dumps(payload), 'utf-8')
    )
    
