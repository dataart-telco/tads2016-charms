import shutil

from subprocess import call, check_call

from charmhelpers.core import hookenv
from charmhelpers.core import unitdata

from charms import reactive
from charms.reactive import hook
from charms.reactive import helpers
from charms.reactive import when, when_not, when_any

db = unitdata.kv()
config = hookenv.config()

app_name = 'call-blocker'
docker_image = 'tads2015da/call-blocker:latest'

@when('docker.available')
@when_not('app.available')
def install_app():
    hookenv.status_set('maintenance', 'Pulling application')
    check_call(['docker', 'pull', docker_image])

    # open ports: HTTP
    hookenv.open_port(7070, 'TCP')

    reactive.set_state('app.available')

@hook('stop')
def destroy_app():
    reactive.set_state('app.destroyed')
    remove_container()

def remove_container():
    try:
        check_call(['docker', 'kill', app_name])
    except:
        pass
    try:
        check_call(['docker', 'rm', '-f', app_name])
    except:
        pass
    reactive.remove_state('app.started')

@when('app.changed')
def restart_app():
    remove_container()
    start_app()

@when('app.available')
@when_not('app.started', 'app.destroyed')
def start_app():
    hookenv.status_set('maintenance', 'Start call-blocker')

    host = hookenv.unit_private_ip()
    port = 8080

    registration_host = host
    registration_port = 8080

    user = config.get('user')
    password = config.get('password')
    restcommApp = config.get('restcomm-app')
    clientAppendix = config.get('client-appendix')
    apiKey = config.get('api-key')

    restcomm = db.get('restcomm', record=True)
    if not restcomm:
        hookenv.status_set('blocked', 'Wait for restcomm server connection')
        return
    else:
        host = restcomm['host']
        port = restcomm['port']

    registration = db.get('registration', record=True)
    hookenv.log("!!! registration data is {}".format(registration))
    if registration:
        registration_host = registration['host']
        registration_port = registration['port']
    else:
        registration_host = host
        registration_port = port

    run_command = [
        'docker',
        'run',
        '--restart', 'always',
        '--name', app_name,
        '-e', 'RESTCOMM_SERVER={}:{}'.format(host, port),
        '-e', 'RESTCOMM_LOGIN={}'.format(user),
        '-e', 'RESTCOMM_PASSWORD={}'.format(password),
        '-e', 'APPLICATION_NAME={}'.format(restcommApp),
        '-e', 'CLIENT_APPENDIX={}'.format(clientAppendix),
        '-e', 'API_KEY={}'.format(apiKey),
        '-e', 'REGISTRATION_API_ENDPOINT={}:{}'.format(registration_host, registration_port),
        '-e', 'REGISTRATION_API_KEY={}'.format(config.get('registration-key')),
        '-v', '{}:{}'.format('/opt/scenario1-call-blocker/data/', '/opt/scenario1/data/'),
        '-p', '7070:8080',
        '-d',
        docker_image
    ]
    check_call(run_command)

    hookenv.status_set('active', 'App is started')
    reactive.remove_state('app.changed')
    reactive.set_state('app.started')

@hook('config-changed')
def config_changed():
    reactive.set_state('app.changed')

def save_and_notify(relation, data):
    if helpers.is_state('app.started') and not helpers.data_changed(relation, data):
        hookenv.log("!!! data IS NOT changed for {} {}".format(relation, data))
        return
    db.set(relation, data)
    hookenv.log("!!! data saved for {} {}".format(relation, data))
    reactive.set_state('app.changed')

def get_first_http_service(http):
    service = http.services()
    if len(service) == 0:
        return None
    http = service[0]
    hosts = http['hosts']
    if len(hosts) == 0:
        return None
    return hosts[0]

def api_relation_changed(relation, api):
    api = get_first_http_service(api)
    if not api:
        return
    save_and_notify(relation, {'host': api['hostname'], 'port': api['port']})

@when('restcomm.available')
def configure_api(api):
    api_relation_changed('restcomm', api)

@when('registration.available')
def configure_api(api):
    api_relation_changed('registration', api)