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
import os
from flask_wtf import Form
from wtforms import StringField
from flask import request, flash
try:
    from flask.ext.babel import gettext, ngettext
except ImportError:
    from flask_babel import gettext, ngettext

    pass

### package specific functions

def get_token_link(product_id , product_secret, access_token_cache_file):
    napi = nest.Nest(client_id=product_id, client_secret=product_secret, access_token_cache_file=access_token_cache_file)
    login_url = napi.authorize_url
    login_url = unicode(login_url, 'utf-8')
    return login_url

def generate_token_file(authorization_code, product_id , product_secret, access_token_cache_file):
    napi = nest.Nest(client_id=product_id, client_secret=product_secret, access_token_cache_file=access_token_cache_file)
    napi.request_token(authorization_code)
    if napi.invalid_access_token is True:
        flash(gettext(u"Error while getting token from Nest code, check you products id/secret Pin code"),
              "error")
    else:
        flash(gettext(u"Successfully generate token. Please restart the plugin."), "success")

def get_info_from_log(cmd):
    print("Command = %s" % cmd)
    errorlog = subprocess.Popen([cmd], stdout=subprocess.PIPE)
    output = errorlog.communicate()[0]
    if isinstance(output, str):
        output = unicode(output, 'utf-8')
    return output

def get_device_list(product_id , product_secret, access_token_cache_file):
    napi = nest.Nest(client_id=product_id, client_secret=product_secret, access_token_cache_file=access_token_cache_file)
#    try:
    return_value = ""
    for structure in napi.structures:
        return_value =  return_value + "Nest.Home name: " + " " + str(structure.name) + "\n"
        for ProtectDevice in structure.smoke_co_alarms:
            return_value = return_value + "Nest.Protect name: " + " " + str(ProtectDevice.where) + " " + str(ProtectDevice.serial) + "\n"
        for thermostat in structure.thermostats:
            return_value = return_value + "Nest.Thermostat name: " + " " + str(thermostat.where) + " " + str(thermostat.serial) + "\n"
        for camera in structure.cameras:
            return_value = return_value + "Nest.Camera name: " + " " + str(camera.where) + " " + str(camera.serial) + "\n"
    return return_value
#    except:
#	return unicode("ERROR getting Nest information!\nCheck your configuration.\nOr wait some time if you do too much request in little time.", 'utf-8')

def get_device(product_id , product_secret, access_token_cache_file):
    napi = nest.Nest(client_id=product_id, client_secret=product_secret, access_token_cache_file=access_token_cache_file)
#    try:
    return_value = []
    for structure in napi.structures:
        return_value.append({'type':'nest.home','where':str(structure.name),'serial':str(structure.name),'device_name':str(structure.name)})
        for ProtectDevice in structure.smoke_co_alarms:
            return_value.append({'type':'nest.protect','where':str(ProtectDevice.where),'serial':str(ProtectDevice.serial)})
        for thermostat in structure.thermostats:
            return_value.append({'type':'nest.thermostat','where':str(thermostat.where),'serial':str(thermostat.serial)})
        for camera in structure.cameras:
            return_value.append({'type':'nest.camera','where':str(camera.where),'serial':str(camera.serial)})
    return return_value
#    except:
#	return unicode("ERROR getting Nest information\nCheck your configuration", 'utf-8')

class CodeForm(Form):
    code = StringField("code")

### common tasks
package = "plugin_nestdevice"
template_dir = "{0}/{1}/admin/templates".format(get_packages_directory(), package)
static_dir = "{0}/{1}/admin/static".format(get_packages_directory(), package)
geterrorlogcmd = "{0}/{1}/admin/geterrorlog.sh".format(get_packages_directory(), package)

# TODO
# access_token_cache_file = os.path.join(get_data_files_directory_for_plugin("nestdevice"), nest.json)
access_token_cache_file = os.path.join(os.path.dirname(__file__), '../data/nest.json')

plugin_nestdevice_adm = Blueprint(package, __name__,
                        template_folder = template_dir,
                        static_folder = static_dir)


@plugin_nestdevice_adm.route('/<client_id>', methods=['GET', 'POST'])
def index(client_id):
    detail = get_client_detail(client_id)
    form = CodeForm()
    product_id = str(detail['data']['configuration'][1]['value'])
    product_secret = str(detail['data']['configuration'][2]['value'])

    if request.method == "POST":
        generate_token_file(form.code.data, product_id, product_secret, access_token_cache_file)
    try:
        return render_template('plugin_nestdevice.html',
            clientid = client_id,
            client_detail = detail,
            mactive="clients",
            active = 'advanced',
	    get_token_url=get_token_link(product_id, product_secret, access_token_cache_file),
	    form=form,
            device_list = get_device_list(product_id, product_secret, access_token_cache_file),
            devices = get_device(product_id, product_secret, access_token_cache_file),
            errorlog = get_info_from_log(geterrorlogcmd))

    except TemplateNotFound:
        abort(404)

