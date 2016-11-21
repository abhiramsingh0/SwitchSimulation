"""
    A bit more detailed set of components to use in packet switching
    queueing experiments.
    Copyright 2014 Greg M. Bernstein
    Released under the MIT license
"""
import simpy
import random
from Params import port_rate, numOfVOQsPerPort, numOfOutputPorts, lk_delay

class Packet(object):
    """ A very simple class that represents a packet.
        This packet will run through a queue at a switch output port.
        We use a float to represent the size of the packet in bytes so that
        we can compare to ideal M/M/1 queues.

        Parameters
        ----------
        time : float
            the time the packet arrives at the output queue.
        size : float
            the size of the packet in bytes
        id : int
            an identifier for the packet
        src, dst : int
            identifiers for source and destination
        flow_id : int
            small integer that can be used to identify a flow
    """
    def __init__(self, time, size, id, src, dst, flow_id=0, portID=None, contentionDelay=0, lookupwait =0):
        self.time = time
        self.size = size
        self.id = id
        self.src = src
        self.dst = dst
        self.flow_id = flow_id
        self.portID = portID
        self.contentionDelay = contentionDelay
        self.lookupwait = lookupwait

    def __repr__(self):
        return "time: {}, id: {}, src: {}, dst: {}, size: {}".\
            format(self.time, self.id, self.portID, self.dst, self.size)

class PacketGenerator(object):
    """ Generates packets with given inter-arrival time distribution.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        adist : function
            a no parameter function that returns the successive inter-arrival times of the packets
        sdist : function
            a no parameter function that returns the successive sizes of the packets
        initial_delay : number
            Starts generation after an initial delay. Default = 0
        finish : number
            Stops generation at the finish time. Default is infinite


    """
    def __init__(self, env, id,  adist, sdist,active, initial_delay=0, finish=float("inf"), flow_id=0, portID=None):
        self.id = id
        self.env = env
        self.adist = adist
        self.sdist = sdist
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.packets_sent = 0
        self.bytes_sent=0
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.flow_id = flow_id
        self.start1time= env.now
        self.active = active
        self.portID = portID

    def run(self):
        """The generator function used in simulations.
        """
        if self.active:
            while self.env.now < self.finish:
            # wait for next transmission
                yield self.env.timeout(self.adist())
                self.packets_sent += 1
#                 src= random.randrange(0,16,1)
                dst = random.randrange(0,numOfOutputPorts)
#                 dst=0
#                p = Packet(self.env.now, self.sdist, self.packets_sent, src=self.id, dst=dst,  flow_id=self.flow_id)
                p = Packet(self.env.now, self.sdist, self.packets_sent, src=self.id, dst=dst,  flow_id=self.flow_id, portID=self.portID)
              #  print(p)
                self.bytes_sent+= p.size
                self.out.put(p)

class PacketSink(object):
    """ Receives packets and collects delay information into the
        waits list. You can then use this list to look at delay statistics.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        debug : boolean
            if true then the contents of each packet will be printed as it is received.
        rec_arrivals : boolean
            if true then arrivals will be recorded
        absolute_arrivals : boolean
            if true absolute arrival times will be recorded, otherwise the time between consecutive arrivals
            is recorded.
        rec_waits : boolean
            if true waiting time experienced by each packet is recorded
        selector: a function that takes a packet and returns a boolean
            used for selective statistics. Default none.

    """
    def __init__(self, env, rec_arrivals=False, absolute_arrivals=False, rec_waits=True, debug=False):
        self.store = simpy.Store(env)
        self.env = env
        self.rec_waits = rec_waits
        self.rec_arrivals = rec_arrivals
        self.absolute_arrivals = absolute_arrivals
        self.waits = []
        self.qWaits = []
        self.cWaits = []
        self.arrivals = []
        self.debug = debug
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.packets_rec = 0
        self.bytes_rec = 0

    def run(self):
        while True:
            msg = yield self.store.get()
            self.packets_rec += 1
            self.bytes_rec += msg.size

            if self.rec_waits:
                self.waits.append(self.env.now - msg.time)
                endTime = self.env.now
                genTime = msg.time
                transDelay = msg.size * 8.0 / port_rate
                lookupDelay = 55 * 6.5 * 10 ** -9
                contentionDelay = msg.contentionDelay
                self.cWaits.append(contentionDelay)
                if endTime - genTime - transDelay - lookupDelay - contentionDelay < 0:
                    self.qWaits.append(0)
                else:
                    self.qWaits.append(endTime - genTime - transDelay - lookupDelay - contentionDelay)

            if self.debug:
                print(msg)
    
    def put(self, pkt):
        self.store.put(pkt)

