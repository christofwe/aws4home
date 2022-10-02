import os
import boto3
import json
import pytz
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
tz_str = os.environ['TZ']
mqtt_topic = os.environ['MQTT_TOPIC']


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):
  # Duration of current pass over was stored in R53 record ;)
  # Message is being sent for ISS to light up
  current_duration = read_duration_from_route53(hosted_zone_id)
  publish_to_iot(mqtt_topic, "iss.gif", current_duration)
  
  tz=pytz.timezone(tz_str)
  current_time = datetime.now(tz)
  try:
    response = requests.get(f"{iss_url}&lon={lon}&lat={lat}&tz={tz_str}").json()
    logger.debug(f"response: {response}")

    passes = response['passes']

    # Find next pass over, that is at least an hour in the future. API does always return all passes for current day.
    i = 0
    for pass_over in passes:
      pass_begin = tz.localize(datetime.strptime(pass_over['begin'], "%Y%m%d%H%M%S"))
      pass_end = tz.localize(datetime.strptime(pass_over['end'], "%Y%m%d%H%M%S"))
      
      if (pass_begin - current_time).seconds > 3600:
        next_pass_index = i + 1
        break
      
      i += 1
  
    next_pass_begin = tz.localize(datetime.strptime(passes[next_pass_index]['begin'], "%Y%m%d%H%M%S"))
    next_pass_end = tz.localize(datetime.strptime(passes[next_pass_index]['end'], "%Y%m%d%H%M%S"))
    next_pass_duration = (next_pass_end - next_pass_begin).seconds
    
    logger.debug(f"current time: {str(current_time)}")
    logger.debug(f"(next_pass_begin - current_time).seconds: {str((next_pass_begin - current_time).seconds)}")
    logger.debug(f"next_pass_begin: {str(next_pass_begin)}")
    logger.debug(f"next_pass_end: {str(next_pass_end)}")
    logger.debug(f"next_pass_duration: {str(next_pass_duration)}")

    # Cron trigger in EventBridge requires time in UTC
    next_pass_utc = next_pass_begin.astimezone(pytz.utc)
    cron_expression = 'cron(' + str(next_pass_utc.minute) + ' ' + str(next_pass_utc.hour) + ' ' + str(next_pass_utc.day) + ' ' + str(next_pass_utc.month) + ' ? ' + str(next_pass_utc.year) + ')'

    logger.debug(f"next_pass_utc: {next_pass_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"new cron(UTC): {cron_expression}")

  except Exception as e:
    raise Exception('ERROR - handler - Debug by hand: ' + str(e))

  update_event_rule(cron_expression)

  write_next_duration_to_route53(hosted_zone_id, next_pass_begin, next_pass_duration)


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

## response https://www.astroviewer.net/iss/ws/predictor.php
## Note: 

# {
#     "passes": [
#         {
#             "begin": "20221002194400",
#             "end": "20221002195013",
#             ...
#         },
#         {
#             "begin": "20221003185914",
#             "end": "20221003190222",
#             ...
#         }
#     ],
#     ...
# }