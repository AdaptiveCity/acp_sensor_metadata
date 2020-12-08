"use strict"

from os import listdir, path
import json
from collections import defaultdict
import sys
from datetime import datetime
import time
from flask import request, make_response
from pathlib import Path
from jsonpath_ng import jsonpath, parse

from classes.utils import Utils

import requests

DEBUG = True

###################################################################
#
# READINGS DataAPI
#
###################################################################

#r = requests.get('https://api.github.com/repos/psf/requests')
#r.json()["description"]

class ReadingsDataAPI(object):

    def __init__(self, settings):
        print("Initializing SENSORS DataAPI")
        self.settings = settings
        self.basePath = self.settings['readings_base_path']

#################################################################
#  API FUNCTIONS                                                #
#################################################################

    # /get/<acp_id> returns most recent sensor reading for sensor
    # Note this returns data from the most recent message from the sensor,
    # which, depending on the sensor, may contain values for a subset of
    # the features.
    def get(self, acp_id, args):
        response_obj = {}
        try:
            if DEBUG:
                args_str = ""
                for key in args:
                    args_str += key+"="+args.get(key)+" "
                print("get {}/{}".format(acp_id,args_str) )
            # Lookup the sensor metadata, this will include the
            # filepath to the readings, and also may be returned
            # in the response.
            sensor_info = self.get_sensor_info(acp_id)

            today = Utils.getDateToday()

            records = self.get_day_records(acp_id, today, sensor_info)

            if len(records) > 0:
                response_obj["reading"] = json.loads(records[-1])

            if "metadata" in args and args["metadata"] == "true":
                response_obj["sensor_metadata"] = sensor_info
        except:
            print('get() sensor {} not found'.format(acp_id))
            print(sys.exc_info())
            return '{ "acp_error_msg": "readings_data_api get Exception" }'
        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

    # /get_day/<acp_id>/[?date=YY-MM-DD][&metadata=true]
    def get_day(self, acp_id, args):
        response_obj = {}

        # Lookup the sensor metadata, this will include the
        # filepath to the readings, and also may be returned
        # in the response.
        sensor_info = self.get_sensor_info(acp_id)

        if "metadata" in args and args["metadata"] == "true":
            response_obj["sensor_metadata"] = sensor_info

        # Only get readings if sensor_info is not {}
        if bool(sensor_info):
            try:
                if DEBUG:
                    args_str = ""
                    for key in args:
                        args_str += key+"="+args.get(key)+" "
                    print("get_day() {}/{}".format(acp_id,args_str) )

                if "date" in args:
                    selected_date = args.get("date")
                else:
                    selected_date = Utils.getDateToday()

                records = self.get_day_records(acp_id, selected_date, sensor_info)

                readings = []

                for line in records:
                    readings.append(json.loads(line))

                response_obj["readings"] = readings

            except FileNotFoundError as e:
                print(f'get() sensor {acp_id} readings for {selected_date} not found',file=sys.stderr)
                print(sys.exc_info())
                response_obj = {}
                response_obj["acp_error_id"] = "NO_READINGS"
                response_obj["acp_error_msg"] = "readings_data_api get_day() Exception "+str(e.__class__)
        else:
            response_obj = {}
            response_obj["acp_error_id"] = "NO_METADATA_FOR_SENSOR"
            response_obj["acp_error_msg"] = "No metadata available for this sensor, so location of readings is unknown"

        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

    # /get_feature/<acp_id> returns most recent sensor reading for sensor + feature
    def get_feature(self, acp_id, feature_id, args):
        response_obj = {}
        try:
            if DEBUG:
                args_str = ""
                for key in args:
                    args_str += key+"="+args.get(key)+" "
                print(f"Readings API get_feature {acp_id}/{feature_id}/{args_str}", file=sys.stderr)

            # Lookup the sensor metadata, this will include the
            # filepath to the readings, and also may be returned
            # in the response.
            sensor_info = self.get_sensor_info(acp_id)

            feature_reading = self.get_feature_reading(acp_id, feature_id, sensor_info)

            if feature_reading is not None:
                response_obj["reading"] = feature_reading

            if "metadata" in args and args["metadata"] == "true":
                response_obj["sensor_info"] = sensor_info
        except:
            print(f'get_feature() sensor {acp_id} exception', file=sys.stderr)
            print(sys.exc_info(), file=sys.stderr)
            return '{ "acp_error_msg": "readings_data_api get_feature Exception" }'
        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

    # /get_floor_feature/<system>/<floor>/<feature>/ returns most recent sensor reading for
    # all sensors with required feature on a given floor
    # E.g. /api/sensors/get_floor_feature/WGB/1/temperature
    # { readings: { dict acp_id -> reading }
    #   sensors: { dict acp_id -> sensor metadata }
    #   sensor_types: { dict acp_type_id -> sensor type metadata }
    # }
    def get_floor_feature(self, system, floor, feature_id, args):
        response_obj = {}
        try:
            if DEBUG:
                args_str = ""
                for key in args:
                    args_str += key+"="+args.get(key)+" "
                print(f"Readings API get_floor_feature {system}/{floor}/{feature_id}/{args_str}", file=sys.stderr)

            # Call Sensors API to find sensors on given floor
            # get_floor_sensors returns:
            # { "sensors": { },
            #   "sensor_type_info": {}
            # }
            floor_sensors = self.get_floor_sensors(system, floor)

            if "metadata" in args and args["metadata"] == "true":
                response_obj["sensors"] = floor_sensors["sensors"]
                #DEBUG get_floor_feature() Sensors API get_floor_number should return ["sensor_types"] not ["sensor_type_info"]
                response_obj["sensor_types"] = floor_sensors["sensor_type_info"]

            readings = {}

            for acp_id in floor_sensors["sensors"]:
                sensor = floor_sensors["sensors"][acp_id]
                sensor_info = response_obj["sensor_types"][sensor["acp_type_id"]]
                feature_reading = self.get_feature_reading(acp_id, feature_id, sensor_info)
                readings[acp_id] = feature_reading

            response_obj["readings"] = readings

        except:
            print(f'get_floor_feature() sensor {system} {floor} {feature_id} exception', file=sys.stderr)
            print(sys.exc_info(), file=sys.stderr)
            return '{ "acp_error_msg": "readings_data_api get_floor_feature Exception" }'
        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

