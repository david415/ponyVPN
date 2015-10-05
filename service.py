#!/usr/bin/env python

import pytun
from twisted.internet import reactor
from twisted.application import service
from twisted.pair.tuntap import TuntapPort

from tun_protocol import TunProducerConsumer
from onion_readerwriter import OnionProducer



class OnionVPNService(service.Service):

    def __init__(self, tun_name, tor_control_port, onion_key_file):
        # XXX should accept a tor_control_address argument
        self.tun_name = tun_name
        self.tor_control_port = tor_control_port
        self.onion_key_file = onion_key_file

    def startService(self):
        tun_protocol = TunProducerConsumer()
        onion_producer_protocol = OnionProducer(consumer = tun_protocol)
        ipv6_onion_consumer = IPv6OnionConsumer()
        tun_protocol.setConsumer(ipv6_onion_consumer)
        onion_endpoint = serverFromString("onion:80:controlPort=%s:hiddenServiceKeyFile=%s" % (self.tor_control_port, self.onion_key_file))
        d = onion_endpoint.listen(onion_producer_protocol)
        d.addCallback()

        tun = TuntapPort(self.tun_name, tun_protocol, reactor=reactor)
        tun.startListening()

    def stopService(self):
        pass