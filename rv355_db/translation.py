from CONFIG import *
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from dbconn import *
from collections import defaultdict
import re

# Temporary variable, will be replaced later
floors = {'WGB':['GF','FF','SF'], 'IMF':['GFF','FFF','SFF']}

# Return all crates on a floor
def get_all_crates(floor_id):
    query = "SELECT * FROM "+TABLE_BIM+" WHERE crate_id IN (SELECT crate_id from "+TABLE_BIM+" WHERE bim_info->>'parent_crate_id'='"+floor_id+"')"

    rows = dbread(query)
    crate_dict = defaultdict(list)
    
    for row in rows:
        boundary = []
        boundaryList = re.split('{|,|}',row[1]['acp_boundary'])
        for b in boundaryList:
            if b != '':
                boundary.append(float(b))
        crate_dict[row[0]] = boundary

    return crate_dict

# Returns the crate from list of crates holding the sensor at coordinate (x,y)
def get_crate(crates, x, y):
    point = Point(float(x), float(y))
    for key in crates.keys():
        boundary = crates[key]
        if point.x < boundary[0]:
            continue
        else:
            plist = []
            i = 0
            while i < len(boundary) - 1:
                plist.append((boundary[i],boundary[i+1]))
                i+=2
            polygon = Polygon(plist)
            if polygon.contains(point):
                return key
    return ''

# Returns the (x,y) coordinates for a given crate
def getXY(crate_id):
    query = "SELECT bim_info->'acp_boundary' FROM "+TABLE_BIM+" WHERE crate_id = '"+crate_id+"'"

    rows = dbread(query)

    boundary = []
    boundaryList = re.split('{|,|}',rows[0][0])
    for b in boundaryList:
        if b != '':
            boundary.append(float(b))
    
    pointlist = []
    i = 0
    while i < len(boundary) - 1:
        pointlist.append((boundary[i],boundary[i+1]))
        i+=2
    polygon = Polygon(pointlist)
    centroidPoint = polygon.centroid

    return round(centroidPoint.x,2), round(centroidPoint.y,2)

# Returns the floor of a crate
def getCrateFloor(system, crate_id):
    if crate_id == system:
        return ''

    elif crate_id in floors[system]:
        return floors[system].index(crate_id)
    
    query = "SELECT bim_info->'parent_crate_id' FROM "+TABLE_BIM+" WHERE crate_id = '"+crate_id+"'"
    rows = dbread(query)
    return floors[system].index(rows[0][0])