import json
import boto3
import datetime

from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer

tracer = Tracer()
logger = Logger()


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


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
def lambda_handler(event, context):

    today = datetime.date.today()
    start = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    ce_client = boto3.client('ce', region_name='us-east-1')
    billings_sorted = get_cost(ce_client, start, end)
    return billings_sorted
    # return response['ResultsByTime']
