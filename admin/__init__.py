# -*- coding: utf-8 -*-

### common imports
from flask import Blueprint, abort
from domogik.common.utils import get_packages_directory
from domogik.admin.application import render_template
from domogik.admin.views.clients import get_client_detail
from jinja2 import TemplateNotFound
import ow
import traceback
import sys

### package specific imports
import subprocess
import nest
import locale
import time
import json


### package specific functions

def get_info_from_log(cmd):
    print("Command = %s" % cmd)
    errorlog = subprocess.Popen([cmd], stdout=subprocess.PIPE)
    output = errorlog.communicate()[0]
    if isinstance(output, str):
        output = unicode(output, 'utf-8')
    return output

def get_device_list(product_id , product_secret, access_token_cache_file):
    napi = nest.Nest(client_id=product_id, client_secret=product_secret, access_token_cache_file=access_token_cache_file)
    try:
	return_value = ""
	for structure in napi.structures:
	    return_value =  return_value + "Nest.Home name: " + " " + str(structure.name) + "\n"
            for ProtectDevice in structure.protectdevices:
		return_value = return_value + "Nest.Protect serial: " + " " + str(ProtectDevice.where) + " " + str(ProtectDevice.serial) + "\n"
            for device in structure.devices:
	        return_value = return_value + "Nest.Thermostat serial: " + " " + str(device.where) + " " + str(device.name) + "\n"
        return return_value
    except:
	return unicode("ERROR getting Nest information!\nCheck your configuration.\nOr wait some time if you do too much request in little time.", 'utf-8')

def get_device(username , password):
    napi = nest.Nest(username , password)
    try:
	return_value = []
	for structure in napi.structures:
            return_value.append({'type':'nest.home','where':str(structure.name),'serial':str(structure.name)})
            for ProtectDevice in structure.protectdevices:
		return_value.append({'type':'nest.protect','where':str(ProtectDevice.where),'serial':str(ProtectDevice.serial)})
            for device in structure.devices:
		return_value.append({'type':'nest.thermostat','where':str(device.where),'serial':str(device.name)})
        return return_value
    except:
	return unicode("ERROR getting Nest information\nCheck your configuration", 'utf-8')

### common tasks
package = "plugin_nestdevice"
template_dir = "{0}/{1}/admin/templates".format(get_packages_directory(), package)
static_dir = "{0}/{1}/admin/static".format(get_packages_directory(), package)
geterrorlogcmd = "{0}/{1}/admin/geterrorlog.sh".format(get_packages_directory(), package)

plugin_nestdevice_adm = Blueprint(package, __name__,
                        template_folder = template_dir,
                        static_folder = static_dir)


@plugin_nestdevice_adm.route('/<client_id>')
def index(client_id):
    detail = get_client_detail(client_id)
    product_id = str(detail['data']['configuration'][1]['value'])
    product_secret = str(detail['data']['configuration'][2]['value'])
    access_token_cache_file = 'nest.json'
    try:
        return render_template('plugin_nestdevice.html',
            clientid = client_id,
            client_detail = detail,
            mactive="clients",
            active = 'advanced',
            device_list = get_device_list(product_id,product_secret,access_token_cache_file),
            devices = get_device(product_id,product_secret,access_token_cache_file),
            errorlog = get_info_from_log(geterrorlogcmd))

    except TemplateNotFound:
        abort(404)

