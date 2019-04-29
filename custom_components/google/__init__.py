"""Support for Google - Calendar Event Devices."""
import logging
import os
import yaml
from datetime import timedelta, datetime

import voluptuous as vol
from voluptuous.error import Error as VoluptuousError

import homeassistant.helpers.config_validation as cv
from homeassistant.setup import setup_component
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_time_change
from homeassistant.util import convert, dt

REQUIREMENTS = [
    "google-api-python-client==1.6.4",
    "httplib2==0.10.3",
    "oauth2client==4.0.0",
]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "google"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_TRACK_NEW = "track_new_calendar"

CONF_CAL_ID = "cal_id"
CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_ENTITIES = "entities"
CONF_TRACK = "track"
CONF_SEARCH = "search"
CONF_OFFSET = "offset"
CONF_IGNORE_AVAILABILITY = "ignore_availability"

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = "!!"

NOTIFICATION_ID = "google_calendar_notification"
NOTIFICATION_TITLE = "Google Calendar Setup"
GROUP_NAME_ALL_CALENDARS = "Google Calendar Sensors"

SERVICE_SCAN_CALENDARS = "scan_for_calendars"
SERVICE_FOUND_CALENDARS = "found_calendar"
SERVICE_ADD_EVENT = "add_event"

# Service call conf
EVENT_CALENDAR_ID = "calendar_id"
EVENT_SUMMARY = "summary"
EVENT_DESCRIPTION = "description"
EVENT_START_DATETIME = "start_date_time"
EVENT_END_DATETIME = "end_date_time"
EVENT_START_DATE = "start_date"
EVENT_END_DATE = "end_date"
EVENT_IN = "in"
EVENT_IN_DAYS = "days"
EVENT_IN_WEEKS = "weeks"

DATA_INDEX = "google_calendars"

YAML_DEVICES = "{}_calendars.yaml".format(DOMAIN)
SCOPES = "https://www.googleapis.com/auth/calendar"

TOKEN_FILE = ".{}.token".format(DOMAIN)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Optional(CONF_TRACK_NEW): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_SINGLE_CALSEARCH_CONFIG = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_IGNORE_AVAILABILITY, default=True): cv.boolean,
        vol.Optional(CONF_OFFSET): cv.string,
        vol.Optional(CONF_SEARCH): cv.string,
        vol.Optional(CONF_TRACK): cv.boolean,
    }
)

event_types = "event_types"
_EVENT_IN_TYPES = vol.Schema(
    {
        vol.Exclusive(EVENT_IN_DAYS, event_types): cv.positive_int,
        vol.Exclusive(EVENT_IN_WEEKS, event_types): cv.positive_int,
    }
)

start = "start"
end = "end"

