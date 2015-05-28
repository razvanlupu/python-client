"""
Simple example that connects to the first Crazyflie found, ramps up/down
the motors and disconnects.
"""

import time, sys
from threading import Thread

#FIXME: Has to be launched from within the example folder
sys.path.append("../lib")
import cflib
from cflib.crazyflie import Crazyflie

from cfclient.utils.logconfigreader import LogConfig

import logging
logging.basicConfig(level=logging.ERROR)

class MotorRampExample:
    def __init__(self, link_uri):
        self._cf = Crazyflie()

        self._cf.connected.add_callback(self._connected)
        self._cf.disconnected.add_callback(self._disconnected)
        self._cf.connection_failed.add_callback(self._connection_failed)
        self._cf.connection_lost.add_callback(self._connection_lost)

        self._cf.open_link(link_uri)

	self.gyro_x = None
	self.gyro_y = None
	self.gyro_z = None
	self.timest = None

        print "Connecting to %s" % link_uri

    def _connected(self, link_uri):
        """ This callback is called form the Crazyflie API when a Crazyflie
        has been connected and the TOCs have been downloaded."""

        # Start a separate thread to do the motor test.
        # Do not hijack the calling thread!
        Thread(target=self._ramp_motors).start()

    def _connection_failed(self, link_uri, msg):
        """Callback when connection initial connection fails (i.e no Crazyflie
        at the speficied address)"""
        print "Connection to %s failed: %s" % (link_uri, msg)

    def _connection_lost(self, link_uri, msg):
        """Callback when disconnected after a connection has been made (i.e
        Crazyflie moves out of range)"""
        print "Connection to %s lost: %s" % (link_uri, msg)

    def _disconnected(self, link_uri):
        """Callback when the Crazyflie is disconnected (called in all cases)"""
        print "Disconnected from %s" % link_uri
    
    def _stab_log_error(self, logconf, msg):
        """Callback from the log API when an error occurs"""
        print "Error when logging %s: %s" % (logconf.name, msg)
    
    def _stab_log_data_gyro(self, timestamp, data, logconf):
        """Callback froma the log API when data arrives"""
	
       	self.gyro_x = data["gyro.x"]
	self.gyro_y = data["gyro.y"]
	self.gyro_z = data["gyro.z"]
	self.timest = timestamp
	
    def _stab_log_data_baro(self, timestamp, data, logconf):
        self.baro   = data["baro.aslLong"]

    def _ramp_motors(self):
	self.logGyro = LogConfig(name="Gyro",period_in_ms=10)
        self.logGyro.add_variable("gyro.x", "float")
        self.logGyro.add_variable("gyro.y", "float")
        self.logGyro.add_variable("gyro.z", "float")

	self.logBaro = LogConfig(name="Baro",period_in_ms=10)	
	self.logBaro.add_variable("baro.aslLong", "float")
        
	self._cf.log.add_config(self.logGyro)
	self._cf.log.add_config(self.logBaro)

	if self.logGyro.valid:
            # This callback will receive the data
            self.logGyro.data_received_cb.add_callback(self._stab_log_data_gyro)
            # This callback will be called on errors
            self.logGyro.error_cb.add_callback(self._stab_log_error)
            # Start the logging
            self.logGyro.start()
        else:
            print("Could not add logconfig since some variables are not in TOC")

	if self.logBaro.valid:
            # This callback will receive the data
            self.logBaro.data_received_cb.add_callback(self._stab_log_data_baro)
            # This callback will be called on errors
            self.logBaro.error_cb.add_callback(self._stab_log_error)
            # Start the logging
            self.logBaro.start()
        else:
            print("Could not add logconfig since some variables are not in TOC")

	thrust_mult = 1
        thrust_step = 100
        thrust = 45000
	count = 0
        pitch = 0
        roll = 0
        yawrate = 0
	x = 0
	y = 0
	z = 0
        t_init = 0
        altit   = 0
	raise_time = 6

	while thrust >= 0:
	    roll    = -0.2*x  
	    pitch   = -0.2*y 
	    yawrate = -0.2*z		    
   	    	
            if count == raise_time:
	    	altit = self.baro	
	    
	    if count <= raise_time:	
            	self._cf.commander.send_setpoint(roll, pitch, yawrate, thrust)
            	time.sleep(0.1)
	    else:
		#self._cf.param.set_value("flightmode.althold", "True")
		if self.baro: 
			thrust = thrust - 2500*(self.baro - altit)
		else:  
			thrust = 30000
		self._cf.commander.send_setpoint(roll, pitch, yawrate, thrust)            			
	        time.sleep(0.1)
	    			    
	    if count == 0:
    	    	t_init = self.timest
            else:	 
	    	x = x + self.gyro_x*(self.timest - t_init)/1000
	    	y = y + self.gyro_y*(self.timest - t_init)/1000
            	z = z + self.gyro_z*(self.timest - t_init)/1000
	    
	    	t_init = self.timest

	    	print [t_init,"---",x, y, z, "baro:",self.baro,"altit:",altit,"thrust:",thrust]	
	    
	    count = count + 1
        self._cf.commander.send_setpoint(0, 0, 0, 0)
        
	# Make sure that the last packet leaves before the link is closed
        # since the message queue is not flushed before closing
        time.sleep(0.1)
        self._cf.close_link()

if __name__ == '__main__':
    # Initialize the low-level drivers (don't list the debug drivers)
    cflib.crtp.init_drivers(enable_debug_driver=False)
    # Scan for Crazyflies and use the first one found
    print "Scanning interfaces for Crazyflies..."
    available = cflib.crtp.scan_interfaces()
    print "Crazyflies found:"
    for i in available:
        print i[0]

    if len(available) > 0:
        le = MotorRampExample(available[0][0])
    else:
        print "No Crazyflies found, cannot run example"
