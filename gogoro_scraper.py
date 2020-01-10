# -*- coding: utf-8 -*-

# 1. Download GoStations from Gogoro website.
# 2. Calculate reachagble area with HERE Isoline Routing.
# 3. Write the output as WKT format.
# 4. Upload to HERE Custom Location API.
# 5. Test functionality with HERE Positioning API.

import json
import operator
import os
import platform
import re
import ssl
import subprocess
import urllib.request
import zipfile
from math import radians, cos, sin, atan, tan, acos
from urllib.error import HTTPError

import certifi
import pycurl
from bs4 import BeautifulSoup

context = ssl._create_unverified_context()


def getDistance(latA, lonA, latB, lonB):
    ra = 6378140  # radius of equator: meter
    rb = 6356755  # radius of polar: meter
    flatten = (ra - rb) / ra  # Partial rate of the earth
    # change angle to radians
    radLatA = radians(latA)
    radLonA = radians(lonA)
    radLatB = radians(latB)
    radLonB = radians(lonB)

    pA = atan(rb / ra * tan(radLatA))
    pB = atan(rb / ra * tan(radLatB))
    x = acos(sin(pA) * sin(pB) + cos(pA) * cos(pB) * cos(radLonA - radLonB))
    c1 = (sin(x) - x) * (sin(pA) + sin(pB)) ** 2 / cos(x / 2) ** 2
    c2 = (sin(x) + x) * (sin(pA) - sin(pB)) ** 2 / sin(x / 2) ** 2
    dr = flatten / 8 * (c1 - c2)
    distance = ra * (x + dr)
    return distance


def json_request(req):
    json_result = json.load(urllib.request.urlopen(req, timeout=10), encoding='utf-8')
    return json_result


def wifi_positioning():
    try:
        if platform.system() == 'Windows':
            results = subprocess.check_output(["netsh", "wlan", "show", "network", "bssid"])
            results = results.decode("utf-8")  # needed in python 3
            list = results.replace('\r', '').split('\n')
            mac_list = set()
            for element in list:
                if re.match('.*BSSID.*', element):
                    mac_list.add('{"mac": "' + (element.split(' : ')[1]) + '"}')
        elif platform.system() == 'Darwin':
            results = os.popen(
                '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s -x | grep \'<string>[a-z0-9][a-z0-9]:[a-z0-9][a-z0-9]:[a-z0-9][a-z0-9]:[a-z0-9][a-z0-9]:[a-z0-9][a-z0-9]:[a-z0-9][a-z0-9]\'').read()
            list = results.replace('<string>', '').replace('</string>', '').replace('\t', '').split('\n')
            mac_list = set()
            i = 1
            while i < len(list) - 1:
                mac_list.add('{"mac": "' + (list[i]) + '"}')
                i += 1
        data = '{"wlan":[' + ','.join(i for i in mac_list) + ']}'
        print('\n' + data)
        req = urllib.request.Request(url=positioning_url, data=data.encode('ascii'), headers=positioning_headers)
        json_result = json.loads(urllib.request.urlopen(req, context=context).read().decode('utf-8'))
        lat = json_result['location']['lat']
        lon = json_result['location']['lng']
    except Exception:
        pass
        print(Exception.with_traceback())
        print('wifi positioning failed, getting ip location...')
        req = urllib.request.Request(url='http://ip-api.com/json')
        json_result = json.load((urllib.request.urlopen(req)))
        lat = json_result['lat']
        lon = json_result['lon']
    rev_geocoder(lat, lon)
    return lat, lon