#################################################################
#  SUPPORT FUNCTIONS                                            #
#################################################################

    # Get a day's-worth of sensor readings for required sensor as list of STRINGS (one per reading)
    # readings_day will be "YYYY-MM-DD"
    # sensor_info is required to work out where the data is stored
    def get_day_records(self, acp_id, readings_day, sensor_info):

        try:
            YYYY = readings_day[0:4]
            MM   = readings_day[5:7]
            DD   = readings_day[8:10]

            day_file = sensor_info["acp_type_info"]["day_file"]

            readings_file_name = ( day_file.replace("<acp_id>",acp_id)
                                           .replace("<YYYY>",YYYY)
                                           .replace("<MM>",MM)
                                           .replace("<DD>",DD)
            )

            print("get_day_records() readings_file_name {}".format(readings_file_name))
        except:
            print("get_day_records() no data for {} on {}".format(acp_id,readings_day))
            return []
        try:
            readings = open(readings_file_name, "r").readlines()
        except FileNotFoundError:
            readings = []

        return readings


    def get_feature_reading(self, acp_id, feature_id, sensor_info):

        path = parse(f'$.acp_type_info.features[{feature_id}].jsonpath')
        try:
            value_path_str = path.find(sensor_info)[0].value
            print(f'get_feature value_path "{value_path_str}"')
            value_path = parse(value_path_str)
        except:
            return f'{{ "acp_error_msg": "readings_data_api get_feature no {acp_id}/{feature_id}" }}'

        today = Utils.getDateToday()

        records = self.get_day_records(acp_id, today, sensor_info)

        # Loop backwards through the day's records until we find one with the required feature
        # NOTE each reading is a STRING
        for reading in reversed(records):
            try:
                reading_obj = json.loads(reading)
                if len(value_path.find(reading_obj)) > 0:
                    return reading_obj
            except IndexError:
                continue

        return None

    #################################################
    # Get data from the Sensors API
    #################################################

    def get_sensor_info(self, acp_id):
        print("get_sensor_info() {}".format(acp_id))
        sensors_api_url = self.settings["API_SENSORS"]+'get/'+acp_id+"/"
        #fetch data from Sensors api
        try:
            response = requests.get(sensors_api_url)
            response.raise_for_status()
            # access JSON content
            sensor_info = response.json()
        except HTTPError as http_err:
            print(f'get_sensor_info() HTTP GET error occurred: {http_err}')
            return { "acp_error_msg": "readings_data_api: get_sensor_info() HTTP error." }
        except Exception as err:
            print(f'get_sensor_info() Other GET error occurred: {err}')
            return { "acp_error_msg": "readings_data_api: Exception in get_sensor_info()."}
        return sensor_info

    #################################################
    # Get sensors for a floor from the Sensors API
    #################################################

    # E.g. get_floor_sensors('WGB',1)
    def get_floor_sensors(self, system, floor):
        print(f"get_floor_sensors {system} {floor}")
        sensors_api_url = self.settings["API_SENSORS"]+f'get_floor_number/{system}/{floor}/?metadata=true'
        #fetch data from Sensors api
        try:
            response = requests.get(sensors_api_url)
            response.raise_for_status()
            # access JSON content
            floor_sensors = response.json()
        except HTTPError as http_err:
            print(f'get_floor_sensors() HTTP GET error occurred: {http_err}')
            return { "acp_error_msg": "readings_data_api: get_floor_sensors() HTTP error." }
        except Exception as err:
            print(f'get_floor_sensors() Other GET error occurred: {err}')
            return { "acp_error_msg": "readings_data_api: Exception in get_floor_sensors()."}
        return floor_sensors
