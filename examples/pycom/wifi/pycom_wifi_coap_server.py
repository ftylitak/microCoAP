from network import WLAN
import machine
import microcoapy.microcoapy as microcoapy
import utime as time

wlan = WLAN(mode=WLAN.STA)

_MY_SSID = 'myssid'
_MY_PASS = 'mypass'
_SERVER_PORT = 5683  # default CoAP port


def connectToWiFi():
    print('Starting attempt to connect to WiFi...')
    nets = wlan.scan()
    for net in nets:
        if net.ssid == _MY_SSID:
            print('Network found!')
            wlan.connect(net.ssid, auth=(net.sec, _MY_PASS), timeout=5000)
            while not wlan.isconnected():
                machine.idle()  # save power while waiting

            connectionResults = wlan.ifconfig()
            print('WLAN connection succeeded with IP: ', connectionResults[0])
            break

    return wlan.isconnected()

connectToWiFi()

def turnOnLed(packet, senderIp, senderPort):
    print('Turn-on-led request received:', packet, ', from: ', senderIp, ":", senderPort)
    client.sendResponse(senderIp, senderPort, packet.messageid,
                      "ok", microcoapy.COAP_RESPONSE_CODE.COAP_CONTENT,
                      microcoapy.COAP_CONTENT_FORMAT.COAP_NONE, packet.token)


def measureCurrent(packet, senderIp, senderPort):
    print('Measure-current request received:', packet, ', from: ', senderIp, ":", senderPort)
    client.sendResponse(senderIp, senderPort, packet.messageid,
                      None, microcoapy.COAP_RESPONSE_CODE.COAP_SERVICE_UNAVALIABLE,
                      microcoapy.COAP_CONTENT_FORMAT.COAP_NONE, packet.token)

client = microcoapy.Coap()
# setup callback for incoming response to a request
client.addIncomingRequestCallback('led/turnOn', turnOnLed)
client.addIncomingRequestCallback('current/measure', measureCurrent)

# Starting CoAP...
client.start()

# wait for incoming request for 60 seconds
timeoutMs = 60000
start_time = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start_time) < timeoutMs:
    client.poll(60000)

# stop CoAP
client.stop()
