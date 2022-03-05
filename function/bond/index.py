import os
import boto3
import json
import time
from datetime import datetime
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Tracer
import requests
from bs4 import BeautifulSoup
import pytz
from pytz import timezone

logger = Logger()
tracer = Tracer()

bond_prefix = os.environ['BOND_PREFIX']
bond_url = os.environ['BOND_URL']
tz_local = os.environ['TZ']
mqtt_topic = os.environ['MQTT_TOPIC']

utc = pytz.utc
local = timezone(tz_local)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

  publish_to_iot(mqtt_topic, "bond", 7200)

  program = []

  try:
    page = requests.get(bond_url)
    soup = BeautifulSoup(page.content, 'html.parser')
    table = soup.find_all('table')[4]

    current_time_unix = int(time.time())
    logger.debug(f"current time UNIX: {str(current_time_unix)}")

    for tr in table.find_all('tr')[1:]:
      tds = tr.find_all('td')
      logger.debug(f"tds: {tds}")
      when = (tds[0].text.strip() + tds[1].text.strip()).replace("\n", "")
      when = when.replace("\xa0", "")
      when = when.replace(" ", "")
      if "/" in when:
        when = when.split("/")[1]
      logger.debug(f"when: {when}")
      show_time_naive = datetime.strptime(when, '%d.%m.%Y%H.%MUhr')
      show_time_local = local.localize(show_time_naive)
      show_time_unix = int(datetime.timestamp(show_time_local))

      logger.debug(f"show time NAIVE: {str(show_time_naive)} show time LOCAL: {str(show_time_local)} show time UNIX: {str(show_time_unix)}")

      program.append({
        'show_time_naive': show_time_naive,
        'show_time_local': show_time_local,
        'show_time_unix': show_time_unix,
        'channel': tds[2].text,
        'title': tds[3].text,
      })

    for show in program:
      if show['show_time_unix'] > current_time_unix:
        next_show_time = datetime.utcfromtimestamp(show['show_time_unix'])
        cron_expression = 'cron(' + str(next_show_time.minute) + ' ' + str(next_show_time.hour) + ' ' + str(next_show_time.day) + ' ' + str(next_show_time.month) + ' ? ' + str(next_show_time.year) + ')'

        logger.debug(f"next show time: {str(next_show_time)} new cron expression: {str(cron_expression)}")

        update_event_rule(cron_expression)
        return

  except Exception as e:
    raise Exception('ERROR - handler - Debug by hand: ' + str(e))


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

@tracer.capture_method
def update_event_rule(cron_expression):

  try:
    events = boto3.client("events")
    events.put_rule(
      Name=bond_prefix,
      ScheduleExpression=cron_expression,
      State='ENABLED',
      Description='Scheduled trigger for [OVERWRITTEN w/ time of the next Bond movie on TV]',
    )
  except ClientError as client_error:
    logger.error(client_error)