import os
import boto3
import json
import time
from datetime import datetime
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer
import requests

logger = Logger()
tracer = Tracer()

hosted_zone_id = os.environ['HOSTED_ZONE_ID']
iss_prefix = os.environ['ISS_PREFIX']
iss_url = os.environ['ISS_URL']
lat = os.environ['LATITUDE']
lon = os.environ['LONGITUDE']
alt = os.environ['ALTITUDE']
mqtt_topic = os.environ['MQTT_TOPIC']


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):
  current_duration = read_duration_from_route53(hosted_zone_id)

  publish_to_iot(mqtt_topic, "iss.gif", current_duration)

  try:
    response = requests.get(f"{iss_url}?lat={lat}&lon={lon}&alt={alt}")
    data = response.json()
    logger.debug(f"data: {data}")

    current_time = int(time.time())
    next_risetime = data['response'][0]['risetime']
    next_duration = data['response'][0]['duration']

    logger.debug(f"current time: {str(current_time)}")
    logger.debug(f"risetime0: {str(next_risetime)}")
    logger.debug(f"duration0: {str(next_duration)}")

    if next_risetime - current_time < 300:
      next_risetime = data['response'][1]['risetime']
      next_duration = data['response'][1]['duration']

      logger.debug(f"risetime1: {str(next_risetime)}")
      logger.debug(f"duration0: {str(next_duration)}")

    pass_time = datetime.utcfromtimestamp(next_risetime)
    cron_expression = 'cron(' + str(pass_time.minute) + ' ' + str(pass_time.hour) + ' ' + str(pass_time.day) + ' ' + str(pass_time.month) + ' ? ' + str(pass_time.year) + ')'

    logger.debug(f"next risetime: {datetime.utcfromtimestamp(next_risetime).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"new cron expression: {cron_expression}")

  except Exception as e:
    raise Exception('ERROR - handler - Debug by hand: ' + str(e))

  update_event_rule(cron_expression)

  write_next_duration_to_route53(hosted_zone_id, next_risetime, next_duration)


@tracer.capture_method
def publish_to_iot(topic, pattern, duration):

  try:
    iot = boto3.client("iot-data",verify = False)
    iot.publish(
      topic=topic,
      qos=0,
      retain=False,
      payload=json.dumps(
        {
          "pattern": pattern,
          "duration": duration
        }
      )
    )
  except ClientError as client_error:
    logger.error(client_error)

@tracer.capture_method
def update_event_rule(cron_expression):

  try:
    events = boto3.client("events")
    events.put_rule(
      Name=iss_prefix,
      ScheduleExpression=cron_expression,
      State='ENABLED',
      Description='Scheduled trigger for [OVERWRITTEN w/ time of the next ISS pass over specified location]',
    )
  except ClientError as client_error:
    logger.error(client_error)

@tracer.capture_method
def read_duration_from_route53(hosted_zone_id):

  try:
    route53 = boto3.client("route53")

    zone_response = route53.get_hosted_zone(
      Id=hosted_zone_id
      )
    zone_name = zone_response['HostedZone']['Name']
    record_name_duration = f"duration.{iss_prefix}.{zone_name}"

    record = route53.list_resource_record_sets(
      HostedZoneId=hosted_zone_id,
      StartRecordName=record_name_duration,
      StartRecordType='TXT',
      MaxItems='1'
    )

    current_duration = record['ResourceRecordSets'][0]['ResourceRecords'][0]['Value']
    current_duration_int = int(current_duration.strip('"'))
    return current_duration_int

  except ClientError as client_error:
    logger.error(client_error)

@tracer.capture_method
def write_next_duration_to_route53(hosted_zone_id, risetime, duration):
  duration_record = '"' + str(duration) + '"'
  risetime_record = '"' + str(risetime) + '"'

  try:
    route53 = boto3.client("route53")

    zone_response = route53.get_hosted_zone(
      Id=hosted_zone_id
      )
    zone_name = zone_response['HostedZone']['Name']
    record_name_duration = f"duration.{iss_prefix}.{zone_name}"
    record_name_risetime = f"risetime.{iss_prefix}.{zone_name}"


    route53.change_resource_record_sets(
      HostedZoneId=hosted_zone_id,
      ChangeBatch={
        'Comment': 'string',
        'Changes': [
          {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
              'Name': record_name_duration,
              'Type': 'TXT',
              'TTL': 300,
              'ResourceRecords': [
                {
                  'Value': duration_record
                }
              ]
            }
          },
          {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
              'Name': record_name_risetime,
              'Type': 'TXT',
              'TTL': 300,
              'ResourceRecords': [
                {
                  'Value': risetime_record
                }
              ]
            }
          }
        ]
      }
  )
  except ClientError as client_error:
    logger.error(client_error)

## reponse http://api.open-notify.org/iss-pass.json?lat=48.956752&lon=12.238356&alt=335
#
# {
#   "message": "success",
#   "request": {
#     "altitude": 335,
#     "datetime": 1588492443,
#     "latitude": 48.956752,
#     "longitude": 12.238356,
#     "passes": 5
#   },
#   "response": [
#     {
#       "duration": 549,
#       "risetime": 1588493504
#     },
#     {
#       "duration": 333,
#       "risetime": 1588548193
#     },
#     {
#       "duration": 618,
#       "risetime": 1588553800
#     },
#     {
#       "duration": 656,
#       "risetime": 1588559574
#     },
#     {
#       "duration": 652,
#       "risetime": 1588565396
#     }
#   ]
# }
