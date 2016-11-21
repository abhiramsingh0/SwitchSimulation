from Params import *
import simpy
import numpy as np
from SimComponents import PacketGenerator, PacketSink, VOQ, Port
from simpy.resources.resource import Resource

def expArrivals():  # Constant arrival distribution for generator
    return (mean_pkt_size * 8 / port_rate)    # in seconds

x = [0]*numOfInputPorts
for numOfGenerators in range(num_gen):
    x[numOfGenerators] = 1

env = simpy.Environment()

inputPorts = [None for _ in range(numOfInputPorts)]
voq = [[None] * numOfVOQsPerPort for _ in range(numOfInputPorts)]
outputPorts = [Resource(env, capacity=1) for _ in range(numOfOutputPorts)]
pg = [None for _ in range(numOfInputPorts)]    # list that contains packet generator threads
ps = PacketSink(env, debug=False, rec_waits=True)

for inputPortID in range(numOfInputPorts):
    inputPorts[inputPortID]= Port(env, port_rate, qlimit_edgeports)
    pg[inputPortID] = PacketGenerator(env, "SJSU1", expArrivals, sdist, x[inputPortID], portID=inputPortID)
    pg[inputPortID].out = inputPorts[inputPortID]

    for voqID in range(numOfVOQsPerPort):
        voq[inputPortID][voqID] = VOQ(env, port_rate, qlimit_voq, outputPorts=outputPorts)
        inputPorts[inputPortID].outs[voqID] = voq[inputPortID][voqID]
        voq[inputPortID][voqID].out = ps

env.run(until=sim_time)

totalPktsGenerated = sum(pg[pktGenID].packets_sent for pktGenID in range(numOfInputPorts))
totalPktsRecdAcrossAllPorts = sum(inputPorts[inputPortID].packets_rec for inputPortID in range(numOfInputPorts))
totalPktsDroppedAcrossAllPorts = sum(inputPorts[inputPortID].packets_drop for inputPortID in range(numOfInputPorts))
totalPktsRecdAcrossAllVOQs = sum(voq[inputPortID][VOQid].packets_rec for inputPortID in range(numOfInputPorts) for VOQid in range(numOfVOQsPerPort))
totalPktsDroppedAcrossAllVOQs = sum(voq[inputPortID][VOQid].packets_drop for inputPortID in range(numOfInputPorts) for VOQid in range(numOfVOQsPerPort))

print('List of parameters:')
print("\tNumber of active input inputPorts = {}".format(x.count(1)))
print("\tInput data rate = {}".format(port_rate))
print("\tInput avg. packet size = {} bytes".format(mean_pkt_size))
print("\t1st level buffer size = {} packets".format(int(qlimit_edgeports/mean_pkt_size)))
print("\tVOQ buffer size = {} packets".format(int(qlimit_voq/mean_pkt_size)))

print('Results:')
print("\tTotal packets  generated = {}".format(totalPktsGenerated))
print("\tTotal packets received and dropped across all inputs inputPorts = {}, {}".format(totalPktsRecdAcrossAllPorts, totalPktsDroppedAcrossAllPorts))
print("\tTotal packets received and dropped across all VOQs = {}, {}".format(totalPktsRecdAcrossAllVOQs, totalPktsDroppedAcrossAllVOQs))
print("\tTotal packets received at sink = {}".format(ps.packets_rec))
print("\tAvg. port to port latency = {}".format(np.mean(ps.waits)))
    
print(mean_pkt_size, 55*6.5*10**-9, np.mean(ps.qWaits), np.mean(ps.cWaits), mean_pkt_size*8/port_rate, np.mean(ps.waits))