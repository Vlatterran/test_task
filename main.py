import asyncio
import os.path

import dateutil.parser
from dateutil.parser import parse
from pprint import pprint

import model
from model import Order

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file creds.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1Tgmkt3XjGCeGgoUURNJKAFjQDfOzOsTZpaeWGkRx3NQ'


class GoogleSheet:
    def __init__(self, sheet_id, creds_file='creds.json', token_file='token.json'):
        creds = None
        self.sheet_id = sheet_id
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, 'w') as token:
                token.write(creds.to_json())

        service = build('sheets', 'v4', credentials=creds)
        self.sheet = service.spreadsheets()
        service = build('drive', 'v3', credentials=creds)
        self.file = service.revisions()
        self.last_update = self._get_last_update()

    def read(self, range_):
        return self.sheet.values().get(spreadsheetId=self.sheet_id, range=range_).execute()

    async def aread(self, range_):
        return await asyncio.to_thread(self.read, range_=range_)

    def _get_last_update(self):
        return sorted([parse(revision['modifiedTime'])
                       for revision in self.file.list(fileId=self.sheet_id).execute()['revisions']],
                      reverse=True)[0]

    def updated(self):
        if self.last_update != (new := self._get_last_update()):
            self.last_update = new
            return True
        return False

    async def a_updated(self):
        return await asyncio.to_thread(self.updated)


async def main():
    await model.init()
    await Order.all().delete()
    sheet = GoogleSheet(SAMPLE_SPREADSHEET_ID)
    lines = (await sheet.aread('A2:D'))['values']
    orders = []
    for line in lines:
        orders.append(Order(number=line[1],
                            cost_usd=line[2],
                            cost_rub=line[2],
                            delivery_date=dateutil.parser.parse(line[3])))
    await Order.bulk_create(orders)
    while True:
        if await sheet.a_updated():
            pprint(lines := (await sheet.aread('A2:D'))['values'])
            orders = []
            for line in lines:
                orders.append(Order(number=line[1],
                                    cost_usd=line[2],
                                    cost_rub=line[2],
                                    delivery_date=dateutil.parser.parse(line[3])))
            update_task = Order.bulk_create(orders,
                                            update_fields=('cost_usd', 'cost_rub', 'delivery_date'),
                                            on_conflict=('number',))
            delete_task = Order.filter(number__not_in=[line[1] for line in lines]).delete()
            await asyncio.gather(update_task, delete_task)
        await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
