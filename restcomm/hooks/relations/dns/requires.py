from charmhelpers.core import hookenv

from charms.reactive import hook
from charms.reactive import RelationBase
from charms.reactive import scopes

class DnsRequires(RelationBase):
    scope = scopes.UNIT

    @hook('{requires:dns}-relation-joined')
    def joined(self):
        conv = self.conversation()
        conv.set_state('{relation_name}.connected')

    @hook('{requires:dns}-relation-changed')
    def changed(self):
        conv = self.conversation()
        conv.set_state('{relation_name}.available')

    @hook('{requires:dns}-relation-departed')
    def departed(self):
        conv = self.conversation()
        conv.remove_state('{relation_name}.available')
        conv.remove_state('{relation_name}.connected')
        conv.set_state('{relation_name}.removing')

    @hook('{requires:dns}-relation-broken')
    def broken(self):
        conv = self.conversation()
        conv.remove_state('{relation_name}.connected')
        conv.remove_state('{relation_name}.available')
        conv.remove_state('{relation_name}.removing')

    def services(self):
        for conv in self.conversations():
            yield {'ip': conv.get_remote('private-address'),
                   'port': conv.get_remote('port', 53)}

    def configure(self, domain, alias):
        relation_info = {
            'addr': hookenv.unit_get('private-address'),
            'domain': domain,
            'alias': alias,
            'rr': 'A',
        }
        self.set_remote(**relation_info)