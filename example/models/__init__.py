#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

# los modelos estan definidos en el paquete "tipos"
from .root import Areas, Sedes
from .sede import Switches as Sede_Switches
from .sede import Vlans as Sede_Vlans
from .sede_switch import Puertos as Sede_Switch_Puertos
from .sede_vlan import Vlans as Sede_Vlan_Vlans
from .sede_vlan import Switches as Sede_Vlan_Switches
from .wan import WANs

