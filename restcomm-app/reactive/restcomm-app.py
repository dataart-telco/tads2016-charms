import shutil
import zipfile
import os

from subprocess import call, check_call

from charmhelpers.core import hookenv
from charmhelpers.core import unitdata

from charms import reactive
from charms.reactive import hook
from charms.reactive import when, when_not, when_any

rvdWorkspace = '/opt/restcomm-rvd-workspace/'

db = unitdata.kv()
config = hookenv.config()

@hook('install')
def install_app():
    check_call(['pip', 'install', 'requests'])
    host = hookenv.unit_private_ip()
    port = 8080
    user = config.get('user')
    pswd = config.get('password')

    appId = create_app(user, pswd, host, port, hookenv.service_name())
    copy_project(appId)

def create_app(user, pswd, host, port, appName):
    import requests
    app = {
        'FriendlyName': appName,
        'ApiVersion': '2012-04-24',
        'HasVoiceCallerIdLookup': 'false',
        'Kind': 'voice'
    }
    r = requests.post(
        "http://{}:{}@{}:{}/restcomm/2012-04-24/Accounts/{}/Applications.json".format(user, pswd, host, port, user), 
        data=app
    )
    r.raise_for_status()
    appObj = r.json()
    appId = appObj['sid']
    app = {
        'RcmlUrl': 'http://{}:{}/restcomm-rvd/services/apps/{}/controller'.format(host, port, appId)
    }
    r = requests.post(
        "http://{}:{}@{}:{}/restcomm/2012-04-24/Accounts/{}/Applications/{}.json".format(user, pswd, host, port, user, appId), 
        data=app
    )
    r.raise_for_status()
    return appId

def copy_project(appId):
    zip = zipfile.ZipFile('files/project.zip')
    zip.extractall(os.path.join(rvdWorkspace, appId))