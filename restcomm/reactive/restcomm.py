import shutil

from subprocess import call, check_call

from charmhelpers.core import hookenv
from charmhelpers.core import unitdata
from charmhelpers.core import host

from charms import reactive
from charms.reactive import hook
from charms.reactive import helpers
from charms.reactive import when, when_not, when_any

db = unitdata.kv()
config = hookenv.config()

app_name = 'restcomm'
docker_image = 'restcomm/restcomm:7.9.0'

@when('docker.available')
@when_not('app.available')
def install_restcomm():
    hookenv.status_set('maintenance', 'Pulling Restcomm-Connect')
    check_call(['docker', 'pull', docker_image])

    # open ports: HTTP, SIP, RTP
    hookenv.open_port(8080, 'TCP')
    hookenv.open_port(5080, 'UDP')
    hookenv.open_port('65000-65535', 'UDP')

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
def restart_restcomm():
    remove_container()
    start_restcomm()

@when('app.available')
@when_not('app.started', 'app.destroyed')
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
        outboundProxy = "{}:{}".format(config.get('zone'), proxy['port'])
        check_call(["echo", "'{} {}'".format(proxy['host'], config.get('zone')), " >> ", "/etc/hosts"])

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

#   '-e', 'ENVCONFURL={}'.format(configUrl),
    run_command = [
        'docker',
        'run',
        '--restart', 'always',
        '--name', app_name,
        '--net', 'host',
        '-e', 'STATIC_ADDRESS={}'.format(hookenv.unit_private_ip()),
        '-e', 'MEDIASERVER_EXTERNAL_ADDRESS={}'.format(hookenv.unit_public_ip()),
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
        '-e', 'MEDIASERVER_LOWEST_PORT={}'.format('65000'),
        '-e', 'MEDIASERVER_HIGHEST_PORT={}'.format('65535'),
        '-e', 'LOG_LEVEL={}'.format('DEBUG'),
        '-e', 'RESTCOMM_LOGS={}'.format('/var/log/restcomm'),
        '-e', 'CORE_LOGS_LOCATION={}'.format('restcomm_core'),
        '-e', 'RESTCOMM_TRACE_LOG={}'.format('restcomm_trace'),
        '-e', 'RVD_LOCATION={}'.format('/opt/restcomm-rvd-workspace'),
        '-v', '{}:{}'.format('/var/log/restcomm/', '/var/log/restcomm/'),
        '-v', '{}:{}'.format('/opt/restcomm-rvd-workspace/', '/opt/restcomm-rvd-workspace/'),
        '-d',
        docker_image
    ]
    check_call(run_command)

    hookenv.status_set('active', 'Restcomm-Connect is started')
    reactive.remove_state('app.changed')
    reactive.set_state('app.started')

@hook('config-changed')
def config_changed():
    reactive.set_state('app.changed')

def save_and_notify(relation, data):
    if helpers.is_state('app.started') and not helpers.data_changed(relation, data):
        return
    db.set(relation, data)
    reactive.set_state('app.changed')

@when('api.available')
def configure_api(api):
    api.configure(port=8080)

@when('sip.available')
def configure_api(api):
    api.configure(port=5080)

@when('mysql.available')
def mysql_changed(mysql):
    if not mysql:
        return
    save_and_notify("mysql", 
        {
        'host': mysql.host(), 
        'database': mysql.database(), 
        'user': mysql.user(), 
        'password': mysql.password()
    })

@when('dns.connected')
@when_not('dns.available')
def dns_joined(dns):
    dns.configure(config.get('zone'), hookenv.service_name())

@when('dns.available')
def dns_changed(dns):
    if not dns:
        return
    for service in dns.services():
        record = "AUTO GENERATED\n"
        record += "nameserver\t{}\n".format(service['ip'])
        host.write_file("/etc/resolvconf/resolv.conf.d/head", bytes(record, 'UTF-8'))
        check_call(["resolvconf", "-u"])
        break

@when('dns.removing')
def dns_disconnected(dns):
    reactive.remove_state('dns.removing')
    dns.configure(config.get('zone'), hookenv.service_name())
    record = "AUTO GENERATED\n"
    host.write_file("/etc/resolvconf/resolv.conf.d/head", bytes(record, 'UTF-8'))

@hook('loadbalancer-relation-changed')
def loadbalancer_changed():
    pass
#    lbnode = hookenv.relation_get()
#    if lbnode:
#        db.set("loadbalancer", {'public': lbnode['host'], 'private': lbnode['private-address']})
#        reactive.set_state('app.changed')

@hook('outbound-proxy-relation-changed')
def outbound_proxy_changed(proxy):
    if not proxy:
        return
    for service in proxy.services():
        save_and_notify("outbound-proxy", {'host': service['host'], 'port': service['port']})
        break