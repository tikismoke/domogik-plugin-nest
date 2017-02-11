""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

Plugin for NEST protect and thermostat

Implements
==========

class NEST, nestException

@author: tikismoke
@copyright: (C) 2007-2016 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import traceback
import subprocess
import os

try:
    import nest
except RuntimeError:
    print("Error importing nest!")

import locale
import time


class nestException(Exception):
    """
    NEST exception
    """

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class NESTclass:
    """
    Get informations about nest
    """

    # -------------------------------------------------------------------------------------------------
    def __init__(self, log, client_id, client_secret, period, dataPath):
        try:
            """
            Create a nest instance, allowing to use NEST api
            """
            self._log = log
            self._sensors = []
            self.period = period
            self._dataPath = dataPath
            if not os.path.exists(self._dataPath):
                self._log.info(u"Directory data not exist, trying create : %s", self._dataPath)
                try:
                    os.mkdir(self._dataPath)
                    self._log.info(u"Nest data directory created : %s" % self._dataPath)
                except Exception as e:
                    self._log.error(e.message)
                    raise nestException("Nest data directory not exist : %s" % self._dataPath)
            if not os.access(self._dataPath, os.W_OK):
                self._log.error("User %s haven't write access on data directory : %s" % (user, self._dataPath))
                raise nestException("User %s haven't write access on data directory : %s" % (user, self._dataPath))
            access_token_cache_file = os.path.join(os.path.dirname(__file__), '../data/nest.json')
            self.napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)

        except ValueError:
            self._log.error(u"error reading Nest.")
            return

    # -------------------------------------------------------------------------------------------------
    def boolify(self, s):
        return (str)(s).lower() in ['true' '1' 't' 'y' 'yes' 'on' 'enable'
                                    'enabled']

    # -------------------------------------------------------------------------------------------------
    def epoch2date(self, epoch):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))

    # -------------------------------------------------------------------------------------------------
    def CtoF(self, t):
        return (t * 9) / 5 + 32

    # -------------------------------------------------------------------------------------------------
    def add_sensor(self, deviceid, device_name, sensor_name):
        """
        Add a sensor to sensors list.
        """
        self._sensors.append({'deviceid': deviceid, 'device_name': device_name, 'sensor_name': sensor_name})

    # -------------------------------------------------------------------------------------------------
    def readNestApi(self, name):
        """
        read the nest api
        """
        try:
            # Loop through Nest structures aka homes
            for structure in self.napi.structures:
                self._log.debug("Reading for name: '%s' " % name)
                self._log.debug("Strucutre: '%s' " % structure)
                if name == structure.name:
                    event = self.mapStructure(structure)
                    self._log.debug("strucutre data: '%s' " % event)
                    return event
#                # list device
#                self._log.debug("structure.devices: '%s' " % structure.devices)
                # Loop through all Thermostats
                for thermostat in structure.thermostats:
                    self._log.debug("thermostat name: '%s' " % thermostat.name)
                    if name == thermostat.serial:
                        event = self.mapThermostat(thermostat)
                        self._log.debug("thermostat data: '%s' " % event)
                        return event
                # Loop through all Protects
                for protect in structure.smoke_co_alarms:
                    self._log.debug("protect name: '%s' " % protect.name)
                    if name == protect.serial:
                        event = self.mapProtect(protect)
                        self._log.debug("protect data: '%s' " % event)
                        return event
                # Loop through all cameras
                for camera in structure.cameras:
                    self._log.debug("camera name: '%s' " % camera.name)
                    if name == camera.serial:
                        event = self.mapCamera(camera)
                        self._log.debug("camera data: '%s' " % event)
                        return event
            return "failed"

        except AttributeError:
            self._log.error(u"### Sensor '%s', ERROR while reading value." % name)
            return "failed"

    # -------------------------------------------------------------------------------------------------
    def writeState(self, name, command, value):
        """
            Write nest device 'name' with 'value'
        """
        self._log.debug(u"==> Receive command '%s'" % command)
        self._log.debug(u"==> Receive writeState command for '%s'" % name)
        self._log.debug(u"==> And value '%s'" % value)

        try:
            for structure in self.napi.structures:
                if command == "away":
                    if name == structure.name:
                        if str(value) == "1":
                            structure.away = "away"
                        else:
                            structure.away = "home"
                        self._log.info(u"Writing away state of '%s' to '%s'" % (name, structure.away))
                elif command == "temperature":
                    for thermostat in structure.thermostats:
                        if name == thermostat.serial:
                            if thermostat.mode != "heat-cool":
                                if int(value) > 32:
                                    thermostat.target = 32
                                elif int(value) < 9:
                                    thermostat.target = 9
                                else:
                                    thermostat.target = int(value)
                                self._log.info(u"Writing target temp of '%s' to '%s'" % (name, thermostat.target))
                            else:
                                self._log.warning(
                                    u"Settings temperature when mode is set to heat-cool is not implement yet!!!!")
                                # Todo find a way to handle this case
                elif command == "fan":
                    for thermostat in structure.thermostats:
                        if name == thermostat.serial:
			    thermostat.fan = value
                elif command == "mode":
                    for thermostat in structure.thermostats:
                        if name == thermostat.serial:
			    if value == "0":
				thermostat.mode = "heat-cool"
			    if value == "1":
				thermostat.mode = "heat"
			    if value == "2":
				thermostat.mode = "heat"
			    if value == "3":
				thermostat.mode = "eco"
			    if value == "4":
				thermostat.mode = "off"

        except AttributeError:
            errorstr = u"### Sensor '%s', ERROR while writing value." % name
            self._log.error(errorstr)
            return False, errorstr
        return True, None

    # -------------------------------------------------------------------------------------------------
    def loop_read_sensor(self, send, stop):
        """
        """
        while not stop.isSet():
