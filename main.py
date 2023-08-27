from microdot_asyncio import Microdot, send_file
from umqtt.simple import MQTTClient
from wiegand import Wiegand
from machine import SDCard, WDT
from utime import sleep
import sdcard
import machine
import time
import uasyncio
from machine import Pin, PWM
import os
gc.collect()

# Watchdog timeout set @ 60sec
wdt = WDT(timeout = 60000)

_VERSION = const('20230827')

year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

print('DL32 - MicroPython Edition')
print('Version: ' + _VERSION)
print('Current Date/Time: ' + '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(year, month, day, hour, mins, secs))

# 1.1 SD card Pins
# CD DAT3 CS 5
# CMD DI DIN MOSI 23
# CLK SCLK 18
# DAT0 D0 MISO 19

# 1.1 Pins - Uncomment if using board revision 1.1
# buzzer_pin = Pin(14, Pin.OUT)
# neopin_pin = Pin(21, Pin.OUT)
# lockRelay_pin = Pin(27, Pin.OUT)
# progButton_pin = Pin(12, Pin.IN, Pin.PULL_UP)
# exitButton_pin = Pin(32, Pin.IN, Pin.PULL_UP)
# bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
# magSensor = Pin(22, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 25
# wiegand_1 = 26
# sd = SDCard(slot=2)

# 1.1 Pins w/TinyPico adapter - Uncomment if using board revision 1.1 with tinypico adapter
buzzer_pin = Pin(14, Pin.OUT)
neopin_pin = Pin(21, Pin.OUT)
lockRelay_pin = Pin(27, Pin.OUT)
progButton_pin = Pin(4, Pin.IN, Pin.PULL_UP)
exitButton_pin = Pin(32, Pin.IN, Pin.PULL_UP)
bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
magSensor = Pin(22, Pin.IN, Pin.PULL_UP)
wiegand_0 = 25
wiegand_1 = 26
sd = SDCard(slot=2)

# 2.0 Pins - Uncomment if using S2 Mini board revision
# buzzer_pin = Pin(14, Pin.OUT)
# neopin_pin = Pin(38, Pin.OUT)
# lockRelay_pin = Pin(10, Pin.OUT)
# progButton_pin = Pin(12, Pin.IN, Pin.PULL_UP)
# exitButton_pin = Pin(13, Pin.IN, Pin.PULL_UP)
# bellButton_pin = Pin(33, Pin.IN, Pin.PULL_UP)
# magSensor = Pin(11, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 16
# wiegand_1 = 17

# 3.0 Pins - Uncomment if using S3 Wemos board revision
# buzzer_pin = Pin(16, Pin.OUT)
# neopin_pin = Pin(13, Pin.OUT)
# lockRelay_pin = Pin(2, Pin.OUT)
# progButton_pin = Pin(8, Pin.IN, Pin.PULL_UP)
# exitButton_pin = Pin(9, Pin.IN, Pin.PULL_UP)
# bellButton_pin = Pin(11, Pin.IN, Pin.PULL_UP)
# magSensor = Pin(15, Pin.IN, Pin.PULL_UP)
# wiegand_0 = 12
# wiegand_1 = 10
# sd = sdcard.SDCard(machine.SPI(1, sck=machine.Pin(5), mosi=machine.Pin(6), miso=machine.Pin(8)), machine.Pin(7))

silent_mode = False
stop_bell = False

# Try mounting SD card and list contents. Catch error.
try:
  uos.mount(sd, '/sd')
  print('SD card mounted')
  print('  ' + str(os.listdir('/sd')))
except:
  print ('No SD card present')

# Durations for each unlock type (eg: unlock for 10 seconds if unclocked via MQTT)
exitBut_dur = 5000
http_dur = 10000
key_dur = 5000
mqtt_dur = 10000
addKey_dur = 15000
add_hold_time = 2000
sd_boot_hold_time = 3000
add_mode = False
add_mode_counter = 0
add_mode_intervals = 10
ip_address = '0.0.0.0'

# Set initial pin states
buzzer_pin.value(0)
lockRelay_pin.value(0)

CONFIG_DICT = {}
KEYS_DICT = {}

# Wipe config dictionary from memory
def wipe_config():
  global CONFIG_DICT
  CONFIG_DICT = {}

# Wipe key dictionary from memory
def wipe_keys():
  global KEYS_DICT
  KEYS_DICT = {}

# Load config file from ESP32
def load_esp_config():
  global CONFIG_DICT
  try:
    with open('dl32.cfg') as json_file:
      CONFIG_DICT = json.load(json_file)
  except:
    print('ERROR: Could not load dl32.cfg into config dictionary')
load_esp_config()

# Load keys file from ESP32
def load_esp_keys():
  global KEYS_DICT
  try:
    with open('keys.cfg') as json_file:
      KEYS_DICT = json.load(json_file)
  except:
    print('ERROR: Could not load keys.cfg into keys dictionary')
load_esp_keys()

# Load config file from SD card
def load_sd_config():
  global CONFIG_DICT
  try:
    with open('sd/dl32.cfg') as json_file:
      wipe_config()
      CONFIG_DICT = json.load(json_file)
      resync_html_content()
  except:
    print('ERROR: Could not load sd/dl32.cfg into config dictionary')

# Load keys file from SD card
def load_sd_keys():
  global KEYS_DICT
  try:
    with open('sd/keys.cfg') as json_file:
      wipe_keys()
      KEYS_DICT = json.load(json_file)
      resync_html_content()
  except:
    print('ERROR: Could not load sd/keys.cfg into keys dictionary')

WIFISSID = (CONFIG_DICT['wifi_ssid'])
WIFIPASS = (CONFIG_DICT['wifi_pass'])
mqtt_clid = (CONFIG_DICT['mqtt_clid'])
mqtt_brok = (CONFIG_DICT['mqtt_brok'])
mqtt_port = (CONFIG_DICT['mqtt_port'])
mqtt_user = (CONFIG_DICT['mqtt_user']).encode('utf_8')
mqtt_pass = (CONFIG_DICT['mqtt_pass']).encode('utf_8')
mqtt_cmd_top = (CONFIG_DICT['mqtt_cmd_top']).encode('utf_8')
mqtt_sta_top = (CONFIG_DICT['mqtt_sta_top']).encode('utf_8')
web_port = (CONFIG_DICT['web_port'])
key_NUMS = KEYS_DICT.keys()

# Check if a file exists
def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False

# Connect to wifi using details from config file
def connect_wifi():
  global ip_address
  sta_if = network.WLAN(network.STA_IF)
  if not sta_if.isconnected():
    sta_if.active(True)
    sta_if.connect(WIFISSID, WIFIPASS)
    while not sta_if.isconnected():
      pass # wait till connection
  ip_address = sta_if.ifconfig()[0]
  print('IP address: ' + ip_address)
  print('Connected to wifi SSID ' + WIFISSID)
  resync_html_content()

# REfresh the date and time
def refresh_time():
  global year, month, day, hour, mins, secs, weekday, yearday
  year, month, day, hour, mins, secs, weekday, yearday = time.localtime()

# Save key dictionary to SD card
def save_keys_to_sd():
  if file_exists('sd/keys.cfg'):
      #rename old file
      refresh_time()
      os.rename('sd/keys.cfg', ('sd/keys' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('sd/keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)

# Save configuration dictionary to SD card
def save_config_to_sd():
  if file_exists('sd/dl32.cfg'):
      #rename old file
      refresh_time()
      os.rename('sd/dl32.cfg', ('sd/dl32' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('sd/dl32.cfg', 'w') as json_file:
    json.dump(CONFIG_DICT, json_file)

# Save key dictionary to ESP32
def save_keys_to_esp():
  if file_exists('keys.cfg'):
      #rename old file
      refresh_time()
      os.rename('keys.cfg', ('keys' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)

# Save configuration dictionary to ESP32
def save_config_to_esp():
  if file_exists('dl32.cfg'):
      #rename old file
      refresh_time()
      os.rename('dl32.cfg', ('dl32' + str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs) + '.cfg')))
  with open('dl32.cfg', 'w') as json_file:
    json.dump(CONFIG_DICT, json_file)

# Start Microdot Async web server
def start_server():
  print('Starting web server on port ' + str(web_port))
  mqtt.publish(mqtt_sta_top, ('Starting web server on port ' + str(web_port)), retain=False, qos=0)
  try:
    web_server.run(port = web_port)
  except:
    web_server.shutdown()
    print('Failed to start web server')

# Import keys from SD card into keys dictionary and overwrite keys.cfg on ESP32
def import_keys_from_sd():
  if file_exists('sd/keys.cfg'):
    load_sd_keys()
    if file_exists('keys.cfg'):
      refresh_time()
      os.rename('keys.cfg', 'keys_' + (str('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))))
      save_keys_to_esp()
  else:
    print('No file sd/' + filename + ' on SD card')

# Check for button commands at boot
def check_boot():
  global sd_boot_hold_time
  while True:
    if int(progButton_pin.value()) == 0:
      time_held = 0
      while (int(progButton_pin.value()) == 0 and time_held <= sd_boot_hold_time):
        time.sleep_ms(10)
        time_held += 10
      if time_held > add_hold_time:
        print('Loading configuration from SD card')

# Add a new key to the autorized keys dictionary
def add_key(key_number):
  if (len(str(key_number)) > 1 and len(str(key_number)) < 7):
    print ('  Adding key ' + str(key_number))
    refresh_time()
    KEYS_DICT[str(key_number)] = ('{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))
    with open('keys.cfg', 'w') as json_file:
      json.dump(KEYS_DICT, json_file)
    print('  Key added to authorized list as: ' + '{}{:02d}{:02d}_{:02d}{:02d}{:02d}'.format(year, month, day, hour, mins, secs))
    resync_html_content()
  else:
    print('  Unable to add key ' + key_number)
    print('  Invalid key!')

# Add a new key to the autorized keys dictionary
def rem_key(key_number):
  if (len(str(key_number)) > 1 and len(str(key_number)) < 7) and (str(key_number) in KEYS_DICT):
    print ('  Removing key ' + str(key_number))
    del KEYS_DICT[str(key_number)]
    with open('keys.cfg', 'w') as json_file:
      json.dump(KEYS_DICT, json_file)
    print('  Key '+ str(key_number) +' removed!')
    resync_html_content()
  else:
    print('  Unable to remove key ' + key_number)
    print('  Invalid key format - key not removed')

def ren_key(key, name):
  if (len(str(key)) > 1 and len(str(key)) < 7) and (str(key) in KEYS_DICT) and (len(name) > 0) and (len(name) < 16) :
    print ('  Renaming key ' + str(key) + ' to ' + name)
    KEYS_DICT[str(key)] = name
    with open('keys.cfg', 'w') as json_file:
      json.dump(KEYS_DICT, json_file)
    print('  Key '+ str(key) +' renamed!')
    resync_html_content()
  else:
    print('  Unable to rename key ' + key)

# RFID key listener function
def on_key(key_number, facility_code, keys_read):
  global add_mode
  global add_mode_counter
  global add_mode_intervals
  print('key detected')
  if (str(key_number) in key_NUMS):
    if add_mode == False:
      print ('  Authorized key: ')
      print ('  key #: ' + str(key_number))
      print ('  key belongs to ' + KEYS_DICT[str(key_number)])
      unlock(key_dur)
    else:
      add_mode = False
      print ('  key #' + str(key_number) + ' is already authorized.')
      add_mode_counter = add_mode_intervals
  else:
    if add_mode == False:
      print ('  Unauthorized key: ')
      print ('  key #: ' + str(key_number))
      print ('  Facility code: ' + str(facility_code))
      invalidBeep()
    else:
      add_key(key_number)
      add_mode = False
      add_mode_counter = add_mode_intervals

Wiegand(wiegand_0, wiegand_1, on_key)

# MQTT callback function
def sub_cb(topic, msg):
  print('Message arrived on topic ' + topic.decode('utf-8') + ': ' + msg.decode('utf-8'))
  if topic == mqtt_cmd_top:
    if msg.decode('utf-8') == 'unlock':
      unlock(mqtt_dur)
    else:
      print ('Command not recognized!')

# Resync contents of static HTML webpage to take into account changes
def resync_html_content():
  global html
  global ip_address
  
  rem_buttons = '<table style="width: 380px; text-align: left; border: 0px solid black; border-collapse: collapse; margin-left: auto; margin-right: auto;">'
  for key in KEYS_DICT:
      rem_buttons += '<tr> <td style="width: 200px;"> <a style="font-size: 15px;"> &bull; ' + key + ' (' + KEYS_DICT[key] + ') </a> </td> <td> <input id="renKeyInput_' + key + '" class="renInput" value=""> <a> <button onClick="renKey('+key+')" class="ren">REN</button> </a> </td> <td> <a href="/rem_key/' + key + '  "> <button class="rem">DEL</button> </a> </td> </tr>'
  rem_buttons += "</table>"
  
  html = """<!DOCTYPE html>
  <html>
    <head>
      <style>div {width: 400px; margin: 20px auto; text-align: center; border: 3px solid #32e1e1; background-color: #555555; left: auto; right: auto;}.header {font-family: Arial, Helvetica, sans-serif; font-size: 20px; color: #32e1e1;}button {width: 300px; background-color: #32e1e1; border: none; text-decoration: none;}button.rem {background-color: #C12200; width: 40px;}button.rem:hover {background-color: red}button.ren {background-color: #ff9900; width: 40px;}button.ren:hover {background-color: #ffcc00}input {width: 296px; border: none; text-decoration: none;}button:hover {background-color: #12c1c1; border: none; text-decoration: none;} input.renInput{width: 75px} .main_heading {font-family: Arial, Helvetica, sans-serif; color: #32e1e1; font-size: 30px;}h5 {font-family: Arial, Helvetica, sans-serif; color: #32e1e1;}label{font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}a {font-family: Arial, Helvetica, sans-serif; font-size: 10px; color: #32e1e1;}textarea {background-color: #303030; font-size: 11px; width: 300px; height: 75px; resize: vertical; color: #32e1e1;}body {background-color: #303030; text-align: center;}</style>
      <script>
      window.addKey = function(){
        var input = document.getElementById("addKeyInput").value;
        window.location.href = "/add_key/" + input;
      }
      </script>
      <script>
      window.renKey = function(key){
        var inputid = "renKeyInput_" + key.toString()
        console.log(inputid)
        var input = document.getElementById(inputid).value;
        window.location.href = "/ren_key/" + key + "/" + input;
      }
      </script>
    </head>
    <body>
      <div>
        <br/>
        <a class='main_heading'>DL32 MENU</a></br/>
        <a style="font-size: 15px">--- MicroPython edition ---</a><br/>
        <a>by Mark Booth - </a><a href='https://github.com/Mark-Roly/DL32_mpy'>github.com/Mark-Roly/DL32_mpy</a><br/><br/>
        <a class='header'>Device Control</a>
        <br/>
        <a href='/unlock'><button>HTTP Unlock</button></a><br/>
        <a href='/bell'><button>Ring bell</button></a><br/>
        <a href='/reset'><button>Reset Board</button></a><br/><br/>
        <a class='header'>Key Management</a>
        <br/>
        <a href='/print_keys'><button>List authorized keys</button></a><br/>
        <a href='/purge_keys'><button>Purge authorized keys</button></a><br/><br/>
        <a class='header'>File Download</a>
        <br/>
        <a href='/download/main.py'><button>Download main.py</button></a><br/>
        <a href='/download/boot.py'><button>Download boot.py</button></a><br/>
        <a href='/download/dl32.cfg'><button>Download dl32.cfg</button></a><br/>
        <a href='/download/keys.cfg'><button>Download keys.cfg</button></a><br/><br/>
        <hr> <a class='header'>Delete/Rename Keys</a><br/><a style="color:#ffcc00; font-size: 15px; font-weight: bold;">***This cannot be undone!***</a>
        <br/>""" + rem_buttons + """
        <br/>
        <hr> <a class='header'>Add Key</a><br/>
        <input id="addKeyInput" value="">
        <button onClick="addKey()">Add</button>
        <br/>
        <br/>
        <hr>
        <a class='header'>keys.cfg JSON</a><br/>
        <textarea readonly style="height: 50px">""" + str(KEYS_DICT) + """</textarea><br/><br/>
        <a class='header'>dl32.cfg JSON</a><br/>
        <textarea readonly style="height: 100px">""" + str(CONFIG_DICT) + """</textarea>
        <br/>
        <a>Version """ + _VERSION + """ IP Address """ + str(ip_address) + """</a><br/>
        <br/>
      </div>
    </body>
  </html>"""

resync_html_content()

# Print allowed keys to serial
def print_keys():
  global KEYS_DICT
  if KEYS_DICT == {}:
    print('  [NONE]')
  else:
    for key in KEYS_DICT:
      print('  ' + key + ' - ' + KEYS_DICT[key])

# Delete all allowed keys
def purge_keys():
  global KEYS_DICT
  KEYS_DICT = {}
  with open('keys.cfg', 'w') as json_file:
    json.dump(KEYS_DICT, json_file)
  resync_html_content()

# Unlock for duration specified as argument
def unlock(dur):
  lockRelay_pin.value(1)
  unlockBeep()
  print('  Unlocked')
  mqtt.publish(mqtt_sta_top, 'Unlocked', retain=False, qos=0)
  time.sleep_ms(dur)
  lockRelay_pin.value(0)
  print('  Locked')
  mqtt.publish(mqtt_sta_top, 'Locked', retain=False, qos=0)

# Async function to listen for exit button presses
def mon_exit_but():
  global add_hold_time
  global add_mode
  global stop_bell
  if int(exitButton_pin.value()) == 0:
    stop_bell = True
    time_held = 0
    while (int(exitButton_pin.value()) == 0 and time_held <= add_hold_time):
      time.sleep_ms(10)
      time_held += 10
    if time_held > add_hold_time:
      print('Key add mode')
      uasyncio.create_task(key_add_mode())
      add_mode == True
    elif add_mode == False:
      print('Exit button pressed')
      unlock(exitBut_dur)

# Async function to listen for proramming button presses
def mon_prog_but():
  global add_hold_time
  global stop_bell
  if int(progButton_pin.value()) == 0:
    stop_bell = True
    time_held = 0
    while (int(progButton_pin.value()) == 0 and time_held <= add_hold_time):
      time.sleep_ms(10)
      time_held += 10
    if time_held > add_hold_time:
      print('copying SD to ESP')
      prog_sd_beeps()
      try:
        import_keys_from_sd()
        print('Complete')
      except:
        print('ERROR: Import from SD failed!')
    else:
      print('prog button pressed')

# Async function to listed for MQTT commands
def mon_cmd_topic():
  mqtt.check_msg()

# Async function to send PinReq messages to MQTT broker
async def mqtt_ping():
  while True:
    mqtt.ping()
    await uasyncio.sleep(60)

# Send hearbeat MQTT message every 30min
async def mqtt_status():
  while True:
    print('Published status message to ' + mqtt_sta_top.decode('utf-8'))
    mqtt.publish(mqtt_sta_top, 'Still alive!', retain=False, qos=0)
    await uasyncio.sleep(1800)

# Play doorbel tone
async def ring_bell():
  print ('  Ringing bell')
  mqtt.publish(mqtt_sta_top, 'Ringing bell', retain=False, qos=0)
  global stop_bell
  stop_bell = False
  loop1 = 0
  while loop1 <= 3:
    loop2 = 0
    while loop2 <= 30:
      if stop_bell == True:
          return
      if silent_mode == True:
          return
      buzzer_pin.value(1)
      await uasyncio.sleep_ms(10)
      buzzer_pin.value(0)
      await uasyncio.sleep_ms(10)
      loop2 +=1
    await uasyncio.sleep_ms(2000)
    loop1 +=1

# Enter mode to add new key
def key_add_mode():
  global add_mode
  global add_mode_intervals
  global add_mode_counter
  add_mode_counter = 0
  print('Waiting for new key',end=' ')
  add_mode = True
  while add_mode_counter < add_mode_intervals:
    print('.',end=' ')
    lil_bip()
    await uasyncio.sleep_ms(int(addKey_dur/add_mode_intervals))
    add_mode_counter += 1
  if key_add_mode == True:
    print('No key detected.')
    key_add_mode == False

# "Beep-Beep"
def unlockBeep():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(75)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(75)
  buzzer_pin.value(0)

# "Beeeep-Beeeep"
def invalidBeep():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(500)
  buzzer_pin.value(0)
  time.sleep_ms(100)
  buzzer_pin.value(1)
  time.sleep_ms(500)
  buzzer_pin.value(0)

# "Bip"
def lil_bip():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(10)
  buzzer_pin.value(0)

def prog_sd_beeps():
  if silent_mode == True:
    return
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)
  time.sleep_ms(50)
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)
  time.sleep_ms(50)
  buzzer_pin.value(1)
  time.sleep_ms(50)
  buzzer_pin.value(0)

# --------- MAIN -----------

async def main_loop():
  while True:
    wdt.feed()
    mon_exit_but()
    mon_prog_but()
    mon_cmd_topic()
    await uasyncio.sleep_ms(10)
  
if silent_mode == True:
  print('Silent Mode Activated')

try:
  connect_wifi()
except:
  print('ERROR: Could not connect to WiFi')

try:
  mqtt = MQTTClient(mqtt_clid, mqtt_brok, port=mqtt_port, user=mqtt_user, password=mqtt_pass, keepalive=300)
  mqtt.set_callback(sub_cb)
  mqtt.connect()
  print ('Connected to MQTT broker ' + mqtt_brok)
except:
  print('ERROR: Could not connect to MQTT Broker')

try:
  mqtt.subscribe(mqtt_cmd_top)
  print ('Subscribed to topic ' + mqtt_cmd_top.decode('utf-8'))
except: 
  print('ERROR: Could not subscribe to MQTT command topic ' + mqtt_cmd_top.decode('utf-8'))

web_server = Microdot()

uasyncio.create_task(main_loop())
uasyncio.create_task(mqtt_ping())

# uasyncio.create_task(mqtt_status())

@web_server.route('/')
def hello(request):
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/unlock')
def unlock_http(request):
  print('Unlock command recieved from WebUI')
  unlock(http_dur)
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/reset')
def reset_http(request):
  print('Reset command recieved from WebUI')
  machine.reset()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/bell')
async def bell_http(request):
  print('Bell command recieved from WebUI')
  uasyncio.create_task(ring_bell())
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/download/<string:filename>', methods=['GET', 'POST'])
def dl_file(request, filename):
  return send_file(str('/' + filename), status_code=200)

@web_server.route('/print_keys')
def print_keys_http(request):
  print('Print keys command recieved from WebUI')
  print_keys()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/purge_keys')
def purge_keys_http(request):
  print('Purge keys command recieved from WebUI')
  purge_keys()
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/add_key/<string:key>', methods=['GET', 'POST'])
def content(request, key):
  print('Add key command recieved from WebUI ' + key)
  add_key(key)
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/rem_key/<string:key>', methods=['GET', 'POST'])
def content(request, key):
  print('Remove key command recieved from WebUI ' + key)
  rem_key(key)
  return html, 200, {'Content-Type': 'text/html'}

@web_server.route('/ren_key/<string:key>/<string:name>', methods=['GET', 'POST'])
def content(request, key, name):
  print('Rename key command recieved from WebUI  to rename ' + key + ' to ' + name)
  ren_key(key, name)
  return html, 200, {'Content-Type': 'text/html'}

start_server()