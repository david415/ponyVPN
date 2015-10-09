# import stuct
import struct

from zope.interface import implementer
from twisted.internet import interfaces
from twisted.protocols.basic import Int16StringReceiver
from twisted.internet.protocol import Protocol, Factory
from twisted.python import log
from scapy.all import IPv6, hexdump
from struct import unpack

from buffer import Buffer


IPV6_HEADER_LEN = 40
MAX_FRAME_LEN = 65580

class PersistentSingletonFactory(Factory):
    def __init__(self, protocol):
        print "PersistentSingletonFactory __init__"
        self.protocol = protocol

    def buildProtocol(self, addr):
        print "PersistentSingletonFactory buildProtocol addr %s" % (addr,)
        p = PersistentProtocol(self.protocol)
        return p


class PersistentProtocol(Protocol):
    def __init__(self, target_protocol):
        self.target_protocol = target_protocol

    def logPrefix(self):
        return 'PersistentProtocol'

    def dataReceived(self, data):
        print "PersistentProtocol dataReceived"
        print(self.target_protocol)

        # Forward data from hidden service to TcpFrameProducer.dataReceived()
        # to deframe the data
        self.target_protocol.dataReceived(data)

    def connectionLost(self, reason):
        print "connectionLost %r" % (reason,)

@implementer(interfaces.IPushProducer)
class TcpFrameProducer(Protocol, object):
    def __init__(self, local_addr, consumer=None):
        super(TcpFrameProducer, self).__init__()
        print "TcpFrameProducer init"
        self.local_addr = local_addr
        self.consumer = consumer

        self.frag_buffer = Buffer()
        self.frag_target_size = -1

    def dataReceived(self, data):
        packet = None
        if self.frag_buffer:
            if len(data) < self.frag_target_size:
                self.frag_buffer.write(data)
                self.frag_target_size = self.frag_target_size - len(data)
            elif len(data) == self.frag_target_size:
                self.filter_send(self.frag_buffer.drain() + data)
                self.frag_target_size = -1
            else: # len(data) > self.frag_target_size
                self.filter_send(self.frag_buffer.drain() + data[:self.frag_target_size])
                self.frag_buffer.write(data[self.frag_target_size:])
                ip_payload_len = unpack('!H', data[self.frag_target_size:])
                print "unpacked ipv6 payload len %r" % (ip_payload_len,)
                if ip_payload_len > MAX_FRAME_SIZE - IPV6_HEADER_LEN:
                    print "max frame size exceeded in overlap read op"
                    print "dropping data..."
                    self.frag_buffer.drain()
                    self.frag_target_size = -1
                else:
                    self.frag_target_size = ip_payload_len + IPV6_HEADER_LEN
        else:
            ip_payload_len = unpack('!H', data[4:6]) # IPv6 header field for payload len
            if ip_payload_len > MAX_FRAME_SIZE - IPV6_HEADER_LEN:
                print "max frame size exceeded in read op"
                print "dropping data..."
                return
            print "unpacked ipv6 payload len %r" % (ip_payload_len,)
            self.current_frag_len = IPV6_HEADER_LEN + ip_payload_len
            if len(data) < self.current_frag_len:
                self.frag_buffer.write(data)
                self.frag_target_size = self.current_frag_len - len(data)
            elif len(data) == self.current_frag_len:
                self.filter_send(packet)
            else: # len(data) > self.current_frag_len
                ip_payload_len = unpack('!H', data[4:6])
                self.filter_send(data[:ip_payload_len + IPV6_HEADER_LEN])
                self.frag_buffer.write(data[ip_payload_len + IPV6_HEADER_LEN:])

    def filter_send(self, packet):
        # assert that it's an IPv6 packet
        try:
            print "valid IPv6 packet"
            ipv6_packet = IPv6(packet)
        except struct.error:
            print "not an IPv6 packet"
            log.msg("not sending IPv6 packet")
            return # not-send non-ipv6 packets

        # assert that the destination IPv6 address matches our address
        if ipv6_packet.dst != self.local_addr:
            log.msg("packet destination doesn't match our vpn destination")

        # write the IPv6 packet to our consumer
        print "writing to consumer now"
        self.consumer.write(packet)

    def logPrefix(self):
        return 'OnionProducer'

    # IPushProducer
    def pauseProducing(self):
        print "pauseProducing"

    def resumeProducing(self):
        print "resumeProducing"

    def stopProducing(self):
        print "stopProducing"
