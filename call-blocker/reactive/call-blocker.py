import shutil

from subprocess import call, check_call

from charmhelpers.core import hookenv
from charmhelpers.core import unitdata

from charms import reactive
from charms.reactive import hook
from charms.reactive import when, when_not, when_any

db = unitdata.kv()
config = hookenv.config()

@when('docker.available')
@when_not('app.available')
def install_app():
    hookenv.status_set('maintenance', 'Pulling application')
    check_call(['docker', 'pull', 'tads2015da/call-blocker:latest'])

    # open ports: HTTP
    hookenv.open_port(7070, 'TCP')

    reactive.set_state('app.available')

def remove_container():
    run_command = [
        'docker',
        'rm', '-f',
        'call-blocker'
    ]
    call(run_command)
    reactive.remove_state('app.started')

@when('app.changed')
def restart_app():
    remove_container()
    start_app()

@when('app.available')
@when_not('app.started')
def start_app():
    hookenv.status_set('maintenance', 'Start call-blocker')

    host = hookenv.unit_private_ip()
    port = 8080
    user = config.get('user')
    password = config.get('password')
    restcommApp = config.get('restcomm-app')
    clientAppendix = config.get('client-appendix')
    apiKey = config.get('api-key')

    api = db.get('api', record=True)
    if not api:
        hookenv.status_set('blocked', 'Wait for api server connection')
        return
    else:
        host = api['host']
        port = api['port']

    run_command = [
        'docker',
        'run',
        '--restart', 'always',
        '--name', 'call-blocker',
        '-e', 'RESTCOMM_SERVER={}:{}'.format(host, port),
        '-e', 'RESTCOMM_LOGIN={}'.format(user),
        '-e', 'RESTCOMM_PASSWORD={}'.format(password),
        '-e', 'CLIENT_APP={}'.format(restcommApp),
        '-e', 'CLIENT_POSTFIX={}'.format(clientAppendix),
        '-e', 'API_KEY={}'.format(apiKey),
        '-v', '{}:{}'.format('/opt/scenario1-call-blocker/data/', '/opt/scenario1/data/'),
        '-p', '7070:8080',
        '-d',
        'tads2015da/call-blocker:latest'
    ]
    check_call(run_command)

    hookenv.status_set('active', 'App is started')
    reactive.set_state('app.started')

@hook('config-changed')
def config_changed():
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

@when('api.available')
def configure_api(api):
    api = get_first_http_service(api)
    if not api:
        return
    db.set("api", {'host': api['hostname'], 'port': api['port']})
    reactive.set_state('app.changed')
