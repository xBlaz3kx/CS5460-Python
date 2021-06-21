import spidev
import RPi.GPIO as GPIO


class CS5460:
    """
    Class representing a CS5460 power meter chip.
    """

    def __init__(self, pin: int = 0, bus: int = 0, voltage_divider_offset: float = 52,
                 current_shunt_offset: float = 0.01):
        self.pin: int = pin
        self.bus: int = bus
        GPIO.setup(self.pin, GPIO.OUT)
        # Input range (+-) in mV
        self.VOLTAGE_RANGE: float = 0.250
        self.CURRENT_RANGE: float = 0.250
        # (R1 + R2) / R2
        self.VOLTAGE_DIVIDER: float = voltage_divider_offset
        # Shunt resistance in Ohms
        self.CURRENT_SHUNT: float = current_shunt_offset
        self.VOLTAGE_MULTIPLIER: float = (self.VOLTAGE_RANGE * self.VOLTAGE_DIVIDER)
        self.CURRENT_MULTIPLIER: float = (self.CURRENT_RANGE / self.CURRENT_SHUNT)
        self.POWER_MULTIPLIER = self.VOLTAGE_MULTIPLIER * self.CURRENT_MULTIPLIER
        # Set power meter constants
        self.START_SINGLE_CONVERT = 0xE0
        self.START_MULTI_CONVERT = 0xE8
        self.SYNC0 = 0xFE
        self.SYNC1 = 0xFF
        self.POWER_UP_HALT_CONTROL = 0xA0
        self.POWER_DOWN_MODE_0 = 0x80
        self.POWER_DOWN_MODE_1 = 0x88
        self.POWER_DOWN_MODE_2 = 0x90
        self.POWER_DOWN_MODE_3 = 0x98
        self.CALIBRATE_CONTROL = 0xC0
        self.CALIBRATE_CURRENT = 0x08
        self.CALIBRATE_VOLTAGE = 0x10
        self.CALIBRATE_CURRENT_VOLTAGE = 0x18
        self.CALIBRATE_GAIN = 0x02
        self.CALIBRATE_OFFSET = 0x01
        self.CALIBRATE_ALL = 0x1B
        self.CONFIG_REGISTER = (0x00 << 1)
        self.CURRENT_OFFSET_REGISTER = (0x01 << 1)
        self.CURRENT_GAIN_REGISTER = (0x02 << 1)
        self.VOLTAGE_OFFSET_REGISTER = (0x03 << 1)
        self.VOLTAGE_GAIN_REGISTER = (0x04 << 1)
        self.CYCLE_COUNT_REGISTER = (0x05 << 1)
        self.PULSE_RATE_REGISTER = (0x06 << 1)
        self.LAST_CURRENT_REGISTER = (0x07 << 1)
        self.LAST_VOLTAGE_REGISTER = (0x08 << 1)
        self.LAST_POWER_REGISTER = (0x09 << 1)
        self.TOTAL_ENERGY_REGISTER = (0x0A << 1)
        self.RMS_CURRENT_REGISTER = (0x0B << 1)
        self.RMS_VOLTAGE_REGISTER = (0x0C << 1)
        self.TIME_BASE_CALI_REGISTER = (0x0D << 1)
        self.STATUS_REGISTER = (0x0F << 1)
        self.INTERRUPT_MASK_REGISTER = (0x1A << 1)
        self.WRITE_REGISTER = 0x40
        self.READ_REGISTER = (~self.WRITE_REGISTER)
        self.CHIP_RESET = 0x01 << 7
        self.SIGN_BIT = 0x01 << 23
        self.DATA_READY = 0x01 << 23
        self.CONVERSION_READY = 0x01 << 20
        # Init SPI
        self._spi = spidev.SpiDev()
        self._spi.open(bus, 0)
        self._spi.max_speed_hz = 500000
        self._spi.no_cs = True
        # Initial sync
        try:
            GPIO.output(self.pin, GPIO.LOW)
            self._spi.writebytes([self.SYNC1, self.SYNC1, self.SYNC1, self.SYNC0])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        self._start_converting()

    def __send(self, data):
        """
        Send data to the chip.
        :param data: Byte to send
        """
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Send data
            self._spi.writebytes([data])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)

    def _send_to_register(self, register, data):
        """
        Send data to a certain register.
        :param register: Register address (5 bits << 1)
        :param data: data to write (3 bytes)
        :return:
        """
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Select register for writing
            self._spi.writebytes([register | self.WRITE_REGISTER])
            # Send data
            self._spi.writebytes([(data & 0xFF0000) >> 16, (data & 0xFF00) >> 8, data & 0xFF])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)

    def reset(self):
        self._send_to_register(self.CONFIG_REGISTER, self.CHIP_RESET)
        try:
            GPIO.output(self.pin, GPIO.LOW)
            self._spi.writebytes([self.SYNC1, self.SYNC1, self.SYNC1, self.SYNC0])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        self._start_converting()
        while not (self.__get_status() & self.CONVERSION_READY):
            # Wait until conversion starts
            pass

    def _start_converting(self):
        self.__clear_status(self.CONVERSION_READY)
        self.__send(self.START_MULTI_CONVERT)
        while not (self.__get_status() & self.CONVERSION_READY):
            # Wait until conversion starts
            pass

    def _stop_converting(self):
        self.__send(self.POWER_UP_HALT_CONTROL)

    def __read_value_from_register(self, register):
        """
        Get the current value of the desired register
        :return: Register value between 0 and 0xFFFFFF
        """
        value = 0
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Select register for reading
            self._spi.writebytes([register & self.READ_REGISTER])
            # Read the register
            read_list = self._spi.readbytes(3)

            for i in range(0, 3):
                value <<= 8
                value |= read_list[i]
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        return value

    def __signed_to_float(self, data):
        """
        Convert signed int value to float
        :param data: Raw register value
        :return: Float from -1 to 1
        """
        if data & self.SIGN_BIT:
            data = data - (self.SIGN_BIT << 1)
        return data / self.SIGN_BIT

    def get_current(self) -> float:
        """
        Get current measured in the last conversion cycle in Amps (A).
        :return: Electric current value
        """
        current_value_raw = self.__read_value_from_register(self.LAST_CURRENT_REGISTER)
        return self.__signed_to_float(current_value_raw) * self.CURRENT_MULTIPLIER

    def get_voltage(self) -> float:
        """
        Get voltage measured in the last conversion cycle in Volts (V).
        :return: Voltage value
        """
        voltage_value_raw = self.__read_value_from_register(self.LAST_VOLTAGE_REGISTER)
        return self.__signed_to_float(voltage_value_raw) * self.VOLTAGE_MULTIPLIER

    def get_power(self) -> float:
        """
        Get instantaneous power from the last conversion cycle in Watts (W).
        :return: Power value
        """
        power_value_raw = self.__read_value_from_register(self.LAST_POWER_REGISTER)
        return self.__signed_to_float(power_value_raw) * self.POWER_MULTIPLIER

    def get_energy(self) -> float:
        """
        Get energy consumed in the last computation cycle in Joules (J)
        This should be called every second and the result added to total
        energy.
        :return: Energy value
        """
        energy_value_raw = self.__read_value_from_register(self.TOTAL_ENERGY_REGISTER)
        return self.__signed_to_float(energy_value_raw) * self.POWER_MULTIPLIER

    def __get_status(self):
        return self.__read_value_from_register(self.STATUS_REGISTER)

    def __clear_status(self, cmd):
        self._send_to_register(self.STATUS_REGISTER, cmd)

    def __calibrate(self, cmd):
        """
        Performs the calibration and stores the value in the appropriate
        register. The value needs to be written to the register after
        every reset. The calibration doesn't seem to work very well,
        it's better to read the value and then invert it manually.
        :param cmd:
        :return:
        """
        # Stop any conversions
        self._stop_converting()
        self.__clear_status(self.DATA_READY)
        cmd = self.CALIBRATE_CONTROL | (cmd & self.CALIBRATE_ALL)
        self.__send(cmd)
        while not (self.__get_status() & self.DATA_READY):
            # Wait until data ready
            pass
        self.__clear_status(self.DATA_READY)
        self._start_converting()

    def calibrate_voltage_offset(self) -> int:
        """
        Short the VIN+ and VIN- pins and call the function.
        The value will be stored until next reset.
        :return: VOLTAGE_OFFSET_REGISTER value
        """
        self.__calibrate(self.CALIBRATE_VOLTAGE | self.CALIBRATE_OFFSET)
        return self.__read_value_from_register(self.VOLTAGE_OFFSET_REGISTER)

    def set_voltage_offset(self, value):
        """
        Sets the VOLTAGE_OFFSET_REGISTER, use to restore
        a previously measured calibration value.
        A good default value is 400000
        :param value: VOLTAGE_OFFSET_REGISTER value
        """
        self._stop_converting()
        self._send_to_register(self.VOLTAGE_OFFSET_REGISTER, value)
        self._start_converting()

    def calibrate_current_offset(self) -> int:
        """
        Short the VIN+ and VIN- pins and call the function.
        The value will be stored until next reset.
        :return: VOLTAGE_OFFSET_REGISTER value
        """
        self.__calibrate(self.CALIBRATE_CURRENT | self.CALIBRATE_OFFSET)
        return self.__read_value_from_register(self.CURRENT_OFFSET_REGISTER)

    def set_current_offset(self, value):
        """
        Sets the CURRENT_OFFSET_REGISTER, use to restore
        a previously measured calibration value.
        A good default value is -70000
        :param value: CURRENT_OFFSET_REGISTER value
        """
        self._stop_converting()
        self._send_to_register(self.CURRENT_OFFSET_REGISTER, value)
        self._start_converting()
