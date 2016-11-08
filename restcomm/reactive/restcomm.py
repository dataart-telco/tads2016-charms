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
@when_not('restcomm.available')
def install_restcomm():
    hookenv.status_set('maintenance', 'Pulling Restcomm-Connect')
    check_call(['docker', 'pull', 'restcomm/restcomm:stable'])

    # open ports: HTTP, SIP, RTP
    hookenv.open_port(8080, 'TCP')
    hookenv.open_port(5080, 'UDP')
    hookenv.open_port('65000-65535', 'UDP')

    reactive.set_state('restcomm.available')

def remove_container():
    run_command = [
        'docker',
        'rm', '-f',
        'restcomm'
    ]
    call(run_command)
    reactive.remove_state('restcomm.started')

@when('restcomm.changed')
def restart_restcomm():
    remove_container()
    start_restcomm()

@when('restcomm.available')
@when_not('restcomm.started')
def start_restcomm():
    hookenv.status_set('maintenance', 'Start Restcomm-Connect')

    adminPassword = config.get('init_password')
    voiceRssKey = config.get('voicerss_key')
    configUrl = config.get('config_url')
    smsOutboundProxy = config.get('sms_outbound_proxy')

    proxy = db.get('outbound-proxy', record=True)
    if not proxy:
        outboundProxy = config.get('outbound_proxy')
    else:
        outboundProxy = "{}:{}".format(proxy['host'], proxy['port'])

    mysqlHost = ''
    mysqlSchema = ''
    mysqlUser = ''
    mysqlPswd = ''

    lbPublicIp = ''
    lbPrivateIp = ''

    mysql = db.get('mysql', record=True)
    if mysql:
        mysqlHost = mysql['host']
        mysqlSchema = mysql['database']
        mysqlUser = mysql['user']
        mysqlPswd = mysql['password']

    lb = db.get('loadbalancer', record=True)
    if lb:
        lbPublicIp = lb['public']
        lbPrivateIp = lb['private']

    run_command = [
        'docker',
        'run',
        '--restart', 'always',
        '--name', 'restcomm',
        '--net', 'host',
        '-e', 'ENVCONFURL={}'.format(configUrl),
        '-e', 'MYSQL_HOST={}'.format(mysqlHost),
        '-e', 'MYSQL_USER={}'.format(mysqlUser),
        '-e', 'MYSQL_PASSWORD={}'.format(mysqlPswd),
        '-e', 'MYSQL_SCHEMA={}'.format(mysqlSchema),
        '-e', 'OUTBOUND_PROXY={}'.format(outboundProxy),
        '-e', 'SMS_OUTBOUND_PROXY={}'.format(smsOutboundProxy),
        '-e', "INITIAL_ADMIN_PASSWORD='{}'".format(adminPassword),
        '-e', 'VOICERSS_KEY={}'.format(voiceRssKey),
        '-e', 'LB_PUBLIC_IP={}'.format(lbPublicIp),
        '-e', 'LB_INTERNAL_IP={}'.format(lbPrivateIp),
        '-e', 'MEDIASERVER_LOGS_LOCATION={}'.format('media_server'),
        '-e', 'EDIASERVER_LOWEST_PORT={}'.format('65000'),
        '-e', 'MEDIASERVER_HIGHEST_PORT={}'.format('65535'),
        '-e', 'LOG_LEVEL={}'.format('DEBUG'),
        '-e', 'RESTCOMM_LOGS={}'.format('/var/log/restcomm'),
        '-e', 'CORE_LOGS_LOCATION={}'.format('restcomm_core'),
        '-e', 'RESTCOMM_TRACE_LOG={}'.format('restcomm_trace'),
        '-e', 'RVD_LOCATION={}'.format('/opt/restcomm-rvd-workspace'),
        '-v', '{}:{}'.format('/var/log/restcomm/', '/var/log/restcomm/'),
        '-v', '{}:{}'.format('/opt/restcomm-rvd-workspace/', '/opt/restcomm-rvd-workspace/'),
        '-d',
        'restcomm/restcomm:stable'
    ]
    check_call(run_command)

    hookenv.status_set('active', 'Restcomm-Connect is started')
    reactive.set_state('restcomm.started')

@hook('config-changed')
def config_changed():
    reactive.set_state('restcomm.changed')

@when('mysql.available')
def mysql_changed(mysql):
    if not mysql:
        return
    db.set("mysql", {
        'host': mysql.host(), 
        'database': mysql.database(), 
        'user': mysql.user(), 
        'password': mysql.password()
    })
    reactive.set_state('restcomm.changed')

@when('api.available')
def configure_api(api):
    api.configure(port=8080)

@hook('loadbalancer-relation-changed')
def loadbalancer_changed():
    pass
#    lbnode = hookenv.relation_get()
#    if lbnode:
#        db.set("loadbalancer", {'public': lbnode['host'], 'private': lbnode['private-address']})
#        reactive.set_state('restcomm.changed')

@hook('outbound-proxy-relation-changed')
def outbound_proxy_changed(proxy):
    if not proxy:
        return
    for service in proxy.services():
        db.set("outbound-proxy", {'host': service['host'], 'port': service['port']})
        break
    reactive.set_state('app.changed')