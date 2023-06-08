import json
import boto3
import datetime

from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer

tracer = Tracer()
logger = Logger()


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
def lambda_handler(event, context):

    today = datetime.date.today()
    start = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    ce = boto3.client('ce', region_name='us-east-1')
    response = ce.get_cost_and_usage(
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
                'Key': 'LINKED_ACCOUNT'
            }
        ]
    )
    return response['ResultsByTime']
