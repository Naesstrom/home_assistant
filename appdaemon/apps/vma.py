import requests
import appdaemon.plugins.hass.hassapi as hass
import datetime
from datetime import timedelta, date
import json
from math import radians, sin, cos, acos

class VMA(hass.Hass):

    def initialize(self) -> None:
        self.attributes = {}
        self.attributes["messages"] = []
        self.state = "News"

        self.vma_state = ""

        self.slon = self.args["home_long"]
        self.slat = self.args["home_lat"]
        self.range_km = self.args["range_km"]

        time = self.datetime()
        self.run_every(self.get_data, time, 1 * 60)

    def get_data(self, kwargs):
        self.vma_state = self.get_state("sensor.vma")
        self.attributes["messages"] = []
        self.log("Getting data")
        r = requests.get('http://api.krisinformation.se/v2/feed?format=json')
        data = json.loads(r.text)
        for index, element in enumerate(data):
            self.make_object(index = index, element = element)
        self.make_sensor()

    def make_object(self, index, element):
        message = {}
        message['Area'] = []
        distance = None
        within_range = False

        for count, area in enumerate(element['Area']):
            message['Area'].append({ "Type" : area['Type'], "Description" : area['Description'], "Coordinate" : area['Coordinate']})
            distance = self.calculate_distance(coords = area['Coordinate'])
            if float(distance) < float(self.range_km):
                within_range = True
            self.log(f"Distance to {area['Description']}: {distance}")

        if within_range:
            message['ID'] = element['Identifier']
            message['Message'] = element['PushMessage']
            message['Updated'] = element['Updated']
            message['Published'] = element['Published']
            message['Headline'] = element['Headline']
            message['Preamble'] = element['Preamble']
            message['BodyText'] = element['BodyText']
            message['Web'] = element['Web']
            message['Language'] = element['Language']
            message['Event'] = element['Event']
            message['SenderName'] = element['SenderName']
            message['Links'] = []
            for numbers, link in enumerate(element['BodyLinks']):
                message['Links'].append(link['Url'])
            message['SourceID'] = element['SourceID']

            self.attributes["messages"].append(message)
            if element['Event'] == "Alert":
                self.state = "Alert"
            else:
                self.state = "News"

            if self.vma_state != self.state:
                self.notify(event = element['Event'], headline = element['Headline'], push_message = element['PushMessage'], link = element['Web'])

    def notify(self, event, headline, push_message, link):
        self.call_service(self.args["notify_service"], title = f"{event} - {headline}", message = f"{push_message}. {link}")

    def make_sensor(self):
        self.set_state(f"sensor.vma", state = self.state, attributes = self.attributes)
        self.log(f"sensor.vma, state = {self.state}, attributes = {self.attributes}")
        self.log("Made sensor")

    def calculate_distance(self, coords):
        coords = coords.split()
        coords = coords[0].split(',')
        elon = coords[0]
        elat = coords[1]

        #Convert coordinates to radians
        elat2 = radians(float(elat))
        slat2 = radians(float(self.slat))
        elon2 = radians(float(elon))
        slon2 = radians(float(self.slon))

        #Calculate the distance between them
        dist = 6371.01 * acos(sin(slat2)*sin(elat2) + cos(slat2)*cos(elat2)*cos(slon2 - elon2))

        return dist
