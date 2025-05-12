"""
Copy/synchronize events from share calendar to personal calendar.
"""

import os.path
import datetime
import pickle
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)


def event_exists_by_icaluid(service, calendar_id, icaluid):
    """
    Check if an event with the given original iCalUID has already been copied.
    Uses private extended properties stored on the event.
    """
    events = service.events().list(
        calendarId=calendar_id,
        privateExtendedProperty=f"orig_iCalUID={icaluid}",
        singleEvents=True,
        maxResults=1
    ).execute().get('items', [])
    return len(events) > 0


def copy_shifts(name, source_cal_id, destination_cal_id):
    service = get_calendar_service()

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=source_cal_id,
        timeMin=now,
        maxResults=250,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    for event in events:
        summary = event.get('summary', '')
        if name.lower() in summary.lower():
            icaluid = event.get('iCalUID')
            # Skip if already copied
            if event_exists_by_icaluid(service, destination_cal_id, icaluid):
                print(f"Already copied (iCalUID): {summary} [{icaluid}]")
                continue

            new_summary = f"ARC {summary}"
            new_event = {
                'summary': new_summary,
                'location': event.get('location'),
                'description': event.get('description'),
                'start': event['start'],
                'end': event['end'],
                'reminders': event.get('reminders', {'useDefault': True}),
                'colorId': '11',
                'extendedProperties': {
                    'private': {
                        'orig_iCalUID': icaluid
                    }
                }
            }

            created_event = service.events().insert(
                calendarId=destination_cal_id,
                body=new_event
            ).execute()
            print(f"Copied: {created_event['summary']} on {created_event['start'].get('dateTime', created_event['start'].get('date'))}")


def main():

    SHIFT_NAME = os.getenv("SHIFT_NAME")
    SOURCE_CAL_ID = os.getenv("SOURCE_CAL_ID")
    DESTINATION_CAL_ID = os.getenv("DESTINATION_CAL_ID")

    copy_shifts(
        name=SHIFT_NAME,
        source_cal_id=SOURCE_CAL_ID,
        destination_cal_id=DESTINATION_CAL_ID
    )


if __name__ == '__main__':
    main()