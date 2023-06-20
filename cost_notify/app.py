import json
import boto3
import datetime
import os
import pandas as pd
from itertools import groupby

from zoneinfo import ZoneInfo
from tabulate import tabulate
from urllib.request import Request, urlopen, URLError, HTTPError
from aws_lambda_powertools import Logger
from aws_lambda_powertools import Tracer

tracer = Tracer()
logger = Logger()

SLACK_WEBHOOK_URL = os.environ['SLACK_WEBHOOK_URL']
tokyo = ZoneInfo("Asia/Tokyo")

# def get_account_list(response) -> list[str]:
#     account_list = []
#     for item in response['ResultsByTime'][0]['Groups']:
#         account_list.append(item['Keys'][1])

#     account_list=list(set(account_list))
#     return(account_list)


def get_account_name(list_account_res, accountid) -> str:
    for account in list_account_res['Accounts']:
        if accountid == account['Id']:
            return account.get('Name', "NoName")
    return "NoMatch"


def get_cost(ce_client, start, end) -> dict:
    get_cost_res = {}
    billings_raw = []

    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start,
            'End': end,
        },
        Granularity='DAILY',
        Metrics=[
            'UnblendedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            },
            {
                'Type': 'DIMENSION',
                'Key': 'LINKED_ACCOUNT'
            }
        ]
    )

    for item in response['ResultsByTime'][0]['Groups']:
        billings_raw.append(
            {
                'account': item['Keys'][1],
                'service_name': item['Keys'][0],
                'billing': round(
                    float(
                        item['Metrics']['UnblendedCost']['Amount']),
                    2)})

    billings_raw.sort(key=lambda m: m['account'])

    for key, group in groupby(billings_raw, key=lambda m: m['account']):
        print("key:", key)
        tmp_billing_list = []
        for billing in group:
            tmp_billing_list.append(billing)

        billings_sorted = sorted(
            tmp_billing_list,
            key=lambda x: x['billing'],
            reverse=True)
        get_cost_res[str(key)] = billings_sorted[:10]

    return (get_cost_res)


def generate_slack_message(
        account: str,
        account_name: str,
        billing_sorted: list,
        start: str,
        end: str) -> str:
    service_list = [x['service_name'] for x in billing_sorted]
    billing_list = [x['billing'] for x in billing_sorted]
    df = pd.DataFrame({
        'Service': service_list,
        'Cost': billing_list
    })

    dfstr = df.to_string(index_names=False)
    # print(dfstr)
    # print(df.dtypes)

    message = {
        "blocks": [
            {
                "type": "header", "text": {
                    "type": "plain_text", "text": "{}〜{} {} ({})".format(
                        start, end, account_name, account)}}, {
                "type": "section", "text": {
                    "type": "mrkdwn", "text": "```\n{}\n```".format(
                        tabulate(
                            df, headers="keys", tablefmt="psql"))}}], }
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
    today = datetime.datetime.now(tokyo)
    today_1d = today - datetime.timedelta(days=1)
    today_2d = today - datetime.timedelta(days=2)
    start = today_2d.strftime('%Y-%m-%d')
    end = today_1d.strftime('%Y-%m-%d')
    ce_client = boto3.client('ce', region_name='us-east-1')
    get_cost_res = get_cost(ce_client, start, end)
    org_client = boto3.client('organizations', region_name='us-east-1')
    list_account_res = org_client.list_accounts()
    logger.info(list_account_res)
    for account, billing_list in get_cost_res.items():
        account_name = get_account_name(list_account_res, account)
        slack_message = generate_slack_message(
            account, account_name, billing_list, start, end)
        logger.info(slack_message)
        send_slack_message(slack_message, SLACK_WEBHOOK_URL)
    return None
