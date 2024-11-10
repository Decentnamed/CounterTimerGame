import time
import pyvisa as visa
import json

# load config file
with open('config.json', 'r', encoding='utf-8') as file:
    config_data = json.load(file)

rm = visa.ResourceManager()
instr_cnt100 = rm.open_resource(config_data['cnt100'])
instr_cnt100.timeout = 25000

instr_cnt91 = rm.open_resource(config_data['cnt91'])
print(instr_cnt100.query('*IDN?'))
print(instr_cnt91.query('*IDN?'))

output = 'PULSe' # 'OFF' to low level no activity
reset = '*RST'
clear = '*CLS'
pulse_period = ':SOURce:PULSe:PERiod 0.01'
pulse_width = ':SOURce:PULSe:WIDTh 0.005'

print("settings devices...")

# setting device generator
def init_generator_settings():
    instr_cnt91.write(reset)
    instr_cnt91.write(clear)
    instr_cnt91.write(pulse_period)
    instr_cnt91.write(pulse_width)
    instr_cnt91.query('*OPC?')


# setting counter
def init_counter_settings():
    instr_cnt100.write(reset)
    instr_cnt100.write(clear)
    instr_cnt100.write(':SYST:CONF "Function=PeriodSingle A; SampleCount=1; SampleInterval=200E-3; TriggerModeA=Manual; AbsoluteTriggerLevelA=0.5; ImpedanceA=50 Ohm; CouplingA=DC"')
    instr_cnt100.query('*OPC?')
    print(instr_cnt100.query(':SYST:ERR?'))

init_generator_settings()
init_counter_settings()

#time.sleep(1)

#open gate

instr_cnt100.write(':INIT')

instr_cnt91.write(':OUTPut:TYPE ' + output)
print("Gate open pulse HIGH")
time.sleep(config_data['rise']) # to opoznienie jest wazne, inaczej licznik nie "zlapie" zbocza 

output = 'OFF'
instr_cnt91.write(':OUTPut:TYPE ' + output)
print("Gate open pulse LOW")

time.sleep(3)

# close gate
output = 'PULSe'
instr_cnt91.write(':OUTPut:TYPE ' + output)
print("Gate close pulse HIGH")

time.sleep(config_data['rise']) # to opoznienie jest wazne, inaczej licznik nie "zlapie" zbocza 


output = 'OFF'
instr_cnt91.write(':OUTPut:TYPE ' + output)
print("Gate close pulse LOW")

print("Finish")

instr_cnt100.query('*OPC?')
data_str = instr_cnt100.query(':FETCH:ARRAY? MAX, A')
#print(data_str)

data_str = data_str.strip()  # to remove \n at the end

if len(data_str) > 0:
    data = list(map(float, data_str.split(',')))  # Convert the string to python array
else:
    data = []
print('Results: {}'.format(data if data else 'no data (signal not connected?)'))

print(type(data[0]))
instr_cnt91.close()
instr_cnt100.close()



