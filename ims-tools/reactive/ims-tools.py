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
    check_call(['docker', 'pull', 'tads2015da/ims-tools-server:latest'])

    # open ports: HTTP
    hookenv.open_port(7071, 'TCP')

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

    realm = config.get('realm')
    apiKey = config.get('api-key')

    restcomm = db.get('restcomm', record=True)
    if not restcomm:
        hookenv.status_set('blocked', 'Wait for restcomm connection')
        return

    restcomm_host = restcomm['host']
    restcomm_port = restcomm['port']

    homstead = db.get('homestead', record=True)
    if not homstead:
        hookenv.status_set('blocked', 'Wait for homestead connection')
        return

    homestead_host = homstead['host']
    homestead_port = homstead['port']


    run_command = [
        'docker',
        'run',
        '--restart', 'always',
        '--name', 'call-blocker',
        '-e', 'HOSMESTEAD_URL=http://{}:{}'.format(homestead_host, 8889),
        '-e', 'REALM={}'.format(realm),
        '-e', 'RESTCOMM_HOST={}:{}'.format(restcomm_host, restcomm_port),
        '-e', 'API_KEY={}'.format(apiKey),
        '-p', '7071:5000',
        '-d',
        'tads2015da/ims-tools-server:latest'
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

@when('restcomm.available')
def configure_restcomm(restcomm):
    restcomm = get_first_http_service(restcomm)
    if not  restcomm:
        return
    db.set("restcomm", {'host': restcomm['hostname'], 'port': restcomm['port']})
    reactive.set_state('app.changed')

@hook('homestead-relation-changed')
def configure_homestead(homestead):
    if not homestead:
        return
    for service in homestead.services():
        db.set("homestead", {'host': service['host'], 'port': service['port']})
        break
    reactive.set_state('app.changed')