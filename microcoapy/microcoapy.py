import usocket as socket
import uos
import utime as time
import microcoapy.coap_macros as macros
from microcoapy.coap_packet import CoapPacket

from microcoapy.coap_reader import parsePacketHeaderInfo
from microcoapy.coap_reader import parsePacketOptionsAndPayload
from microcoapy.coap_writer import writePacketHeaderInfo
from microcoapy.coap_writer import writePacketOptions
from microcoapy.coap_writer import writePacketPayload

class Coap:
    def __init__(self):
        self.sock = None
        self.callbacks = {}
        self.resposeCallback = None
        self.port = 0

    # Create and initialize a new UDP socket to listen to.
    # port: the local port to be used.
    def start(self, port=macros._COAP_DEFAULT_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', port))

    # Stop and destroy the socket that has been created by
    # a previous call of 'start' function
    def stop(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    # Set a custom instance of a UDP socket
    # Is used instead of calling start/stop functions.
    #
    # Note: This overrides the automatic socket that has been created
    # by the 'start' function.
    # The custom socket must support functions:
    # * socket.sendto(bytes, address)
    # * socket.recvfrom(bufsize)
    # * socket.setblocking(flag)
    def setCustomSocket(self, custom_socket):
        self.stop()
        self.sock = custom_socket

    def addIncomingRequestCallback(self, requestUrl, callback):
        self.callbacks[requestUrl] = callback

    def sendPacket(self, ip, port, coapPacket):
        if coapPacket.content_format != macros.COAP_CONTENT_FORMAT.COAP_NONE:
            optionBuffer = bytearray(2)
            optionBuffer[0] = (coapPacket.content_format & 0xFF00) >> 8
            optionBuffer[1] = (coapPacket.content_format & 0x00FF)
            coapPacket.addOption(macros.COAP_OPTION_NUMBER.COAP_CONTENT_FORMAT, optionBuffer)

        if (coapPacket.query is not None) and (len(coapPacket.query) > 0):
            coapPacket.addOption(macros.COAP_OPTION_NUMBER.COAP_URI_QUERY, coapPacket.query)

        buffer = bytearray()
        writePacketHeaderInfo(buffer, coapPacket)

        writePacketOptions(buffer, coapPacket)

        writePacketPayload(buffer, coapPacket)

        status = 0
        try:
            sockaddr = socket.getaddrinfo(ip, port)[0][-1]
            status = self.sock.sendto(buffer, sockaddr)
            if status > 0:
                status = coapPacket.messageid
            print('Packet sent. Token: ', status)
        except Exception as e:
            status = 0
            print('Exception while sending packet...')
            import sys
            sys.print_exception(e)

        return status

    def send(self, ip, port, url, type, method, token, payload, content_format, query_option):
        packet = CoapPacket()
        packet.type = type
        packet.method = method
        packet.token = token
        packet.payload = payload
        packet.content_format = content_format
        packet.query = query_option

        return self.sendEx(ip, port, url, packet)

    def sendEx(self, ip, port, url, packet):
        # messageId field: 16bit -> 0-65535
        # urandom to generate 2 bytes
        randBytes = uos.urandom(2)
        packet.messageid = (randBytes[0] << 8) | randBytes[1]
        packet.setUriHost(ip)
        packet.setUriPath(url)

        return self.sendPacket(ip, port, packet)

    # to be tested
    def sendResponse(self, ip, port, messageid, payload, method, content_format, token):
        packet = CoapPacket()

        packet.type = macros.COAP_TYPE.COAP_ACK
        packet.method = method
        packet.token = token
        packet.payload = payload
        packet.messageid = messageid
        packet.content_format = content_format

        return self.sendPacket(ip, port, packet)

    def get(self, ip, port, url, token=bytearray()):
        return self.send(ip, port, url, macros.COAP_TYPE.COAP_CON, macros.COAP_METHOD.COAP_GET, token, None, macros.COAP_CONTENT_FORMAT.COAP_NONE, None)

    def put(self, ip, port, url, payload=bytearray(), query_option=None, content_format=macros.COAP_CONTENT_FORMAT.COAP_NONE, token=bytearray()):
        return self.send(ip, port, url, macros.COAP_TYPE.COAP_CON, macros.COAP_METHOD.COAP_PUT, token, payload, content_format, query_option)

    def post(self, ip, port, url, payload=bytearray(), query_option=None, content_format=macros.COAP_CONTENT_FORMAT.COAP_NONE, token=bytearray()):
        return self.send(ip, port, url, macros.COAP_TYPE.COAP_CON, macros.COAP_METHOD.COAP_POST, token, payload, content_format, query_option)

    def handleIncomingRequest(self, requestPacket, sourceIp, sourcePort):
        url = ""
        for opt in requestPacket.options:
            if (opt.number == macros.COAP_OPTION_NUMBER.COAP_URI_PATH) and (len(opt.buffer) > 0):
                if url != "":
                    url += "/"
                url += opt.buffer.decode('unicode_escape')

        urlCallback = None
        if url != "":
            urlCallback = self.callbacks.get(url)

        if urlCallback is None:
            print('Callback for url [', url, "] not found")
            self.sendResponse(sourceIp, sourcePort, requestPacket.messageid,
                              None, macros.COAP_RESPONSE_CODE.COAP_NOT_FOUND,
                              macros.COAP_CONTENT_FORMAT.COAP_NONE, None)
        else:
            urlCallback(requestPacket, sourceIp, sourcePort)

    def readBytesFromSocket(self, numOfBytes):
        try:
            return self.sock.recvfrom(numOfBytes)
        except Exception:
            return (None, None)

    def parsePacketToken(self, buffer, packet):
        if (packet.tokenLength == 0):
            packet.token = None
        elif (packet.tokenLength <= 8):
            packet.token = buffer[4:4+packet.tokenLength]
        else:
            (tempBuffer, tempRemoteAddress) = self.readBytesFromSocket(macros._BUF_MAX_SIZE - bufferLen)
            if tempBuffer is not None:
                buffer.extend(tempBuffer)
            return False
        return True

    def loop(self, blocking=True):
        if self.sock is None:
            return False

        self.sock.setblocking(blocking)
        (buffer, remoteAddress) = self.readBytesFromSocket(macros._BUF_MAX_SIZE)
        self.sock.setblocking(True)

        while (buffer is not None) and (len(buffer) > 0):
            bufferLen = len(buffer)
            if (bufferLen < macros._COAP_HEADER_SIZE) or (((buffer[0] & 0xC0) >> 6) != 1):
                (tempBuffer, tempRemoteAddress) = self.readBytesFromSocket(macros._BUF_MAX_SIZE - bufferLen)
                if tempBuffer is not None:
                    buffer.extend(tempBuffer)
                continue

            packet = CoapPacket()

            parsePacketHeaderInfo(buffer, packet)

            if not self.parsePacketToken(buffer, packet):
                continue

            if not parsePacketOptionsAndPayload(buffer, packet):
                return False

            if packet.type == macros.COAP_TYPE.COAP_ACK or\
               packet.method == macros.COAP_RESPONSE_CODE.COAP_NOT_FOUND:
                if self.resposeCallback is not None:
                    self.resposeCallback(packet, remoteAddress)
            else:
                self.handleIncomingRequest(packet, remoteAddress[0], remoteAddress[1])
            return True

        return False

    def poll(self, timeoutMs=-1, pollPeriodMs=500):
        start_time = time.ticks_ms()
        while not self.loop(False) and (time.ticks_diff(time.ticks_ms(), start_time) < timeoutMs):
            time.sleep_ms(pollPeriodMs)
