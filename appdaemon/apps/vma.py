import requests
import appdaemon.plugins.hass.hassapi as hass
import datetime
from datetime import timedelta, date
import json
from math import radians, sin, cos, acos

class VMA(hass.Hass):

"""
slat = Start Latitude
slon = Start Longitude
elat = End Latitude
elon = End Longitude
"""

    def initialize(self) -> None:
        self.attributes = {}

        time = self.datetime()
        self.run_every(self.get_data, time, 1 * 60)

    def get_data(self, kwargs):
        self.log("Getting data")
        r = requests.get('http://api.krisinformation.se/v2/feed?format=json')
        data = json.loads(r.text)
        state = "News"
        self.log(data)
        for index, element in enumerate(data):
            if "areas" in self.args:
                for area in self.split_device_list(self.args["areas"]):
                    if area not in str(element['Area'].lower()) and "areas" in self.args:
                        self.log("Not matching area in config.")
                        continue
                    else:
                        self.make_sensor(index, element)
            else:
                self.make_sensor(index = index, element = element)

    def make_sensor(self, index, element):
        for count, area in enumerate(element['Area']):
            self.attributes[f'Affected area {count}'] = area['Description']
            self.attributes[f'Affected area {count}'] = area['Coordinate']

        self.attributes['slon,slat'] = element['Coordinate']
        self.attributes['ID'] = element['Identifier']
        self.attributes['Message'] = element['PushMessage']
        self.attributes['Published'] = element['Published']
        self.attributes['Updated'] = element['Updated']
        self.attributes['Sensor Updated'] = str(self.datetime())

        for numbers, link in enumerate(element['BodyLinks']):
            self.attributes[f'Link {numbers}'] = link['Url']

        if index == 0:
            self.set_state(f"sensor.vma", state = element['Event'], attributes = self.attributes)
        else:
            self.set_state(f"sensor.vma_{index}", state = element['Event'], attributes = self.attributes)
        self.log("Made sensor")