def gogoro_vm_to_gfe_wkt():
    wkt = []
    url = 'https://webapi.gogoro.com/api/vm/list'
    req = urllib.request.Request(url)
    output = open('wktoutput.wkt', mode='w', encoding='utf-8')
    column_names = 'vm_id\tvm_name\tvm_addr\tvm_lat\tvm_lon\trange\twkt\n'
    output.write(column_names)
    json_request = json.load(urllib.request.urlopen(req, timeout=10, context=context), encoding='utf-8')
    for gogoro_vms in json_request:
        vm_id = gogoro_vms['Id']
        vm_name = eval(gogoro_vms['LocName'])['List'][1]['Value']
        vm_addr = eval(gogoro_vms['Address'])['List'][1]['Value']
        vm_lat = gogoro_vms['Latitude']
        vm_lon = gogoro_vms['Longitude']
        radius = '35000'
        req = 'https://isoline.route.cit.api.here.com/routing/7.2/calculateisoline.json?maxpoints=65535&quality=1&mode=fastest;pedestrian;traffic:disabled;motorway:-3&destination={},{}&rangetype=distance&range={}&app_id={}&app_code={}'.format(
            vm_lat, vm_lon, radius, app_id, app_code)
        json_result = json.loads(urllib.request.urlopen(req, context=context).read().decode('utf-8') + '\n')
        isolines = json_result['response']['isoline']
        wkt_coords = []
        for isoline in isolines:
            range = isoline['range']
            geoshape = isoline['component'][0]['shape']
            for element in geoshape:
                isoline_lat = element.split(',')[0]
                isoline_lon = element.split(',')[1]
                wkt_coords.append(str(isoline_lon + ' ' + isoline_lat))
                wkt.append([vm_id, vm_name, vm_addr, vm_lat, vm_lon, range, geoshape, wkt_coords])
            wkt.append([vm_id, vm_name, vm_addr, vm_lat, vm_lon, range, wkt_coords])
            gf_wkt = ('{}\t{}\t{}\t{}\t{}\t{}\tPOLYGON(({}))').format(vm_id, vm_name, vm_addr, vm_lat, vm_lon, range,
                                                                      ','.join(
                                                                          wkt_coord for wkt_coord in wkt_coords)) + '\n'
            output.write(gf_wkt)
    output.flush()
    return wkt


def get_eta(ori_lat, ori_lon, dest_lat, dest_lon):
    route_url = 'https://route.cit.api.here.com/routing/7.2/calculateroute.json?'
    wp0 = ('{},{}'.format(ori_lat, ori_lon))
    wp1 = ('{},{}'.format(dest_lat, dest_lon))
    route_options = '&mode=fastest;car;traffic:enabled&departure=now&motorway=-3&language=zh-TW'
    req = route_url + 'app_id=' + app_id + '&app_code=' + app_code + '&waypoint0=geo!' + wp0 + '&waypoint1=geo!' + wp1 + route_options
    json_result = json.loads(urllib.request.urlopen(req, context=context).read().decode('utf-8') + '\n')
    trafficTime = json_result.get('response').get('route')[0].get('summary').get('trafficTime')
    eta_min = int(trafficTime) / 60
    eta_sec = int(trafficTime) % 60
    eta = '{}m{}s'.format(int(eta_min), eta_sec)
    distance = str(json_result.get('response').get('route')[0].get('summary').get('distance')) + 'm'
    maneuvers = json_result.get('response').get('route')[0].get('leg')[0].get('maneuver')
    instructions = []
    for maneuver in maneuvers:
        instruction = maneuver['instruction']
        instructions.append(BeautifulSoup(instruction, 'html.parser').text.replace(' ', ''))
    return eta, distance, instructions


def upload_gfe(url):
    print(url)
    try:
        data = zipfile.ZipFile('wktoutput.wkt.zip', mode='w')
        data.write('wktoutput.wkt')
        data.close()
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.HTTPPOST, [
            ('zipfile', (
                c.FORM_FILE, 'wktoutput.wkt.zip',
                c.FORM_CONTENTTYPE, 'multipart/form-data',
            )),
        ])
        c.setopt(pycurl.CAINFO, certifi.where())
        c.perform()
        c.close()
    except HTTPError as e:
        print('The server couldn\'t fulfill the request.')
        print('Error code: ', e.code)


