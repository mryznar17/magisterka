#!/usr/bin/python

"""
This script creates topology preepared for POC.
"""

import re
import sys
import os
import time

from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.net import Mininet
from mininet.link import Intf
from mininet.util import quietRun
from mininet.node import Controller, RemoteController
from mininet.topo import Topo
from functools import partial
from mininet.node import OVSSwitch

class PocTopo( Topo ):
    "Topology prepared for POC"

    def __init__( self ):

        # Initialize topology
        Topo.__init__( self )

	# Add hosts and switches
        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )
        h3 = self.addHost( 'h3' )
        h4 = self.addHost( 'h4' )

        s1 = self.addSwitch( 's1' )
        s2 = self.addSwitch( 's2' )
        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        s5 = self.addSwitch( 's5' )

        # Add links
        self.addLink( h1, s1 )
        self.addLink( h2 , s1 )
        self.addLink( h3 , s5 )
        self.addLink( h4 , s5 )

        self.addLink( s1, s2 )
        self.addLink( s1, s3 )
        self.addLink( s1, s4 )
        self.addLink( s2, s3 )
        self.addLink( s3, s4 )
        self.addLink( s3, s5 )
        self.addLink( s4, s5 )


topos = { 'poctopo': ( lambda: PocTopo() ) }


def checkIntf( intf ):
    "Make sure intf exists and is not configured."
    if ( ' %s:' % intf ) not in quietRun( 'ip link show' ):
        error( 'Error:', intf, 'does not exist!\n' )
        exit( 1 )
    ips = re.findall( r'\d+\.\d+\.\d+\.\d+', quietRun( 'ifconfig ' + intf ) )
    if ips:
        error( 'Error:', intf, 'has an IP address,'
               'and is probably in use!\n' )
        exit( 1 )

def printHelp( defaultIF1, defaultIF2, defaultControllerIP, defaultInputSwitch, defaultOutputSwitch ):
    info('Usage:\n')
    info('Program gets arguments in following order: \n')
    info(' 1. First harware interface name (defaut '+defaultIF1+')\n')
    info(' 2. Second harware interface name (defaut '+defaultIF2+')\n')
    info(' 3. Controller ip (default '+defaultControllerIP+')\n')
    info(' 4. Switch number that first interface is connected to (defaut '+str(defaultInputSwitch)+' - represent s'+str(defaultInputSwitch+1)+')\n') 
    info(' 5. Switch number that second interface is connected to (defaut '+str(defaultOutputSwitch)+' - represent s'+str(defaultOutputSwitch+1)+')\n')
    exit( 1 )

# input: output from dump flows command, port number in OpenFlow 
def checkFlows( switchFlows, eth):
    in_port = 'in_port='+eth
    out_port = 'output:'+eth
    lldp = 'dl_type=0x88cc'
    if in_port in switchFlows and out_port in switchFlows and lldp in switchFlows:
	return True  

# check if all flows arrived from controller
def isReady( switch1, eth1, switch2, eth2 ):
    switch1Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch1.name).read()
    switch2Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch2.name).read()
    ofS1Names = getOFIntfNames( getIntfs(switch1), switch1.name )
    ofS2Names = getOFIntfNames( getIntfs(switch2), switch2.name )
    eth1No = getInputFlowNumber( ofS1Names, eth1)
    eth2No = getInputFlowNumber( ofS2Names, eth2)
    if checkFlows( switch1Flows, eth1No ) and checkFlows( switch2Flows, eth2No ):
	return True 

def getInputFlowNumber( ofNames, eth ):
    for port_pair in ofNames:
	if ':'+eth in port_pair:
	    return port_pair[0]

# get list of ports in switch ie. [s1-eth1, s1-eth2, ...]
def getIntfs( switch ):
    seq = switch.intfNames()
    sub = 'eth'
    ports = []
    for text in seq:
       if sub in text:
           ports.append(text)
    return ports

# get list of ports in switch with its names in OpenFlow ie. [1:s1-eth1, 2:s1-eth2, ...]
def getOFIntfNames( ports , switchName):
   port_desc = os.popen('ovs-ofctl -O OpenFlow13 dump-ports-desc '+switchName).read() 
   ofports = []
   for port in ports:
	for line in port_desc.split("\n"):
		if '('+port+')' in line:
		    ofports.append(line.lstrip()[0]+':'+port)
		    break	
   return ofports

def setVlanHosts(host1,host3):
   host1.cmd('modprobe 8021q')
   host1.cmd('vconfig add h1-eth0 300')
   host1.cmd('ip addr add 10.0.0.1/24 dev h1-eth0.300')
   host1.cmd('ip link set up h1-eth0.300')

   host3.cmd('modprobe 8021q')
   host3.cmd('vconfig add h3-eth0 300')
   host3.cmd('ip addr add 10.0.0.3/24 dev h3-eth0.300')
   host3.cmd('ip link set up h3-eth0.300')
   


if __name__ == '__main__':
    setLogLevel( 'info' )
   
    os.system('ovs-vsctl set-manager ptcp:6640')
    
    defaultIF1 = 's1-eth1'
    defaultIF2 = 's5-eth1'
    defaultControllerIP = '192.168.11.43'
    defaultInputSwitch = 0
    defaultOutputSwitch = 4

    if len( sys.argv ) > 1 and sys.argv[ 1 ]=='help':
	printHelp( defaultIF1, defaultIF2, defaultControllerIP, defaultInputSwitch, defaultOutputSwitch )

    # try to get hw intfs from the command line; by default, use eth1 and eth2
    intfName = sys.argv[ 1 ] if len( sys.argv ) > 1 else defaultIF1
    intfName2 = sys.argv[ 2 ] if len( sys.argv ) > 2 else defaultIF2
    odl_controller_ip = sys.argv[ 3 ] if len( sys.argv ) > 3 else defaultControllerIP	
    input_switch = sys.argv[ 4 ] if len( sys.argv ) > 4 else defaultInputSwitch
    output_switch = sys.argv[ 5 ] if len( sys.argv ) > 5 else defaultOutputSwitch

    OVSSwitch13 = partial( OVSSwitch, protocols='OpenFlow13' )
    
    topo=PocTopo( )
    net = Mininet( topo , switch=OVSSwitch13 , controller=partial( RemoteController, ip=odl_controller_ip, port=6633 ) )
    
    net.start()
    os.system('ovs-ofctl add-flow -O OpenFlow13 s'+str(input_switch+1)+' "priority=1000,actions=drop"')
    os.system('ovs-ofctl add-flow -O OpenFlow13 s'+str(output_switch+1)+' "priority=1000,actions=drop"')

    host1 = net.hosts[0]
    host3 = net.hosts[2]

    switch = net.switches[ input_switch ]
    switch2 = net.switches[ output_switch ]

    # setVlanHosts(host1,host3)
    # check if all flows are loaded
    while not isReady( switch, intfName, switch2, intfName2 ):
	time.sleep( 1 ) 	
 
    switch1Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch.name).read()
    switch2Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch2.name).read()

    os.system('ovs-ofctl -O OpenFlow13 del-flows s'+str(input_switch+1))
    os.system('ovs-ofctl -O OpenFlow13 del-flows s'+str(output_switch+1))

    switch1Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch.name).read()
    switch2Flows = os.popen('ovs-ofctl -O OpenFlow13 dump-flows '+switch2.name).read()

    CLI( net )
    net.stop()
