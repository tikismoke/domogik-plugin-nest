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

from domogik_packages.plugin_nest.lib.plugin_nest import nestException
from domogik_packages.plugin_nest.lib.plugin_nest import NESTclass

import threading
import time


class nestManager(Plugin):

    # -------------------------------------------------------------------------------------------------
    def __init__(self):
        """
            Init plugin
        """
        Plugin.__init__(self, name='nest')

        # check if the plugin is configured. If not, this will stop the plugin and log an error
        if not self.check_configured():
            return

        # ### get all config keys
        user = str(self.get_config('email_address'))
        password = str(self.get_config('password'))
        period = int(self.get_config('period'))


        # ### get the devices list
        # for this plugin, if no devices are created we won't be able to use devices.
        self.devices = self.get_device_list(quit_if_no_device=False)
        self.log.info(u"==> device:   %s" % format(self.devices))

        # get the sensors id per device :
        self.sensors = self.get_sensors(self.devices)
        self.log.info(u"==> sensors:   %s" % format(self.sensors))

	# ### Open the nest lib
        try:
            self.NESTclass = NESTclass(self.log, user, password, period)
        except nestException as e:
            self.log.error(e.value)
            print(e.value)
            self.force_leave()
            return

        # ### For each device
        self.device_list = {}
        threads = {}
        for a_device in self.devices:
            self.log.info(u"a_device:   %s" % format(a_device))

            device_name = a_device["name"]
            device_id = a_device["id"]
            device_type = a_device["device_type_id"]
            sensor_name = self.get_parameter(a_device, "name")
            self.device_list.update({device_id : {'name': device_name, 'named': sensor_name}})

            if device_type != "gpio.output":
                self.log.info(u"==> Device '{0}' (id:{1}/{2}), name = {3}".format(device_name, device_id, device_type, sensor_name))
                self.log.debug(u"==> Sensor list of device '{0}': '{1}'".format(device_id, self.sensors[device_id]))

                self.log.debug(u"==> Launch reading thread for '%s' device !" % device_name)
                thr_name = "dev_{0}".format(device_id)
                threads[thr_name] = threading.Thread(None,
                                                        self.NESTclass.loop_read_sensor,
                                                        thr_name,
                                                            (device_id,
                                                            device_name,
                                                            sensor_name,
                                                            self.send_pub_data,
                                                            self.get_stop()),
                                                        {})
                threads[thr_name].start()
                self.register_thread(threads[thr_name])
                self.log.info(u"==> Wait some time before running the next scheduled threads ...")
                time.sleep(5)        # Wait some time to not start the threads with the same interval et the same time.

            else:
                self.log.info(u"==> Device '{0}' (id:{1}/{2}), pin = {3}".format(device_name, device_id, device_type, sensor_pin))

        self.ready()


    # -------------------------------------------------------------------------------------------------
    def send_pub_data(self, device_id, value):
        """ Send the sensors values over MQ
        """
        data = {}
        for sensor in self.sensors[device_id]:                  # "for" nécessaire pour les 2 sensors counter : '1-wire counter diff' et '1-wire counter'
            data[self.sensors[device_id][sensor]] = value       # sensor = sensor name in info.json file
        self.log.debug(u"==> Update Sensor '%s' for device id %s (%s)" % (format(data), device_id, self.device_list[device_id]["name"]))    # {u'id': u'value'}

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
                self.log.error(u"### MQ REQ command, Device ID '%s' unknown, Have you restarted the plugin after device creation ?" % device_id)
                status = False
                reason = u"Plugin rpigpio: Unknown device ID %d" % device_id
                self.send_rep_ack(status, reason, command_id, "unknown") ;
                return

            device_name = self.device_list[device_id]["name"]
            self.log.info(u"==> Received for device '%s' MQ REQ command message: %s" % (device_name, format(data)))

            status, reason = self.GPIOclass.writeSensor(self.device_list[device_id]["pin"], data["level"])
            if status:
                self.send_pub_data(device_id, data["level"])

            self.send_rep_ack(status, reason, command_id, device_name) ;

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