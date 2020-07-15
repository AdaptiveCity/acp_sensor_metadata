from os import listdir, path
import json
from collections import defaultdict
import sys
from datetime import datetime
import time
import numpy
from flask import request

import requests
from requests.exceptions import HTTPError


DEBUG = False

###################################################################
#
# SENSORS DataAPI
#
###################################################################

SENSORS=None

class DataAPI(object):

    def __init__(self, settings):
        global SENSORS
        print("Initializing SENSORS DataAPI")
        self.settings = settings
        SENSORS=self.load_sensors()
        print("{} loaded".format(settings["sensors_file_name"]))
        self.load_coordinate_systems()

    #NEW API FUNCTION
    def get_sensor_metadata(self, acp_id):
        print("get_sensor_metadata {}".format(acp_id))
        global SENSORS
        try:
            retrieved=SENSORS[acp_id]
        except:
            return 'no such sensor found'
        return retrieved

    def get_floor_number(self, coordinate_system, floor_number):
        print("SENSORS data_api get_floor_number({},{})".format(coordinate_system, floor_number))
        sensor_list = []
        # coords.f(acp_location) will return floor number
        coords = self.coordinate_systems[coordinate_system]

        for acp_id in SENSORS:
            #determine if the same floor
            sensor = SENSORS[acp_id]
            print("SENSORS api get_floor_number sensor={}".format(sensor))
            if "acp_location" in sensor:
                loc = sensor["acp_location"]
                if loc["system"] == coordinate_system and coords.f(loc) == int(floor_number):
                    sensor_list.append(sensor)

        self.add_xyzf(sensor_list)

        return { 'sensors': sensor_list }

    # Get sensors for a given crate_id
    def get_bim(self, crate_id):
        #iterate through sensors.json0and collect all crates
        sensor_list = []

        for acp_id in SENSORS:
            sensor = SENSORS[acp_id]
            if ( "crate_id" in sensor and
                 sensor["crate_id"] == crate_id ):
                sensor_list += [ sensor ]

        return { 'sensors': sensor_list }

    #DEBUG this function needs parameters or renaming
    #DEBUG moved from space API
    def get_gps(self):
        #response['data'].append({'sensor':sdir,
        #    'acp_ts':jdata['acp_ts'],
        #    'latitude':jdata['metadata']['gateways'][0]['latitude'],
        #    'longitude':jdata['metadata']['gateways'][0]['longitude']
        #})
        #DEBUG mockup
        json_response = """
            { "sensors": [ { "sensor": "ijl20-sodaq-ttn",
                          "acp_ts": "1591094324.123",
                          "acp_lat": 52.210927,
                          "acp_lng": 0.092740,
                          "description": "Outside FE11"
                        }
                      ]
            }
        """
        print("get_gps returning {}".format(json_response))
        return json_response

    ###########################################################################
    #
    # Support functions
    #
    ###########################################################################

    def load_sensors(self):
        file_name=self.settings["sensors_file_name"]

        #Checks if sensors.json exits so we don't have to create it
        if(path.isfile(file_name)):
            #load sensors.json and create dict
            with open(file_name,'r') as json_file:
                #WGB= json.loads(json_file.read())
                sensors=json.load(json_file)
                print(file_name," loaded successfully in load_sensors()")
        else:
            print("sensors.json failed to load in load_sensors()")
            #think of another way to load it then as we can't just use data_api
            #global data_api
            #sensors=json.loads(data_api.sensor_data())
            #print(sensors)
        return sensors

    # Update a list of objects with "acp_location_xyz" and "acp_boundary_xyz" properties
    #DEBUG this routine is common to api_bim and api_sensors so should be in acp_coordinates
    def add_xyzf(self, obj_list):
        if obj_list is None:
            return

        for obj in obj_list:
            if "acp_location" not in obj:
                # We need acp_location to for the coordinate system
                continue # no acp_location in this object so skip
            acp_location = obj["acp_location"]
            coordinate_system = acp_location["system"]
            # Note the xyz coordinates may already be cached in the bim data
            if "acp_location_xyz" not in obj:
                obj["acp_location_xyz"] = self.coordinate_systems[coordinate_system].xyzf(acp_location)
            if "acp_boundary" in obj and "acp_boundary_xyz" not in obj:
                obj["acp_boundary_xyz"] = self.acp_boundary_to_xy(coordinate_system, obj["acp_boundary"])

        return

    #DEBUG this should be in acp_coordinates
    ####################################################################
    ### In-Building coordinate system -> XYZ coords                 ###
    ####################################################################

    # Convert the building coords boundaries into equivalent latlngs
    # acp_boundary is a list [{ boundary_type, boundary: [...] }...]
    def acp_boundary_to_xy(self, coordinate_system, acp_boundary):
        xy_boundaries = [] # this is the list we will return when completed
        for boundary_obj in acp_boundary:
            # create new gps_boundary object, with type set as original
            xy_boundary = { "boundary_type": boundary_obj["boundary_type"] }
            # add the latlng points to this object
            xy_boundary["boundary"] = self.points_to_xy(coordinate_system, boundary_obj["boundary"])
            # append this new object to the list
            xy_boundaries.append(xy_boundary)

        return xy_boundaries

    def points_to_xy(self, coordinate_system, points):
        xy_points = []
        for point in points:
            xy_point = self.point_to_xy(coordinate_system, point)
            xy_points.append(xy_point)

        return xy_points

    def point_to_xy(self, coordinate_system, point):
        return self.coordinate_systems[coordinate_system].xy(point)

    #DEBUG WE'LL DEPRECATE THIS FOR NOW
    ##NEW API FUNCTION
    def get_sensors_count(self, crate_id, depth):
        floors=['GF','FF','SF']
        sensor_locations=[]
        sensor_list=[]
        #iterate through sensors.json and collect all crates
        for sensor in SENSORS:
            sensor_locations.append(SENSORS[sensor]['crate_id'])

        #using numpy makes everythign easier as we want to find frequencies
        sensor_locations = numpy.array(sensor_locations)
        #acquire crate counts to see how often they appear on the list
        (unique, counts) = numpy.unique(sensor_locations, return_counts=True)

        #iterate over unique and counts to compile a dict of sensors
        i=0
        while(i<len(unique)):
            sensor_count={}
            sensor_count['crate_id']=str(unique[i])
            sensor_count['sensors']=int(counts[i])
            sensor_list.append(sensor_count)
            i+=1

        #determine if query for floors
        if(crate_id in floors):
            floor_response=[]
            total_sensors=0
            for objects in sensor_list:
                if objects['crate_id'][0]==crate_id[0]:
                    floor_response.append(objects)
                    total_sensors+=objects['sensors']
            if(depth>0):
                return {'data': floor_response}
            else:
                return {'data': {'crate_id':crate_id, 'sensors':total_sensors}}
        #determine if querying the entire building
        elif (crate_id=='WGB'):
            if depth<=1:
                floor_response=[]
                total_sensors=0
                for floor in floors:
                    total_floor_sensors=0
                    for sensor in sensor_list:
                        if sensor['crate_id'][0]==floor[0]:
                            total_floor_sensors+=sensor['sensors']
                    total_sensors+=total_floor_sensors
                    floor_response.append({'crate_id':floor,'sensors':total_floor_sensors})
                if depth==1:
                    return {'data': floor_response}
                else:
                    return {'data':{'crate_id':crate_id, 'sensors':total_sensors}}
            else:
                #returns data for crates that are in sensors.json
                return {'data': sensor_list}
        #must be room then, check in the list
        else:
            for objects in sensor_list:
                if objects['crate_id']==crate_id:
                    return {'data': objects }


        return 'no such query found'

    ##OLD IMPLEMENTATION THAW WAS USING BIM API
    def get_sensors_count_old(self, crate_id, depth):
        global SENSORS
        #get children of the desired crate
        BIM=self.query_BIM(crate_id, depth)

        children=[]
        for i in BIM:
            children.append(i['crate_id'])

        #if no children,then return the crate itself
        if(len(children)<1):
            children.append(crate_id)

        responses=[]

        for child in children:

            #initiate the sensor counter
            counter=0

            #retrieve crate boundary, floor and type
            #since it's used to reference what crate
            #sensors belong to
            #find_in_list

            child_object=self.find_in_list(child, BIM)

            boundary=child_object['acp_boundary'][0]['boundary']
            child_floor=child_object['acp_location']['f']
            child_type=child_object['crate_type']

            json_response={}
            json_response['crate_id']=child

            for sensor in SENSORS:
                #acquire location data for x,y and floor
                x_loc=SENSORS[sensor]['acp_location']['x']
                y_loc=SENSORS[sensor]['acp_location']['y']
                sensor_floor=SENSORS[sensor]['acp_location']['f']

                #determine the type of child to check what sensors belong to it
                if child_type=='room' or child_type=='floor':
                    #for rooms and floors we have to take into account the level at which sensors are
                    #deployed, since x/y for different floors overlap
                    if(self.is_point_in_path(x_loc,y_loc,boundary) and sensor_floor==child_floor):
                        counter+=1

                if(child_type=='building'):
                    if(self.is_point_in_path(x_loc,y_loc,boundary)):
                        counter+=1

                json_response['sensor']=counter
            responses.append(json_response)
        return {'data':responses}#{'crate':crate_id, 'sensors':counter}

    #https://en.wikipedia.org/wiki/Even-odd_rule
    def is_point_in_path(self,x: int, y: int, poly) -> bool:
        #Determine if the point is in the path.

        #Args:
        #  x -- The x coordinates of point.
        #  y -- The y coordinates of point.
        #  poly -- a list of tuples [(x, y), (x, y), ...]

        #Returns:
        #  True if the point is in the path.

        num = len(poly)
        i = 0
        j = num - 1
        c = False
        for i in range(num):
            if ((poly[i][1] > y) != (poly[j][1] > y)) and \
                    (x < poly[i][0] + (poly[j][0] - poly[i][0]) * (y - poly[i][1]) /
                                    (poly[j][1] - poly[i][1])):
                c = not c
            j = i
        return c

    def find_in_list(self,item_id, item_list):
        for x in item_list:
            if x['crate_id'] == item_id:
                print ("I found it!")
                return x

    def query_BIM(self, crate_id, depth):
       # api_url = self.settings["API_BIM"]+
        api_url="http://127.0.0.1:5010/api/bim/"+"get/"+crate_id+"/"+str(depth)
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            # access JSOn content
            bim_objects = response.json()
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            exit(1)
        except Exception as err:
            print(f'Other error occurred: {err}')
            exit(1)

        floor=bim_objects[0]['acp_location']['f']
        #so we need floor=1 specifier

        api_url = "http://127.0.0.1:5010/api/bim/"+"/select/floor/"+str(floor)

        try:
            response = requests.get(api_url)
            response.raise_for_status()
            # access JSOn content
            bim_response = response.json()
            return bim_response
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            exit(1)
        except Exception as err:
            print(f'Other error occurred: {err}')
            exit(1)

    ####################################################################
    # Load the coordinate system modules into self.coordinate_systems  #
    ####################################################################

    def load_coordinate_systems(self):
        # this could be implemented like acp_decoders
        sys.path.append("..")

        self.coordinate_systems = {}

        # William Gates Building
        from acp_coordinates.WGB import WGB
        self.coordinate_systems["WGB"] = WGB()
        print("Loaded coordinate system WGB")

        # IfM Building
        from acp_coordinates.IFM import IFM
        self.coordinate_systems["IFM"] = IFM()
        print("Loaded coordinate system IFM")

        # Lockdown Lab
        from acp_coordinates.LL import LL
        self.coordinate_systems["LL"] = LL()
        print("Loaded coordinate system LL")
