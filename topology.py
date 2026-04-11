from mininet.topo import Topo

class BroadcastTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1')

        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)

topos = {'broadcasttopo': (lambda: BroadcastTopo())}