class VOQ(object):
    """ Models a switch output port with a given rate and buffer size limit in bytes.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the bit rate of the port
        qlimit : integer (or None)
            a buffer size limit in bytes for the queue (does not include items in service).

    """
    def __init__(self, env, rate, qlimit, debug=False, outputPorts=None):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_rec = 0
        self.packets_drop = 0
        self.qlimit = qlimit
        self.byte_size = 0  # Current size of the queue in bytes
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.count = 1
        self.outputPorts = outputPorts

    def run(self):
        while True:
            msg = yield self.store.get()
            self.byte_size -= msg.size
#            # check if destination port for is free
#            # and set wait time according to it
            with self.outputPorts[msg.dst].request() as req:
                t1 = self.env.now
                yield(req)
                msg.contentionDelay = self.env.now - t1
                yield self.env.timeout(msg.size * 8.0 / self.rate)
                self.out.put(msg)

            if self.debug:
                print(msg)

    def put(self, pkt):
        self.packets_rec += 1
        # find transmission delay for bits in front of queue
        #print("Switch port class put()={}".format(pkt)
        tr_delay = (self.byte_size * 8) / (self.rate)

        tmp = self.byte_size + pkt.size

        if self.qlimit is None:
            self.byte_size = tmp
            # insert delay info in packet
            pkt.delay2 = tr_delay

            return self.store.put(pkt)
        if tmp >= self.qlimit:
            self.packets_drop += 1
            return
        else:
            self.byte_size = tmp
            # insert delay info in packet
            pkt.delay2 = tr_delay

            return self.store.put(pkt)

class Port(object):
    """ Models a switch output port with a given rate and buffer size limit in bytes.
        Set the "out" member variable to the entity to receive the packet.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the bit rate of the port
        qlimit : integer (or None)
            a buffer size limit in bytes for the queue (does not include items in service).

    """
    def __init__(self, env, rate, qlimit, debug=False):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.outs = [None for _ in range(numOfVOQsPerPort)]
        self.packets_rec = 0
        self.packets_drop = 0
        self.qlimit = qlimit
        self.byte_size = 0  # Current size of the queue in bytes
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.lk_delay = lk_delay
        # tabel lookup delay for one packet
        #self.lk_delay = 55*6.5*10**-6


    def run(self):
        while True:
            msg = yield self.store.get()
            msg.lookupwait = self.env.now - msg.lookupwait
            self.busy = 1
            self.byte_size -= msg.size
            yield self.env.timeout(self.lk_delay)
            self.outs[msg.dst].put(msg)
            self.busy = 0
            if self.debug:
                print(msg)

    def put(self, pkt):
        self.packets_rec += 1
        pkt.lookupwait = self.env.now
        #print(len(self.store.items))

        # find loopup delay before inserting packet in input buffer
        #pkt.delay1= (len(self.store.items)+1) * self.lk_delay
        #print( self.store.items
        #print(pkt.delay1
        #print(pkt
        tmp = self.byte_size + pkt.size
        #print pkt
        if self.qlimit is None:
            self.byte_size = tmp
            return self.store.put(pkt)
        if tmp >= self.qlimit:
            self.packets_drop += 1
            #print('sidharth'
            return
        else:
            self.byte_size = tmp
            return self.store.put(pkt)


class SinkMonitor(object):
    """ A monitor for an SwitchSink. Looks at the number of items in the SwitchPort
        in service + in the queue and records that info in the sizes[] list. The
        monitor looks at the port at time intervals given by the distribution dist.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        port : SwitchPort
            the switch port object to be monitored.
        dist : function
            a no parameter function that returns the successive inter-arrival times of the packets

    """
    def __init__(self, env, sink, dist):
        self.sink = sink
        self.env = env
        self.dist = dist
        self.sizes = []
        self.var = []
        self.previous = 0
        #self.counter=0
        self.action = env.process(self.run())

    def run(self):
        while True:
            yield self.env.timeout(self.dist)
            total = self.sink.bytes_rec-self.previous
            #total = self.sink.packets_rec- self.previous
            self.sizes.append(total)
            #self.var.append(self.counter)
            self.previous=self.sink.bytes_rec
            #self.previous = self.sink.packets_rec
            #self.counter +=1
