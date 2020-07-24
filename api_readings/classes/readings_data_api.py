"use strict"

from os import listdir, path
import json
from collections import defaultdict
import sys
from datetime import datetime
import time
from flask import request, make_response
from pathlib import Path

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

class DataAPI(object):

    def __init__(self, settings):
        print("Initializing SENSORS DataAPI")
        self.settings = settings
        self.basePath = self.settings['readings_base_path']

#################################################################
#  API FUNCTIONS                                                #
#################################################################

    #NEW API FUNCTION
    #returns sensor reading for X sensors
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
            sensor_metadata = self.get_sensor_metadata(acp_id)

            today = Utils.getDateToday()

            records = self.get_day_records(acp_id, today, sensor_metadata)

            response_obj["reading"] = json.loads(records[-1])

            if "metadata" in args and args["metadata"] == "true":
                response_obj["sensor_metadata"] = sensor_metadata
        except:
            print('get() sensor {} not found'.format(acp_id))
            print(sys.exc_info())
            return '{ "error": "readings_data_api get Exception" }'
        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

    def get_day(self, acp_id, args):
        response_obj = {}
        try:
            if DEBUG:
                args_str = ""
                for key in args:
                    args_str += key+"="+args.get(key)+" "
                print("get_day() {}/{}".format(acp_id,args_str) )
            # Lookup the sensor metadata, this will include the
            # filepath to the readings, and also may be returned
            # in the response.
            sensor_metadata = self.get_sensor_metadata(acp_id)

            if "date" in args:
                selected_date = args.get("date")
            else:
                selected_date = Utils.getDateToday()

            records = self.get_day_records(acp_id, selected_date, sensor_metadata)

            readings = []

            for line in records:
                readings.append(json.loads(line))

            response_obj = { "readings": readings }

            if "metadata" in args and args["metadata"] == "true":
                response_obj["sensor_metadata"] = sensor_metadata
        except:
            print('get() sensor {} not found'.format(acp_id))
            print(sys.exc_info())
            return '{ "error": "readings_data_api get_day() Exception" }'
        json_response = json.dumps(response_obj)
        response = make_response(json_response)
        response.headers['Content-Type'] = 'application/json'
        return response

    def history_data(self, args):
        if DEBUG:
            print('history_data() Requested')

        try:
            selecteddate = args.get('date')
            source = args.get('source')
            sensor = args.get('sensor')
            feature = args.get('feature')
        except:
            print("history_data() args error")
            if DEBUG:
                print(sys.exc_info())
                print(args)
            return '{ "data": [] }'

        workingDir = ''
        rdict = defaultdict(float)
        print(request)
        workingDir = ( Path(self.basePath)
                        .resolve()
                        .joinpath(source,'data_bin',self.date_to_path(selecteddate))
                     )
        if not path.exists(workingDir):
            print("history_data() bad data path "+workingDir)
            if DEBUG:
                print(args)
            return '{ "data": [] }'

        response = {}
        response['data'] = []

        for f in listdir(workingDir):
            fpath = Path(workingDir).resolve().joinpath(f)
            with open(fpath) as json_file:
                data = json.load(json_file)
                if data['acp_id'] == sensor:
                    try:
                        rdict[float(f.split('_')[0])] = data['payload_fields'][feature]
                    except KeyError:
                        pass

        for k in sorted(rdict.keys()):
            response['data'].append({'ts':str(k), 'val':rdict[k]})

        response['date'] = selecteddate
        response['sensor'] = sensor
        response['feature'] = feature

        json_response = json.dumps(response)
        return(json_response)

#################################################################
#  SUPPORT FUNCTIONS                                            #
#################################################################

    def date_to_path(self, selecteddate):
        data = selecteddate.split('-')
        return(data[0]+'/'+data[1]+'/'+data[2]+'/')

    def date_to_sensorpath(self, selecteddate):
        data = selecteddate.split('-')
        return(data[0]+'/'+data[1]+'/')

    #HELPER FUNCTION FOR NEW API
    #returns most recent readings
    def get_recent_readings(self,sensor):
        sensor_path = self.basePath + 'mqtt_acp/sensors/'
        selecteddate = Utils.getDateToday()
       #load the sensor lookup table
        response={}
        file_dir=sensor_path+sensor+'/'+Utils.date_to_sensorpath(selecteddate)+sensor+"_"+Utils.date_to_sensorpath_name(selecteddate)+".txt"

        print("attempting:",file_dir)

        #adding try/catch here in case we add sensor which has not yet sent any data
        try:
            ip=open("./"+file_dir)
            lines = ip.read().splitlines()
            last_line = lines[-1]
            jstr = last_line.strip()
            jdata = json.loads(jstr)

            response[sensor]=jdata["payload_fields"]

        except:
            print("no such sensor found, next")

        return response

    # Get a day's-worth of sensor readings for required sensor
    # readings_day will be "YYYY-MM-DD"
    # sensor_metadata is required to work out where the data is stored
    def get_day_records(self, acp_id, readings_day, sensor_metadata):

        YYYY = readings_day[0:4]
        MM   = readings_day[5:7]
        DD   = readings_day[8:10]

        day_file = sensor_metadata["acp_type_info"]["day_file"]

        readings_file_name = ( day_file.replace("<acp_id>",acp_id)
                                       .replace("<YYYY>",YYYY)
                                       .replace("<MM>",MM)
                                       .replace("<DD>",DD)
        )

        print("get_day_records() readings_file_name {}".format(readings_file_name))

        return open(readings_file_name, "r").readlines()

    #################################################
    # Get data from the Sensors API
    #################################################

    def get_sensor_metadata(self, acp_id):
        sensors_api_url = self.settings["API_SENSORS"]+'get/'+acp_id+"/"
        #fetch data from Sensors api
        try:
            response = requests.get(sensors_api_url)
            response.raise_for_status()
            # access JSON content
            sensor_metadata = response.json()
        except HTTPError as http_err:
            print(f'get_sensor_metadata HTTP GET error occurred: {http_err}')
            return { "error": "readings_data_api: get_sensor_metadata() HTTP error." }
        except Exception as err:
            print(f'space_api.py Other GET error occurred: {err}')
            return { "error": "readings_data_api: Exception in get_sensor_metadata()."}

        return sensor_metadata