#            try:  # catch error if self._sensors modify during iteration
            for sensor in self._sensors:
                val = self.readNestApi(sensor['sensor_name'])
                if val != "failed":
                    send(sensor['deviceid'], val)
                self._log.debug(u"=> '{0}' : wait for {1} seconds".format(sensor['sensor_name'], self.period))
#            except:
#                self._log.error(u"# Loop_read_sensors EXCEPTION")
#                pass
            stop.wait(self.period)

    # -------------------------------------------------------------------------------------------------
    def mapStructure(self, structure):

        event = {
            'name': structure.name,
            'postal_code': structure.postal_code,
            'num_thermostats': structure.num_thermostats,
            'time_zone': structure.time_zone,
            'peak_period_start_time': structure.peak_period_start_time,
            'peak_period_end_time': structure.peak_period_end_time,
            'eta_begin': str(structure.eta_begin),
            'country_code': structure.country_code,
            'away': structure.away
        }
        return event

    # -------------------------------------------------------------------------------------------------
    def mapProtect(self, protect):

        event = {
            'name': protect.name,
            'device': protect._device,
            'where': protect.where,
            'serial': protect.serial,
            'battery_health': protect.battery_health,
            'co_status': protect.co_status,
            'smoke_status': protect.smoke_status,
            'description': protect.description,
            'product_id': protect.product_id,
            'last_manual_test_time': protect.last_manual_test_time,
            'software_version': protect.software_version
        }
        return event

    # -------------------------------------------------------------------------------------------------
    def mapThermostat(self, thermostat):
        event = {
    	    'name': thermostat.name,
	    'where': thermostat.where,
    	    'serial': thermostat.serial,
    	    'fan': thermostat.fan,
    	    'humidity': thermostat.humidity,
    	    'mode': thermostat.mode,
    	    'has_leaf': thermostat.has_leaf,
    	    'is_using_emergency_heat': thermostat.is_using_emergency_heat,
    	    'last_connection': thermostat.last_connection,
    	    'temperature_scale': thermostat.temperature_scale,
    	    'is_locked': thermostat.is_locked,
#       'locked_temperature': thermostat.locked_temperature,
    	    'temperature': thermostat.temperature,
    	    'min_temperature': thermostat.min_temperature,
    	    'max_temperature': thermostat.max_temperature,
    	    'target': thermostat.target,
#	    'eco_temperature': thermostat.eco_temperature,
    	    'can_heat': thermostat.can_heat,
    	    'can_cool': thermostat.can_cool,
    	    'has_humidifier': thermostat.has_humidifier,
    	    'has_dehumidifier': thermostat.has_dehumidifier,
	    'has_fan': thermostat.has_fan,
	    'has_hot_water_control': thermostat.has_hot_water_control,
    	    'hot_water_temperature': thermostat.hot_water_temperature,
    	    'hvac_state': thermostat.hvac_state,
    	    'online': thermostat.online,
	    'description': thermostat.description
        }
        return event

    # -------------------------------------------------------------------------------------------------
    def mapCamera(self, camera):
        event = {
    	    'name': camera.name,
	    'where': camera.where,
	    'serial': camera.serial,
#	    'ongoing_event': camera.ongoing_event,
	    'ongoing_event': '',
#	    'has_ongoing_motion_in_zone': camera.has_ongoing_motion_in_zone,
	    'has_ongoing_motion_in_zone': '',
	    'sound_detected': camera.sound_detected,
	    'motion_detected': camera.motion_detected,
	    'person_detected': camera.person_detected,
#	    'activity_zones': camera.activity_zones,
	    'activity_zones': '',
#	    'last_event': camera.last_event,
	    'last_event': '',
	    'is_streaming': camera.is_streaming,
	    'is_video_history_enabled': camera.is_video_history_enabled,
	    'is_audio_enabled': camera.is_audio_enabled,
	    'is_public_share_enabled': camera.is_public_share_enabled,
#	    'model': camera.model,
	    'model': '',
	    'snapshot_url': camera.snapshot_url,
	    'description': camera.description,
	    'online': camera.online,
        }
        return event
