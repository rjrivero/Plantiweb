#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

# los modelos estan definidos en el paquete "tipos"
from .root import Areas, Sedes
from .sede import Sede_Switches, Sede_Vlans
from .sede_switch import Sede_Switch_Puertos
from .sede_vlan import Sede_Vlan_Vlans, Sede_Vlan_Switches
from .wan import WANs

