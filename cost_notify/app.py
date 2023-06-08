import json
import boto3
import datetime
import os
import pandas as pd

from urllib.request import Request, urlopen, URLError, HTTPError
from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer

tracer = Tracer()
logger = Logger()

SLACK_WEBHOOK_URL = os.environ['SLACK_WEBHOOK_URL']


def get_cost(ce_client, start, end) -> list:

    billings_raw = []

    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start,
            'End': end,
        },
        Granularity='DAILY',
        Metrics=[
            'NetUnblendedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )
    # logger.info(response)
    for item in response['ResultsByTime'][0]['Groups']:
        billings_raw.append({
            'service_name': item['Keys'][0],
            'billing': item['Metrics']['NetUnblendedCost']['Amount']
        })
    billings_sorted = sorted(
        billings_raw,
        key=lambda x: x['billing'],
        reverse=True)
    logger.info(billings_sorted[:10])
    return billings_sorted[:10]


def generate_slack_message(billing_sorted: list) -> str:
    df = pd.DataFrame({
    '名前' :['田中', '山田', '高橋'],
    '役割' : ['営業部長', '広報部', '技術責任者'],
    '身長' : [178, 173, 169]
    })
    print(df)
    # print(df.dtypes)


    message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": df.to_string()
                }
            }
        ],

    }
    return message


def send_slack_message(message: str, webhookurl: str) -> None:
    slack_message = message
    req = Request(webhookurl, data=json.dumps(slack_message).encode("utf-8"),
                  headers={'content-type': 'application/json'})
    print('------ send Slack message! ------')
    try:
        response = urlopen(req)
        print("Request success : ", response.read())
    except HTTPError as e:
        print("Request failed : ", e.code, e.reason)
    except URLError as e:
        print("Server connection failed: ", e.reason, e.reason)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
def lambda_handler(event, context) -> None:

    today = datetime.date.today()
    start = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    ce_client = boto3.client('ce', region_name='us-east-1')
    billings_sorted = get_cost(ce_client, start, end)
    slack_message = generate_slack_message(billings_sorted)
    send_slack_message(slack_message, SLACK_WEBHOOK_URL)
    return None
    # return billings_sorted
    # return response['ResultsByTime']
