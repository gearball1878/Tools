from dataclasses import dataclass

@dataclass
class Port:
    id: str
    type: str

@dataclass
class Block:
    id: str
    ports: list

@dataclass
class Signal:
    id: str
    endpoints: list


# Ports
p_in = Port("IN", "in")
p_out = Port("OUT", "out")

# Block
block = Block("MyBlock", [p_in, p_out])

# Netze (wichtiger Punkt: eigene Objekte!)
net_in = Signal("NET_IN", ["EXT.IN", "MyBlock.IN"])
net_out = Signal("NET_OUT", ["MyBlock.OUT", "EXT.OUT"])

print(block)
print(net_in)
print(net_out)