def vm_matrix(ori_lat, ori_lon, vm_list):
    matrix_routing_url = 'https://matrix.route.cit.api.here.com/routing/7.2/calculatematrix.json?mode=fastest%3Bcar%3Btraffic%3Aenabled%3B&start0={}%2C{}&{}&app_id={}&app_code={}'
    vm_matrix_list = []
    vm_counts = len(vm_list)
    # print(time.strftime('%H:%M:%S'), 'found {} gogoro vm(s) nearby.'.format(vm_counts))
    if len(vm_list) > 0:
        i = 0
        while i < len(vm_list):
            vm = vm_list[i]
            vm_matrix_list.append('destination{}={},{}'.format(i, vm[1], vm[2]))
            i += 1
        vm_matrix_input = '&'.join(vm_entry for vm_entry in vm_matrix_list)
        matrix_json_result = json.load(
            urllib.request.urlopen(matrix_routing_url.format(ori_lat, ori_lon, vm_matrix_input, app_id, app_code),
                                   context=context))
        matrix_entries = matrix_json_result.get('response').get('matrixEntry')
        min_cost = 99999999
        for matrix_entry in matrix_entries:
            destination_index = matrix_entry['destinationIndex']
            cost_factor = matrix_entry['summary']['costFactor']
            if cost_factor < min_cost:
                min_cost = cost_factor
                min_cost_vm = (vm_list[destination_index], min_cost)
        nearest_vm_name = min_cost_vm[0][0]
        nearest_vm_add = min_cost_vm[0][3]
        nearest_vm_info = ('nearest GoStation: {}/{}'.format(nearest_vm_name, nearest_vm_add))
        # print(time.strftime('%H:%M:%S'), nearest_vm_info)
        nearest_vm_lat = min_cost_vm[0][1]
        nearest_vm_lon = min_cost_vm[0][2]
        travel_info = get_eta(ori_lat, ori_lon, nearest_vm_lat, nearest_vm_lon)
        eta = travel_info[0]
        dot = travel_info[1]
        maneuvers = travel_info[2]
        print(nearest_vm_info)
        return nearest_vm_name, nearest_vm_add, nearest_vm_lat, nearest_vm_lon, eta, dot, maneuvers
    else:
        return None


def vm_finder(layer_id, input_lat, input_lon):
    checker_url = 'https://gfe.api.here.com/2/search/proximity.json?layer_ids={}&app_id={}&app_code={}&proximity={},{},{}'.format(
        layer_id, app_id, app_code, input_lat, input_lon, proximity)
    try:
        i = -1
        json_result = json.load(urllib.request.urlopen(checker_url, context=context))
        vm_list = []
        if len(json_result.get('geometries')) > 0:
            for result in (json_result.get('geometries')):
                i += 1
                vm_name = result.get('attributes').get('VM_NAME')
                vm_lat = float(result.get('attributes').get('VM_LAT'))
                vm_lon = float(result.get('attributes').get('VM_LON'))
                vm_addr = result.get('attributes').get('VM_ADDR')
                vm_air_distance = getDistance(input_lat, input_lon, vm_lat, vm_lon)
                vm_list.append([vm_name, vm_lat, vm_lon, vm_addr, vm_air_distance])
        vm_list = sorted(vm_list, key=operator.itemgetter(4))[:10]
        return vm_matrix(input_lat, input_lon, vm_list)
    except HTTPError as e:
        print('Error code: ', e.code)
        pass


def rev_geocoder(lat, lon):
    results = json.load(urllib.request.urlopen(
        '{}{},{},1000&mode=retrieveAddresses&maxResults=3&gen=8&app_id={}&app_code={}'.format(rev_geocoder_url, lat,
                                                                                              lon, app_id, app_code),
        context=context))['Response']['View'][0]['Result']
    for result in results:
        if result['MatchQuality'].get('Street'):
            address = result['Location']['Address']['Label']
            break
        else:
            continue
    print('\nyour location: {},{} ({})'.format(lat, lon, address))
    return address


app_id = ''  # YOUR APP ID
app_code = ''  # YOUR APP CODE
proximity = 0
context = ssl._create_unverified_context()  # http://stackoverflow.com/questions/27835619/ssl-certificate-verify-failed-error
gogoro_gf_id = 'GGR'
gen = 'gen=8'
lang = 'en-US'
positioning_headers = {'Content-Type': 'application/json'}
rev_geocoder_url = 'https://reverse.geocoder.cit.api.here.com/6.2/reversegeocode.json?prox='
upload_url = 'https://gfe.api.here.com/2/layers/upload.json?layer_id={}&app_id={}&app_code={}'.format(
    gogoro_gf_id, app_id, app_code)
positioning_url = 'https://pos.cit.api.here.com/positioning/v1/locate?app_id={}&app_code={}'.format(app_id,
                                                                                                    app_code)

# GENERATING GEOFENCING FOR GOGORO VM AND WRITE wktoutput.txt
# gogoro_vm_to_gfe_wkt()

# UPLOADING GOGORO VM GEOFENCING TO HERE CLE
# upload_gfe(upload_url)

# WIFI POSITIONING AND FIND THE NEAREST GOGORO VM
p = wifi_positioning()
vm_finder_result = vm_finder(gogoro_gf_id, p[0], p[1])