ADD_EVENT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_CALENDAR_ID): cv.string,
        vol.Required(EVENT_SUMMARY): cv.string,
        vol.Optional(EVENT_DESCRIPTION, default=""): cv.string,
        vol.Exclusive(EVENT_START_DATE, start): cv.date,
        vol.Exclusive(EVENT_END_DATE, end): cv.date,
        vol.Exclusive(EVENT_START_DATETIME, start): cv.datetime,
        vol.Exclusive(EVENT_END_DATETIME, end): cv.datetime,
        vol.Exclusive(EVENT_IN, start, end): _EVENT_IN_TYPES
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAL_ID): cv.string,
        vol.Required(CONF_ENTITIES, None): vol.All(
            cv.ensure_list, [_SINGLE_CALSEARCH_CONFIG]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def do_authentication(hass, hass_config, config):
    """Notify user of actions and authenticate.

    Notify user of user_code and verification_url then poll
    until we have an access token.
    """
    from oauth2client.client import (
        OAuth2WebServerFlow,
        OAuth2DeviceCodeError,
        FlowExchangeError,
    )
    from oauth2client.file import Storage

    oauth = OAuth2WebServerFlow(
        client_id=config[CONF_CLIENT_ID],
        client_secret=config[CONF_CLIENT_SECRET],
        scope="https://www.googleapis.com/auth/calendar",
        redirect_uri="Home-Assistant.io",
    )

    try:
        dev_flow = oauth.step1_get_device_and_user_codes()
    except OAuth2DeviceCodeError as err:
        hass.components.persistent_notification.create(
            "Error: {}<br />You will need to restart hass after fixing." "".format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    hass.components.persistent_notification.create(
        "In order to authorize Home-Assistant to view your calendars "
        'you must visit: <a href="{}" target="_blank">{}</a> and enter '
        "code: {}".format(
            dev_flow.verification_url, dev_flow.verification_url, dev_flow.user_code
        ),
        title=NOTIFICATION_TITLE,
        notification_id=NOTIFICATION_ID,
    )

    def step2_exchange(now):
        """Keep trying to validate the user_code until it expires."""
        if now >= dt.as_local(dev_flow.user_code_expiry):
            hass.components.persistent_notification.create(
                "Authentication code expired, please restart "
                "Home-Assistant and try again",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID,
            )
            listener()

        try:
            credentials = oauth.step2_exchange(device_flow_info=dev_flow)
        except FlowExchangeError:
            # not ready yet, call again
            return

        storage = Storage(hass.config.path(TOKEN_FILE))
        storage.put(credentials)
        do_setup(hass, hass_config, config)
        listener()
        hass.components.persistent_notification.create(
            "We are all setup now. Check {} for calendars that have "
            "been found".format(YAML_DEVICES),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )

    listener = track_time_change(
        hass, step2_exchange, second=range(0, 60, dev_flow.interval)
    )

    return True


def setup(hass, config):
    """Set up the Google platform."""
    if DATA_INDEX not in hass.data:
        hass.data[DATA_INDEX] = {}

    conf = config.get(DOMAIN, {})

    token_file = hass.config.path(TOKEN_FILE)
    if not os.path.isfile(token_file):
        do_authentication(hass, config, conf)
    else:
        do_setup(hass, config, conf)

    return True


def setup_services(hass, hass_config, track_new_found_calendars, calendar_service):
    """Set up the service listeners."""

    def _found_calendar(call):
        """Check if we know about a calendar and generate PLATFORM_DISCOVER."""
        calendar = get_calendar_info(hass, call.data)
        if hass.data[DATA_INDEX].get(calendar[CONF_CAL_ID], None) is not None:
            return

        hass.data[DATA_INDEX].update({calendar[CONF_CAL_ID]: calendar})

        update_config(
            hass.config.path(YAML_DEVICES), hass.data[DATA_INDEX][calendar[CONF_CAL_ID]]
        )

        discovery.load_platform(
            hass,
            "calendar",
            DOMAIN,
            hass.data[DATA_INDEX][calendar[CONF_CAL_ID]],
            hass_config,
        )

    hass.services.register(DOMAIN, SERVICE_FOUND_CALENDARS, _found_calendar)

    def _scan_for_calendars(service):
        """Scan for new calendars."""
        service = calendar_service.get()
        cal_list = service.calendarList()
        calendars = cal_list.list().execute()["items"]
        for calendar in calendars:
            calendar["track"] = track_new_found_calendars
            hass.services.call(DOMAIN, SERVICE_FOUND_CALENDARS, calendar)

    hass.services.register(DOMAIN, SERVICE_SCAN_CALENDARS, _scan_for_calendars)
    # return True

    def _add_event(call):
        """Add a new event to calendar."""
        service = calendar_service.get()
        start = {}
        end = {}
        if EVENT_IN in call.data:
            if EVENT_IN_DAYS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
                end_in = start_in + timedelta(days=1)

                start = {"date": start_in.strftime("%Y-%m-%d")}
                end = {"date": end_in.strftime("%Y-%m-%d")}
            elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
                end_in = start_in + timedelta(days=1)

                start = {"date": start_in.strftime("%Y-%m-%d")}
                end = {"date": end_in.strftime("%Y-%m-%d")}

        elif EVENT_START_DATE in call.data and EVENT_END_DATE in call.data:
            start = {"date": str(call.data[EVENT_START_DATE])}
            end = {"date": str(call.data[EVENT_END_DATE])}
        elif EVENT_START_DATETIME in call.data and EVENT_END_DATETIME in call.data:
            start = {
                "dateTime": str(call.data[EVENT_START_DATETIME].strftime("%Y-%m-%dT%H:%M:%S")),
                "timeZone": str(hass.config.time_zone),
            }
            end = {
                "dateTime": str(call.data[EVENT_END_DATETIME].strftime("%Y-%m-%dT%H:%M:%S")),
                "timeZone": str(hass.config.time_zone),
            }

        event = {
            "summary": call.data[EVENT_SUMMARY],
            "description": call.data[EVENT_DESCRIPTION],
            "start": start,
            "end": end,
        }

        event = (
            service.events()
            .insert(calendarId=call.data[EVENT_CALENDAR_ID], body=event)
            .execute()
        )

    hass.services.register(
        DOMAIN, SERVICE_ADD_EVENT, _add_event, schema=ADD_EVENT_SERVICE_SCHEMA
    )
    return True


def do_setup(hass, hass_config, config):
    """Run the setup after we have everything configured."""
    # Load calendars the user has configured
    hass.data[DATA_INDEX] = load_config(hass.config.path(YAML_DEVICES))

    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))
    track_new_found_calendars = convert(
        config.get(CONF_TRACK_NEW), bool, DEFAULT_CONF_TRACK_NEW
    )
    setup_services(hass, hass_config, track_new_found_calendars, calendar_service)

    # Ensure component is loaded
    setup_component(hass, "calendar", config)

    for calendar in hass.data[DATA_INDEX].values():
        discovery.load_platform(hass, "calendar", DOMAIN, calendar, hass_config)

    # Look for any new calendars
    hass.services.call(DOMAIN, SERVICE_SCAN_CALENDARS, None)
    return True


