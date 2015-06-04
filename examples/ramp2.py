"""
Simple example that connects to the first Crazyflie found, ramps up/down
the motors and disconnects.
"""

import time, sys
from threading import Thread
import numpy as np
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
	
	# Declarare senzori ca atribute
	self.gyro_x = None
	self.gyro_y = None
	self.gyro_z = None
	self.baro   = None
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
    
    ########## Definire callback-uri logging ##########	 	   
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
    ##################################################	
    
    def _ramp_motors(self):

	########## Achizitie date senzori ########################################	
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
	
	
	############### Initializare #############################################
        thrust  = 44000 # thrustul initial
	clock   = 0 	      			
        pitch   = 0
        roll    = 0
        yawrate = 0
	x = 0
	y = 0
	z = 0
        t_init = 0
        altit  = 0
	raise_time = 10 # nr de esantione in care se trimite doar comanda thrust initial
	Baro = list()   # aici se salveaza ultimele primele <raise_time> valori ale senzorului baro
	
	
	# bucla principala de control
	while True: 
	    roll    = -0.3*x    #
	    pitch   = -0.3*y 	# corectii proportionale 
	    yawrate = -0.3*z	#	    
   	    	
            if clock == raise_time:
	    	# altit e valoarea la care dorim sa mentinem CF
		# oscilatiile valorilor scoase de senzorul baro sunt mari 
    		# astfel luam in calcul 3 variante:
		
		altit   = max(Baro)    # maximul valorilor pe ultimele <raise_time> esantioane	
		#altit   = np.mean(Baro # media valorilor pe ultimele <raise_time> esantioane
		#altit   = min(Baro)	# minimul valorilor pe ultimele <raise_time> esantioane    	
		#altit   = self.baro + (max(Baro) - min(Baro)) # valoarea curenta a senzorului adunata cu un delta
		
	    if clock <= raise_time:
		if not(self.baro == None):
			Baro.append(self.baro)
		self._cf.commander.send_setpoint(roll, pitch, yawrate, thrust) # r,p,y vor fi 0 
	    else:
		if self.baro: 
			# diferenta este de ordinul zecimalelor si trebuie amplificata 
			thrust = thrust - 1500*(self.baro - altit) 
			
			# limitam thrust-ul la 10k respectiv 53k pentru siguranta                        
			if thrust < 10000:
				thrust = 10000
			if thrust > 53000:
				thrust = 53000
			
			# trimitem comanda cu valorile calculate		
			self._cf.commander.send_setpoint(roll, pitch, yawrate, thrust)				
		else:  
			# daca nu se citeste baro sau se citeste ca fiind 0, impunem modul de althold
			self._cf.param.set_value("flightmode.althold", "True") 
		 			
	    time.sleep(0.1) # perioada de esantionare
				    
	    if clock < 1: 
		# se sare peste primul esantion ca se se poata face diferenta intre timestamp-uri
    	    	t_init = self.timest
            else:
		# util in calculul noilor roll,pitch,yaw 	 
	    	x = x + self.gyro_x*(self.timest - t_init)/1000
	    	y = y + self.gyro_y*(self.timest - t_init)/1000
            	z = z + self.gyro_z*(self.timest - t_init)/1000
	    
	    	t_init = self.timest

	    	print [t_init,"---",x, y, z, "baro:",self.baro,"altit:",altit,"thrust:",thrust]	
	    
	    clock = clock + 1
	# end while
	
	# nu ar trebui sa ajunga aici         
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
