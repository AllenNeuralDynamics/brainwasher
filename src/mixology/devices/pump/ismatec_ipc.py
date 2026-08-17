#!/usr/bin/python
"""
Low-level serial driver for Ismatec IPC peristaltic pumps.

Communicates with Ismatec IPC-N series pumps over RS-232 serial,
providing flow rate control, timed dispensing, direction control,
and pump status queries.

Serial protocol: 9600 baud, 8N1, 100ms timeout.
Command format: <pump_id><command><CR> (CR = 0x0D)
Response: '*' for success, '+'/'-' for running/stopped status.

Original authors: George Emanuel, Jeff Moffitt, Rusty Nicovich (2017)
Modified by: Brian Long (2017, 2020 - Python 3 port)
"""

import serial
import time
import numpy as np
import logging


class TimeoutError(Exception):
    """Raised when a pump communication times out."""
    pass


acknowledge = '\x06'
start = '\x0A'
stop = '\x0D'


# Acceptable tubing diameters: 1.02, 1.14, 1.52 (~1/16"), 3.17 mm (~1/8")
class Ismatec(object):
    """Serial driver for Ismatec IPC peristaltic pumps.

    Manages a serial connection to an Ismatec IPC pump and provides methods
    for flow rate control, timed volume dispensing, pump start/stop, and
    direction control.

    Args:
        serPort: Serial port name (e.g., 'COM9').
        tubingDiameter: Inner diameter of pump tubing in mm (default 1.52).
        expectedPumpID: Expected pump model ID string for verification.
    """

    def __init__(self, serPort: str, tubingDiameter: float = 1.52, expectedPumpID: str = 'IPC 405') -> None: #trycom5
        # Define attributes
        logger_name = self.__class__.__name__ + f".{expectedPumpID}"
        self.log = logging.getLogger(logger_name)
        self.com_port = serPort
        self.pump_ID= "1"
        self.tubingDiameter = tubingDiameter # 3.17 # diameter in mm (1/8" ID)
        self.flip_flow_direction = False
        self.expectedPumpID = expectedPumpID
        # Create serial port
        self.serial = serial.Serial(port = self.com_port,
                baudrate = 9600,
                parity= serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1)
        # Define initial pump status
        self.flow_status = "Stopped"
        self.speed = 0.0
        self.direction = "Forward"
        
        IDcheck = self.checkPumpIdentification()
        if IDcheck:
            statRC = self.enableRemoteControl(0)
            statTube = self.setTubingDiameter(self.tubingDiameter)
            setZeroCycles = self.sendToPump('"0000')

            stat = statRC and statTube and statusCheck(setZeroCycles)

            if not(stat):
                self.log.error("Initialization error on %s", self.com_port)
        else:
            self.log.error("Incorrect pump ID on %s", self.com_port)
            self.pumpDisconnect()
        self.defaultRate = float(str.split(self.sendToPump("!").strip())[0]) # set flow rate at max rotational speed in mL/min
        self.speed = float(str.split(self.sendToPump("!").strip())[0])


    def pumpDisconnect(self) -> None:
        """Stop the pump, return to manual control, and close the serial port."""
        self.sendToPump('I') # stop pump
        self.enableRemoteControl(0) # set to manual control
        self.serial.close() # close out serial
        self.log.debug("disconnect pump, close the port!")
        
    def checkPumpIdentification(self) -> int:
        """Query pump model ID and print it. Returns 1 (always succeeds)."""
        pumpIDRead = self.sendToPump("#")
        self.log.debug("Pump " + pumpIDRead.rstrip() + " Identified")
        return 1

    def isPumpRunning(self) -> int:
        """Check if the pump is currently running.

        Returns:
            1 if running, 0 if stopped, -1 if unexpected response.
        """
        status = self.sendToPump("E")
        if (status == "+"):
            return 1
        elif (status == "-"):
            return 0
        else:
            self.log.warning("Return from pump \n Got "+status)
            return -1

    def enableRemoteControl(self, remote: int) -> int:
        """Enable or disable remote (serial) control of the pump.

        Args:
            remote: 1 to enable remote control, 0 to return to manual.
        """
        if (remote == 1):
            status = self.sendToPump("B")
            status = self.sendToPump("DA-PC-")
            
        else:
            status = self.sendToPump("A")
            
        return statusCheck(status)
            
    def setTubingDiameter(self, tubingDiameter: float) -> int:
        """Set the pump tubing inner diameter for accurate flow calculations.

        Args:
            tubingDiameter: Tubing inner diameter in mm (e.g., 0.51, 1.02, 1.52, 3.17).
        """
        status = self.sendToPump("+" + str('%04d' % (int(tubingDiameter*100))))

        return statusCheck(status)

    def setFlowRate(self, flowRate: float) -> bool:
        """ 
        flowRate: float sent to pump after translation to percentage of maximum flow rate
        
        #TODO brianl verify that this is the best way to set the speed on the IPC 501

        """ 
        clearReturn = self.getResponse()
        del clearReturn
        self.defaultRate = float(str.split(self.sendToPump("!").strip())[0]) # set flow rate at max rotational speed in mL/min
        pctRate = np.floor(10000.*flowRate/self.defaultRate)/100.
        if pctRate > 100.:
            self.log.warning('Calculated flow rate too high! reducing to max.\n')
            pctRate = 100.

        # Send flow rate as percentage of max rate (6-digit integer, e.g., 050000 = 50.00%)
        statusFlowRate = self.sendToPump("S"+str(int(pctRate*100)).zfill(6))
        if statusCheck(statusFlowRate):
            self.speed = pctRate*self.defaultRate/100.
            self.log.info("Set flow rate to " + str(self.speed) + " ml per min.")
            return True
        else:
            return False

    def setFlowVolumeAndRate(self, flowVolume: float, flowTime: float) -> None:
        """Configure timed volume dispensing mode.

        Sets the pump to 'time dispense' mode and configures the dispensing
        duration. The flow rate is calculated from volume / time.

        Args:
            flowVolume: Volume to dispense in mL.
            flowTime: Dispensing duration in minutes.

        Note:
            Time precision depends on range:
            - 0-16 min: 100ms increments (command 'V####')
            - 16-960 min: 1 minute increments (command 'VM###')
            - 960-59940 min: 1 hour increments (command 'VH###')
        """
        
        clearReturn = self.getResponse()
        del clearReturn
        
        status = self.sendToPump("N") # Set to 'time dispense' mode
        status = self.resetVolumeCounter()
        
        # Check flow time
        # If less than 16 minutes, will enter in 100 ms increments
        # If over 16 minutes and less than 16 hours, in integer minutes
        # If over 16 hours, in integer hours
        # Volume takes precidence over time, but volume implied in pump.  
        # So take nominal specified time, work out what what integer time is 
        # close enough, then use that.
        
        # Convert from nominal time to correct time in defined precision
        if (0 < flowTime < 16):
            # Flow time in tenths of a second
            flowTimeNow = float(int(flowTime*600))/600
            flowTimeStr = str('V' + '%04d' % int(flowTime*600))
            statusTime = self.sendToPump(flowTimeStr)
            
            
        elif (16 <= flowTime < 960):
            # Flow time in minutes
            flowTimeNow = int(flowTime)
            flowTimeStr = str('VM' + '%03d' % int(flowTime))
            statusTime = self.sendToPump(flowTimeStr)
            
        elif (960 <= flowTime < 59940):
            # Flow time in hours
            flowTimeNow = int(float(flowTime)/60)
            flowTimeStr = str('VH' + '%03d' % int(float(flowTime)/60))
            statusTime = self.sendToPump(flowTimeStr)
            
        else:
            flowTimeStr = 'V0000'
            self.log.error('Flow time undefined!\n')

        self.log.debug("Flow time now: " + str(flowTimeNow))

        # Calculate actual dispense rate from volume and rounded time
        dispenseRate = float(flowVolume)/float(flowTimeNow)
        self.log.info("Actual dispenseRate is "+str(dispenseRate))
        return
    
    def resetVolumeCounter(self) -> str:
        """Reset the pump's internal volume counter to zero."""
        return self.sendToPump("W")

    def inquireVolumeCounter(self) -> str:
        """Query the current volume counter value."""
        return self.sendToPump(":")

    def inquireDefaultFlowRate(self) -> str:
        """Query the default (uncalibrated) flow rate."""
        return self.sendToPump("?")

    def inquireCalibratedFlowRate(self) -> str:
        """Query the calibrated flow rate at maximum rotational speed (mL/min)."""
        return self.sendToPump("!")

    def inquireDigitsAfterDecimal(self) -> str:
        """Query the number of digits after the decimal point in flow readings."""
        return self.sendToPump("[")

    def startPump(self) -> int:
        """Start the pump. Returns 1 on success, 0 on failure."""
        status = self.sendToPump("H")
        return statusCheck(status)

    def stopPump(self) -> int:
        """Stop the pump. Returns 1 on success, 0 on failure."""
        status = self.sendToPump("I")
        return statusCheck(status)

    def setFlowDirection(self, forward: bool) -> int:
        """Set pump flow direction.

        Args:
            forward: True for forward flow, False for reverse.
                     Respects flip_flow_direction attribute for installations
                     where tubing is connected in reverse.
        """
        if self.flip_flow_direction:
            if forward:
               status = self.sendToPump("J")
            else:
               status = self.sendToPump("K")
        else:
            if forward:
               status = self.sendToPump("K")
            else:
                status = self.sendToPump("J")
        return statusCheck(status)
    
    def stopFlow(self) -> int:
        """Stop pump flow. Alias for stopPump()."""
        status = self.sendToPump("I")
        return statusCheck(status)

    def sendToPump(self, commandString: str) -> str:
        """Send a command to the pump and return the response.

        Args:
            commandString: Command string (without pump ID prefix or CR terminator).

        Returns:
            Response string from the pump (decoded UTF-8).
        """
        self.sendString(self.pump_ID + commandString + stop)
        lineOut = self.getResponse()

        return lineOut

    def sendString(self, string: str) -> None:
        """Write a raw string to the serial port."""
        self.serial.write(string.encode())

    def getResponse(self) -> str:
        """Read a line from the serial port and return as decoded string."""
        return self.serial.readline().decode('utf-8')


def statusCheck(strIn: str) -> int:
    """Check if a pump response indicates success.

    Args:
        strIn: Response string from the pump.

    Returns:
        1 if response is '*' (success), 0 otherwise.
    """
    if strIn.rstrip() == '*':
        return 1
    else:
        return 0