class GoogleCalendarService:
    """Calendar service interface to Google."""

    def __init__(self, token_file):
        """Init the Google Calendar service."""
        self.token_file = token_file

    def get(self):
        """Get the calendar service from the storage file token."""
        import httplib2
        from oauth2client.file import Storage
        from googleapiclient import discovery as google_discovery

        credentials = Storage(self.token_file).get()
        http = credentials.authorize(httplib2.Http())
        service = google_discovery.build(
            "calendar", "v3", http=http, cache_discovery=False
        )
        return service


def get_calendar_info(hass, calendar):
    """Convert data from Google into DEVICE_SCHEMA."""
    calendar_info = DEVICE_SCHEMA(
        {
            CONF_CAL_ID: calendar["id"],
            CONF_ENTITIES: [
                {
                    CONF_TRACK: calendar["track"],
                    CONF_NAME: calendar["summary"],
                    CONF_DEVICE_ID: generate_entity_id(
                        "{}", calendar["summary"], hass=hass
                    ),
                }
            ],
        }
    )
    return calendar_info


def load_config(path):
    """Load the google_calendar_devices.yaml."""
    calendars = {}
    try:
        with open(path) as file:
            data = yaml.safe_load(file)
            for calendar in data:
                try:
                    calendars.update({calendar[CONF_CAL_ID]: DEVICE_SCHEMA(calendar)})
                except VoluptuousError as exception:
                    # keep going
                    _LOGGER.warning("Calendar Invalid Data: %s", exception)
    except FileNotFoundError:
        # When YAML file could not be loaded/did not contain a dict
        return {}

    return calendars


def update_config(path, calendar):
    """Write the google_calendar_devices.yaml."""
    with open(path, "a") as out:
        out.write("\n")
        yaml.dump([calendar], out, default_flow_style=False)
