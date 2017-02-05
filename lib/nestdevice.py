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
                event = self.mapStructure(structure)
                self._log.debug("strucutre data: '%s' " % event)
                if name == structure.name:
                    return event
                # list device
                self._log.debug("structure.devices: '%s' " % structure.devices)
                # Loop through all Thermostats
                for thermostat in structure.thermostats:
                    self._log.debug("thermostat name: '%s' " % thermostat.name)
                    event = self.mapThermostat(thermostat)
                    self._log.debug("thermostat data: '%s' " % event)
                    if name == thermostat.serial:
                        return event
                # Loop through all Protects
                for protect in structure.smoke_co_alarms:
                    self._log.debug("protect name: '%s' " % protect.name)
                    event = self.mapProtect(protect)
                    self._log.debug("protect data: '%s' " % event)
                    if name == protect.name:
                        return event
                # Loop through all cameras
                for camera in structure.cameras:
                    self._log.debug("camera name: '%s' " % camera.name)
                    event = self.mapCamera(camera)
                    self._log.debug("camera data: '%s' " % event)
                    if name == protect.name:
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
                    for thermostat in structure.devices:
                        if name == thermostat.serial:
                            if thermostat.mode != "range":
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
    def mapProtect(self, protect):

        event = {
            'measurement': 'nest.protect',
            'name': protect.name,
            'where': protect.where,
            'serial': protect.serial,
            'product_id': protect.product_id,
            'auto_away': self.boolify(protect.auto_away),
            'battery_level': (int(protect.battery_level) / 54),
            # It's a supposed value due to 3x1.8V battery inside (http://forum.micasaverde.com/index.php?topic=16941)
            'battery_mv': float(protect.battery_level),
            'co_blame_duration': protect.co_blame_duration,
            'co_blame_threshold': protect.co_blame_threshold,
            'co_previous_peak': protect.co_previous_peak,
            'co_status': protect.co_status,
            'smoke_status': protect.smoke_status,
            'component_als_test_passed': self.boolify(protect.component_als_test_passed),  # noqa
            'component_co_test_passed': self.boolify(protect.component_co_test_passed),  # noqa
            'component_heat_test_passed': self.boolify(protect.component_heat_test_passed),  # noqa
            'component_hum_test_passed': self.boolify(protect.component_hum_test_passed),  # noqa
            'component_led_test_passed': self.boolify(protect.component_led_test_passed),  # noqa
            'component_pir_test_passed': self.boolify(protect.component_pir_test_passed),  # noqa
            'component_smoke_test_passed': self.boolify(protect.component_smoke_test_passed),  # noqa
            'component_temp_test_passed': self.boolify(protect.component_temp_test_passed),  # noqa
            'component_us_test_passed': self.boolify(protect.component_us_test_passed),  # noqa
            'component_wifi_test_passed': self.boolify(protect.component_wifi_test_passed),  # noqa
            'gesture_hush_enable': self.boolify(protect.gesture_hush_enable),
            'heads_up_enable': self.boolify(protect.heads_up_enable),
            'home_alarm_link_capable': self.boolify(protect.home_alarm_link_capable),
            'home_alarm_link_connected': self.boolify(protect.home_alarm_link_connected),  # noqa
            'hushed_state': self.boolify(protect.hushed_state),
            'latest_manual_test_cancelled': self.boolify(protect.latest_manual_test_cancelled),  # noqa
            'line_power_present': self.boolify(protect.line_power_present),
            'night_light_continuous': self.boolify(protect.night_light_continuous),  # noqa
            'night_light_enable': self.boolify(protect.night_light_enable),
            'ntp_green_led_enable': self.boolify(protect.ntp_green_led_enable),  # noqa
            'steam_detection_enable': self.boolify(protect.steam_detection_enable),  # noqa
            'wired_led_enable': self.boolify(protect.wired_led_enable),
            'description': protect.description,
            'software_version': protect.software_version,
            'wifi_ip_address': protect.wifi_ip_address,
            'wifi_mac_address': protect.wifi_mac_address,
            'thread_mac_address': protect.thread_mac_address,
            'battery_health_state': protect.battery_health_state,
            'capability_level': protect.capability_level,
            'certification_body': protect.certification_body,
            'creation_time': self.epoch2date(protect.creation_time / 1000),
            'home_alarm_link_type': protect.home_alarm_link_type,
            'latest_manual_test_end_utc_secs': protect.latest_manual_test_end_utc_secs,  # noqa
            'latest_manual_test_start_utc_secs': protect.latest_manual_test_start_utc_secs,  # noqa
            'replace_by_date_utc_secs': self.epoch2date(protect.replace_by_date_utc_secs),  # noqa
            'co_sequence_number': protect.co_sequence_number,
            'smoke_sequence_number': protect.smoke_sequence_number,
            'wired_or_battery': protect.wired_or_battery
        }
        return event

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
    def mapThermostat(self, thermostat):
        if thermostat.away_temperature[1] is not None:
            away_tempC = (float)('%0.1f' % thermostat.away_temperature[1])
            away_tempF = (float)('%0.1f' % CtoF(thermostat.away_temperature[1]))
        else:
            away_tempC = 'Null'
            away_tempF = 'Null'
        if thermostat.mode != "range":
            if thermostat.target is not None:
                print thermostat.targe
                #                   self._log.error(u"### Target= %s " % thermostat.target)
                #                   target = thermostat.target
        else:
            self._log.info(u"### Target temperature = " + thermostat.target)
            target = thermostat.target[1]
        event = {
            'measurement': 'nest.thermostat',
            'name': thermostat.name,
            'where': thermostat.where,
            'serial': thermostat.serial,
            #            'last_ip': thermostat.last_ip,
            'local_ip': thermostat.local_ip,
            'mode': thermostat.mode,
            #            'last_connection': self.epoch2date(thermostat.last_connection/1000),
            'error_code': thermostat.error_code,
            'fan': self.boolify(thermostat.fan),
            'temperature_C': (float)('%0.1f' % thermostat.temperature),
            'temperature_F': (float)('%0.1f' % self.CtoF(thermostat.temperature)),
            'humidity': thermostat.humidity,
            'target_C': (float)('%0.1f' % target),
            'target_F': (float)('%0.1f' % self.CtoF(target)),
            'away_low_C': (float)('%0.1f' % thermostat.away_temperature[0]),
            'away_low_F': (float)('%0.1f' % self.CtoF(thermostat.away_temperature[0])),  # noqa
            'away_high_C': away_tempC,
            'away_high_F': away_tempF,
            'hvac_ac_state': self.boolify(thermostat.hvac_ac_state),
            'hvac_cool_x2_state': self.boolify(thermostat.hvac_cool_x2_state),
            'hvac_heater_state': self.boolify(thermostat.hvac_heater_state),
            'hvac_aux_heater_state': self.boolify(thermostat.hvac_aux_heater_state),
            'hvac_heat_x2_state': self.boolify(thermostat.hvac_heat_x2_state),
            'hvac_heat_x3_state': self.boolify(thermostat.hvac_heat_x3_state),
            'hvac_alt_heat_state': self.boolify(thermostat.hvac_alt_heat_state),
            'hvac_alt_heat_x2_state': self.boolify(thermostat.hvac_alt_heat_x2_state),  # noqa
            'hvac_emer_heat_state': self.boolify(thermostat.hvac_emer_heat_state),
            'online': self.boolify(thermostat.online),
            'battery_level': float(thermostat.battery_level)
        }
        return event
