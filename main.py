import asyncio
import datetime
import os.path
import typing
from pathlib import Path
from typing import Callable, Optional, Awaitable

import httpx
import tortoise.exceptions
import tortoise.transactions
import typer
from bs4 import BeautifulSoup
from dateutil.parser import parse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from tortoise.expressions import F

from models import Order, init_db

# If modifying these scopes, delete the file creds.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly',
          'https://www.googleapis.com/auth/drive.readonly']


class GoogleSheet:
    """
    Representing google spreadsheet
    """
    def __init__(self, sheet_id: str, creds_file: typing.Union[str, bytes, os.PathLike],
                 token_file: typing.Union[str, bytes, os.PathLike]):
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
        """
        Reading range from spreadsheet
        :param range_: The A1 notation or R1C1 notation of the range to retrieve values from
        :return: list[list] with values in given range
        """
        return self.sheet.values().get(spreadsheetId=self.sheet_id, range=range_).execute()['values']

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

    async def updates(self, delay: int):
        """
        Checks every *delay* seconds if any updates happened in spreadsheet and yields datetime if so
        :param delay:
        :return:
        """
        while True:
            if await self.a_updated():
                yield self.last_update
            await asyncio.sleep(delay)

    async def a_updated(self):
        return await asyncio.to_thread(self.updated)


class ExchangeRates:
    """
    Class that contains exchange rates for currencies relative to the ruble from the www.cbr.ru
    """
    url = 'https://www.cbr.ru/scripts/XML_daily.asp'

    def __init__(self):
        self._values = self._parse(httpx.get(self.url).text.encode('1251'))

    async def start_updating(self,
                             on_update: Optional[Callable[['ExchangeRates'], Awaitable]] = None):
        """
        Starting infinite cycle of updating exchange rates ance per day at 14:00
        :param on_update: coroutine function that will be called on update
        :return: None
        """
        for delay in self._delays(datetime.timedelta(hours=24), datetime.time(hour=14)):
            await asyncio.sleep(delay.total_seconds())
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.url)
                self._values = self._parse(resp.text.encode('1251'))
            if on_update is not None:
                await on_update(self)

    @staticmethod
    def _delays(frequency: datetime.timedelta,
                start: datetime.time):
        next_time = datetime.datetime.combine(datetime.datetime.today(), start)
        if start <= datetime.datetime.now().time():
            next_time += frequency * ((datetime.datetime.now() - next_time) // frequency + 1)
        while True:
            yield next_time - datetime.datetime.now()
            next_time += frequency * ((datetime.datetime.now() - next_time) // frequency + 1)

    @staticmethod
    def _parse(xml):
        soup = BeautifulSoup(xml, features='xml')
        res = {}
        for i in soup.select('Valute'):
            res[i.find('CharCode').text] = float(i.find('Value').text.replace(',', '.'))
        return res

    def __getitem__(self, item):
        return self._values[item]

    def keys(self):
        return self._values.keys()


async def update_table(lines, usd_cost):
    """
    Creates a transaction that deletes all data in table and puts new values
    :param lines: list of lists in form of [any, <INT:ID>, <FLOAT:COST_$>, <DD.MM.YYYY:DELIVERY_DATE>]
    :param usd_cost: cost of usd relative to the ruble
    :return: list of Order objects
    """
    async with tortoise.transactions.in_transaction():
        await Order.all().delete()
        await Order.bulk_create(order for line in lines
                                if (order := Order.from_googlesheet_line(line, usd_cost=usd_cost)) is not None)


async def _main(spreadsheet_id: str,
                db_url: str,
                conditionals: Path,
                token: Path,
                polling_delay: int):
    await init_db(db_url)
    sheet = GoogleSheet(spreadsheet_id, conditionals, token)
    print(f'Tracking for updates in https://docs.google.com/spreadsheets/d/{spreadsheet_id}')
    lines = await sheet.aread('A2:D')
    rates = ExchangeRates()
    asyncio.ensure_future(rates.start_updating(on_update=
                                               lambda rates: Order.all().update(cost_rub=rates['USD'] * F('cost_usd'))))
    await update_table(lines, rates['USD'])
    async for _ in sheet.updates(polling_delay):
        lines = await sheet.aread('A2:D')
        await update_table(lines, rates['USD'])


def main(spreadsheet_id: str = typer.Argument(..., help='Id of google sheet to track'),
         db_url: str = typer.Argument(..., help='URL of database'),
         conditionals: Path = typer.Argument('creds.json'),
         token: Path = typer.Argument('token.json'),
         polling_delay: int = typer.Argument(10, help='Delay in seconds to check if there is any updates in table')):
    asyncio.run(_main(spreadsheet_id, db_url, conditionals, token, polling_delay))


if __name__ == '__main__':
    typer.run(main)
