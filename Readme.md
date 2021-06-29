## CS5460 power meter chip Python library for Raspberry Pi

This is a library for CS5460 Power meter chip written in Python for Raspberry Pi. It uses SPI communication to read
measurements from the power meter. Inspired by and modified
from [an existing C library for Arduino](https://github.com/xxzl0130/CS5460).

### Connecting the power meter to the Pi

| CS5460 pin | RPi pin | 
| :---:    | :---:    | 
|VD+| 5V | 
| VA+ |5V| 
| GND | GND | 
| SLK | SCLK (GPIO 11) | 
| SDO | MISO (GPIO 9) |
| SDI | MOSI (GPIO 10)|
| CS | Any free GPIO pin |
| RST | 3.3V |

### Installing dependencies

Install the dependencies using

> pip3 install -r requirements

### Sample code

```
def main():
    # Instantiate the chip 
    power_meter: CS5460 = CS5460(pin=25, voltage_divider_offset=1333, current_shunt_offset=0.055)
     while True:
        # Print the values of each register 
        print(f"Power: {round(power_meter.get_power(), 2)}")
        print(f"Current: {round(power_meter.get_current(), 2)}")
        print(f"Voltage: {round(power_meter.get_voltage(), 2)}")
        print(f"Energy: {round(power_meter.get_energy(), 2)}")
        print(f"RMS Voltage: {round(power_meter.get_rms_voltage(), 2)}")
        print(f"RMS Current: {round(power_meter.get_rms_current(), 2)}")
```
