import json
import os.path
from enum import Enum
from functools import wraps
from pprint import pprint

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1eEwyAhWRlf2MuycC96qokecqLa5WX8aeA3RUfC7i7mc'


class ValueInputOption(Enum):
    RAW = 'RAW'
    USER_ENTERED = 'USER_ENTERED'


def catch_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, *kwargs)
        except HttpError as e:
            print(e)

    return wrapper


class GoogleSheet:
    def __init__(self, sheet_id, creds_file='creds.json', token_file='token.json'):
        creds = None
        self.sheet_id = sheet_id
        if os.path.exists('token.json'):
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

    @catch_error
    def read(self, range):
        return self.sheet.values().get(spreadsheetId=self.sheet_id, range=range).execute()

    @catch_error
    def write(self, range: str, values: list[list], value_input_option: ValueInputOption = ValueInputOption.RAW):
        return self.sheet.values().update(
            spreadsheetId=self.sheet_id, range=range,
            valueInputOption=value_input_option.value, body=dict(values=values)).execute()

    @catch_error
    def clear(self, range=''):
        return self.sheet.values().clear(spreadsheetId=self.sheet_id, range=range).execute()


def main():
    sheet = GoogleSheet(SAMPLE_SPREADSHEET_ID)
    actions = (
        'Read values',
        'Write values',
        'Clear cells',
        'Exit'
    )
    while True:
        print('Actions:')
        for i, action in enumerate(actions, start=1):
            print(f'{i}. {action}')
        choice = input('Choose action: ')
        if not choice.isdigit() or not (0 < (choice := int(choice)) < len(actions)):
            continue
        if choice == 4:
            return
        range_ = input('Input range: ')
        if choice == 1:
            values = sheet.read(range_).get('values', [])
            if values is not None:
                pprint(values)
        elif choice == 2:
            while True:
                try:
                    values = json.loads(input('Input values as list of lists: '))
                    break
                except json.decoder.JSONDecodeError:
                    print('Invalid input')
            pprint(sheet.write(range_, values))
        elif choice == 3:
            pprint(sheet.clear(range_))
        print()


if __name__ == '__main__':
    main()
