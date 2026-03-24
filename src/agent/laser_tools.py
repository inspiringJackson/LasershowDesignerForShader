from typing import List, Dict, Any, Optional, Union
from core.models import LaserSource, Project
from core.commands import AddItemCommand, RemoveItemCommand, PropertyChangeCommand, ListPropertyChangeCommand, BatchCommand

class LaserAgentTools:
    """
    A collection of tools for the AI Agent to manipulate laser sources in the project.
    All actions are pushed to the main_window's QUndoStack to ensure undo/redo compatibility.
    """
    
    # Mapping of property names to indices in LaserSource.params
    PARAM_MAP = {
        "pos.x": 0, "pos.y": 1, "pos.z": 2,
        "dir.x": 3, "dir.y": 4, "dir.z": 5,
        "color.r": 6, "color.g": 7, "color.b": 8,
        "brightness": 9,
        "thickness": 10,
        "divergence": 11,
        "attenuation": 12,
        "params.x": 13, "params.y": 14, "params.z": 15, "params.w": 16,
        "localUp.x": 17, "localUp.y": 18, "localUp.z": 19
    }

    def __init__(self, main_window):
        self.main_window = main_window
        self.project: Project = main_window.project
        self.undo_stack = main_window.undo_stack

    def _get_laser_by_name(self, name: str) -> Optional[LaserSource]:
        for l in self.project.lasers:
            if l.name == name:
                return l
        return None

    def _get_laser_index(self, name: str) -> int:
        for i, l in enumerate(self.project.lasers):
            if l.name == name:
                return i
        return -1

    def add_laser(self, name: str, laser_type: int = 0, 
                  pos: List[float] = None, dir_vec: List[float] = None, 
                  color: List[float] = None, brightness: float = 2.0, 
                  thickness: float = 2.0, divergence: float = 0.0, 
                  attenuation: float = 0.1, params: List[float] = None, 
                  local_up: List[float] = None) -> bool:
        """
        Add a new laser source to the scene.
        :param name: Unique name of the laser.
        :param laser_type: 0=Beam, 1=Fan, 2=Pattern, 3=Particle, 4=SolidFan.
        :param pos: [x, y, z] position (default: [0, 50, 0]).
        :param dir_vec: [dx, dy, dz] direction (default: [0, 1, 0]).
        :param color: [r, g, b] color values 0.0 to 1.0 (default: [1, 1, 1]).
        :param brightness: 0.0 to 10.0 (default: 2.0).
        :param thickness: Beam thickness (default: 2.0).
        :param divergence: Divergence angle in radians (default: 0.0).
        :param attenuation: Light attenuation (default: 0.1).
        :param params: [x, y, z, w] extra params (default: [0, 0, 0, 0]).
        :param local_up: [ux, uy, uz] up vector (default: [0, 0, 1]).
        :return: True if successful, False if name already exists.
        """
        if self._get_laser_by_name(name):
            return False # Name must be unique
            
        p = [0.0] * 20
        # Default values
        p[0:3] = pos if pos is not None and len(pos) == 3 else [0.0, 50.0, 0.0]
        p[3:6] = dir_vec if dir_vec is not None and len(dir_vec) == 3 else [0.0, 1.0, 0.0]
        p[6:9] = color if color is not None and len(color) == 3 else [1.0, 1.0, 1.0]
        p[9] = brightness
        p[10] = thickness
        p[11] = divergence
        p[12] = attenuation
        p[13:17] = params if params is not None and len(params) == 4 else [0.0, 0.0, 0.0, 0.0]
        p[17:20] = local_up if local_up is not None and len(local_up) == 3 else [0.0, 0.0, 1.0]

        new_laser = LaserSource(name=name, type=laser_type, params=p)
        cmd = AddItemCommand(self.project.lasers, new_laser, f"Add Laser {name}", self.main_window)
        self.undo_stack.push(cmd)
        return True

    def remove_laser(self, name: str) -> bool:
        """
        Remove a laser source by name.
        :param name: Name of the laser to remove.
        :return: True if successful, False if not found.
        """
        idx = self._get_laser_index(name)
        if idx == -1:
            return False
            
        laser = self.project.lasers[idx]
        cmd = RemoveItemCommand(self.project.lasers, idx, laser, f"Remove Laser {name}", self.main_window)
        self.undo_stack.push(cmd)
        return True

    def set_laser_properties(self, name: str, properties: Dict[str, Any]) -> bool:
        """
        Modify multiple properties of a laser source at once.
        :param name: Name of the laser.
        :param properties: Dictionary of properties to change. 
                           Keys can be "name", "type", or param names like "pos.x", "color.r", "brightness", etc.
        :return: True if successful, False if laser not found.
        """
        laser = self._get_laser_by_name(name)
        if not laser:
            return False

        commands = []
        for key, new_val in properties.items():
            if key in ["name", "type"]:
                old_val = getattr(laser, key)
                if old_val != new_val:
                    cmd = PropertyChangeCommand(laser, key, old_val, new_val, f"Change {name} {key}", self.main_window)
                    commands.append(cmd)
            elif key in self.PARAM_MAP:
                idx = self.PARAM_MAP[key]
                old_val = laser.params[idx]
                if old_val != new_val:
                    cmd = ListPropertyChangeCommand(laser.params, idx, old_val, float(new_val), f"Change {name} {key}", self.main_window)
                    commands.append(cmd)
            else:
                # Handle compound properties like 'pos', 'dir', 'color' if passed as lists
                if key in ["pos", "dir", "color", "localUp", "params", "local_up", "dir_vec"] and isinstance(new_val, list):
                    real_key = key
                    if key == "local_up": real_key = "localUp"
                    if key == "dir_vec": real_key = "dir"
                    
                    if real_key == "color": components = ["r", "g", "b"]
                    elif real_key == "params": components = ["x", "y", "z", "w"]
                    else: components = ["x", "y", "z"]
                    
                    for i, comp in enumerate(components):
                        if i < len(new_val):
                            sub_key = f"{real_key}.{comp}"
                            idx = self.PARAM_MAP[sub_key]
                            old_v = laser.params[idx]
                            new_v = float(new_val[i])
                            if old_v != new_v:
                                cmd = ListPropertyChangeCommand(laser.params, idx, old_v, new_v, f"Change {name} {sub_key}", self.main_window)
                                commands.append(cmd)
        
        if commands:
            batch_cmd = BatchCommand(commands, f"Update properties for {name}", self.main_window)
            self.undo_stack.push(batch_cmd)
            
        return True

    def set_laser_type(self, name: str, laser_type: int) -> bool:
        """
        Change the type of a laser source.
        :param name: Name of the laser.
        :param laser_type: 0=Beam, 1=Fan, 2=Pattern, 3=Particle, 4=SolidFan.
        :return: True if successful, False if not found.
        """
        return self.set_laser_properties(name, {"type": laser_type})

    def setup_master_slave(self, master_name: str, subordinate_names: List[str], 
                           offset_params: Dict[str, float] = None, 
                           offset_modes: Dict[str, int] = None) -> bool:
        """
        Configure a master-slave array synchronization for a laser.
        :param master_name: Name of the master laser.
        :param subordinate_names: List of names of subordinate lasers.
        :param offset_params: Dictionary of parameter offsets per subordinate (e.g. {"pos.x": 10.0}).
        :param offset_modes: Dictionary of offset modes per param (0=Sub+Offset, 1=Master+Offset).
        :return: True if successful, False if master laser not found.
        """
        master_laser = self._get_laser_by_name(master_name)
        if not master_laser:
            return False

        commands = []
        
        # Enable master mode
        if not master_laser.is_master:
            commands.append(PropertyChangeCommand(master_laser, "is_master", master_laser.is_master, True, f"Enable Master for {master_name}", self.main_window))
            
        # Set subordinates
        if master_laser.subordinate_ids != subordinate_names:
            commands.append(PropertyChangeCommand(master_laser, "subordinate_ids", master_laser.subordinate_ids.copy(), subordinate_names.copy(), f"Set subordinates for {master_name}", self.main_window))

        # Apply offset parameters
        if offset_params:
            for key, val in offset_params.items():
                if key in self.PARAM_MAP:
                    idx = self.PARAM_MAP[key]
                    old_val = master_laser.offset_params[idx]
                    if old_val != float(val):
                        commands.append(ListPropertyChangeCommand(master_laser.offset_params, idx, old_val, float(val), f"Set {master_name} offset {key}", self.main_window))

        # Apply offset modes
        if offset_modes:
            for key, val in offset_modes.items():
                if key in self.PARAM_MAP:
                    idx = self.PARAM_MAP[key]
                    old_val = master_laser.offset_mode_params[idx]
                    if old_val != float(val):
                        commands.append(ListPropertyChangeCommand(master_laser.offset_mode_params, idx, old_val, float(val), f"Set {master_name} offset mode {key}", self.main_window))

        # Link subordinates to master
        for sub_name in subordinate_names:
            sub_laser = self._get_laser_by_name(sub_name)
            if sub_laser and sub_laser.master_id != master_name:
                commands.append(PropertyChangeCommand(sub_laser, "master_id", sub_laser.master_id, master_name, f"Link {sub_name} to {master_name}", self.main_window))

        if commands:
            batch_cmd = BatchCommand(commands, f"Setup Master-Slave for {master_name}", self.main_window)
            self.undo_stack.push(batch_cmd)
            
        return True
