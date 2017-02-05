#!/usr/bin/python
# -*- coding: utf-8 -*-


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

Plugin for nest thermostat and protect

Implements
==========


@author: tikismoke  (new dt domodroid at gmail dt com)
@copyright: (C) 2007-2016 Domogik project
@license: GPL(v3)
@organization: Domogik
"""
from domogik.common.plugin import Plugin
from domogikmq.message import MQMessage

from domogik_packages.plugin_nestdevice.lib.nestdevice import nestException
from domogik_packages.plugin_nestdevice.lib.nestdevice import NESTclass

import threading
import time
import json


class nestManager(Plugin):
    # -------------------------------------------------------------------------------------------------
    def __init__(self):
        """
            Init plugin
        """
        Plugin.__init__(self, name='nestdevice')

        # check if the plugin is configured. If not, this will stop the plugin and log an error
        if not self.check_configured():
            return

        # ### get all config keys
        product_id = str(self.get_config('product_id'))
        product_secret = str(self.get_config('product_secret'))
        period = int(self.get_config('period'))

        # ### get the devices list
        # for this plugin, if no devices are created we won't be able to use devices.
        self.devices = self.get_device_list(quit_if_no_device=False)
        self.log.info(u"==> device:   %s" % format(self.devices))

        # get the sensors id per device :
        self.sensors = self.get_sensors(self.devices)
        self.log.info(u"==> sensors:   %s" % format(self.sensors))

        pathData = str(self.get_data_files_directory())  # force str type for path data

        # ### Open the nest lib
        try:
            self.NESTclass = NESTclass(self.log, product_id, product_secret, period, dataPath=pathData)
        except nestException as e:
            self.log.error(e.value)
            print(e.value)
            self.force_leave()
            return

        # ### For each home device
        self.device_list = {}
        thread_sensors = None
        for a_device in self.devices:
            device_name = a_device["name"]
            device_id = a_device["id"]
            device_type = a_device["device_type_id"]
            if device_type == "nest.home":
                sensor_name = self.get_parameter(a_device, "name")
            else:
                sensor_name = self.get_parameter(a_device, "serial")
            self.device_list.update({device_id: {'name': device_name, 'named': sensor_name}})
            self.log.info(u"==> Device '{0}' (id:{1}/{2}), name = {3}".format(device_name, device_id, device_type, sensor_name))
            self.log.debug(u"==> Sensor list of device '{0}': '{1}'".format(device_id, self.sensors[device_id]))

            self.NESTclass.add_sensor(device_id, device_name, sensor_name)

        thread_sensors = threading.Thread(None,
                                          self.NESTclass.loop_read_sensor,
                                          'Main_reading_sensors',
                                          (self.send_pub_data, self.get_stop()),
                                          {})
        thread_sensors.start()
        self.register_thread(thread_sensors)
        self.ready()

    # -------------------------------------------------------------------------------------------------
    def send_pub_data(self, device_id, value):
        """ Send the sensors values over MQ
        """
        self.log.debug(u"send_pub_data : '%s' for device_id: '%s' " % (value, device_id))
        data = {}
        value_dumps = json.dumps(value)
        value_dict = json.loads(value_dumps)
        for sensor in self.sensors[device_id]:
            self.log.debug(u"value receive : '%s' for sensors: '%s' " % (value_dict[sensor], sensor))
            data[self.sensors[device_id][sensor]] = value_dict[sensor]
        self.log.debug(u"==> Update Sensor '%s' for device id %s (%s)" % (
        format(data), device_id, self.device_list[device_id]["name"]))  # {u'id': u'value'}

        try:
            self._pub.send_event('client.sensor', data)
        except:
            # We ignore the message if some values are not correct
            self.log.debug(u"Bad MQ message to send.MQ data is : {0}".format(data))
            pass

    # -------------------------------------------------------------------------------------------------
    def on_mdp_request(self, msg):
        """ Called when a MQ req/rep message is received
        """
        Plugin.on_mdp_request(self, msg)
        self.log.info(u"==> Received 0MQ messages: %s" % format(msg))
        if msg.get_action() == "client.cmd":
            reason = None
            status = True
            data = msg.get_data()

            device_id = data["device_id"]
            command_id = data["command_id"]
            if device_id not in self.device_list:
                self.log.error(
                    u"### MQ REQ command, Device ID '%s' unknown, Have you restarted the plugin after device creation ?" % device_id)
                status = False
                reason = u"Plugin nestdevice: Unknown device ID %d" % device_id
                self.send_rep_ack(status, reason, command_id, "unknown");
                return

            device_name = self.device_list[device_id]["name"]
            self.log.info(u"==> Received for device '%s' MQ REQ command message: %s" % (device_name, format(data)))
            for a_device in self.devices:
                if a_device["id"] == device_id:
                    if a_device["device_type_id"] == "nest.home":
                        sensor_name = self.get_parameter(a_device, "name")
                        self.log.info(u"==> Received for nest name or serial '%s' MQ REQ command message: %s" % (
                        sensor_name, format(data)))
                        status, reason = self.NESTclass.writeState(sensor_name, "away", data["away"])
                    elif a_device["device_type_id"] == "nest.thermostat":
                        sensor_name = self.get_parameter(a_device, "serial")
                        self.log.info(u"==> Received for nest name or serial '%s' MQ REQ command message: %s" % (
                        sensor_name, format(data)))
                        status, reason = self.NESTclass.writeState(sensor_name, "temperature", data["temperature"])

                        # This should be eaisier but not available
                    #	    sensor_name = self.get_parameter(self.device_list[device_id], "name")
                    #


                    # TODO return status by calling back for good sensors
                    #            if status:
                    #                self.send_pub_data(device_id, format(data))
                    #                self.send_pub_data(device_id, data["away"])

            self.send_rep_ack(status, reason, command_id, device_name);

            # -------------------------------------------------------------------------------------------------

    def send_rep_ack(self, status, reason, cmd_id, dev_name):
        """ Send MQ REP (acq) to command
        """
        self.log.info(u"==> Reply MQ REP (acq) to REQ command id '%s' for device '%s'" % (cmd_id, dev_name))
        reply_msg = MQMessage()
        reply_msg.set_action('client.cmd.result')
        reply_msg.add_data('status', status)
        reply_msg.add_data('reason', reason)
        self.reply(reply_msg.get())


if __name__ == "__main__":
    nestManager()
