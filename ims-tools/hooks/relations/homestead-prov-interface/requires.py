from charms.reactive import hook
from charms.reactive import RelationBase
from charms.reactive import scopes

class HomesteadProvInterfaceRequires(RelationBase):
    scope = scopes.UNIT

    @hook('{requires:homestead-prov-interface}-relation-{joined,changed}')
    def changed(self):
        conv = self.conversation()
        conv.set_state('{relation_name}.connected')
        if conv.get_remote('port', 8889):
            conv.set_state('{relation_name}.available')

    @hook('{requires:homestead-prov-interface}-relation-{departed,broken}')
    def broken(self):
        conv = self.conversation()
        conv.remove_state('{relation_name}.connected')
        conv.remove_state('{relation_name}.available')

    def services(self):
        for conv in self.conversations():
            yield {'host': conv.get_remote('private-address'),
                   'port': conv.get_remote('port', 8889)}