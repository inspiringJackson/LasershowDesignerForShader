from dataclasses import dataclass, field
from typing import List
from enum import Enum
import math

class CurveType(Enum):
    SMOOTH = "smooth"
    HOLD = "hold"
    SINGLE_CURVE = "single_curve"
    STAIRS = "stairs"
    SMOOTH_STAIRS = "smooth_stairs"
    PULSE = "pulse"
    WAVE = "wave"

@dataclass
class Keyframe:
    time: float  # Relative to Sequence Start (in beats)
    value: float
    curve_type: CurveType = CurveType.SMOOTH
    tension: float = 0.0 # -1.0 to 1.0

@dataclass
class Sequence:
    start_time: float # Global beat time
    duration: float # In beats
    keyframes: List[Keyframe] = field(default_factory=list)
    # For Audio
    audio_file: str = ""
    audio_offset: float = 0.0 # Offset within the audio file
    
    def add_keyframe(self, time: float, value: float, curve: CurveType = CurveType.SMOOTH):
        # time is relative
        kf = Keyframe(time, value, curve)
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda x: x.time)

@dataclass
class Track:
    name: str
    track_type: str # "param" or "audio"
    target_laser: str = "" # Laser Source Name
    target_param: str = "" # Parameter Name (e.g., "brightness", "params.x")
    color: str = "#FF0000"
    sequences: List[Sequence] = field(default_factory=list) # For Audio Only
    keyframes: List[Keyframe] = field(default_factory=list) # For Param Only
    min_val: float = 0.0
    max_val: float = 1.0
    height: int = 60
    enabled: bool = True

    @staticmethod
    def calculate_value(k1: 'Keyframe', k2: 'Keyframe', t: float) -> float:
        v_start = k1.value
        v_end = k2.value
        delta = v_end - v_start
        
        ctype = k1.curve_type
        tension = k1.tension
        
        if ctype == CurveType.HOLD:
            return v_start
            
        elif ctype == CurveType.SMOOTH:
            # 0% (0.0) -> S-Curve (SmoothStep)
            # 100% (1.0) -> Linear
            
            # SmoothStep: 3t^2 - 2t^3
            val_smooth = t * t * (3 - 2 * t)
            val_linear = t
            
            # Mix based on tension
            # If tension is 0 -> val_smooth. If tension is 1 -> val_linear.
            factor = max(0.0, min(1.0, abs(tension)))
            t_mixed = val_smooth * (1.0 - factor) + val_linear * factor
            return v_start + delta * t_mixed
            
        elif ctype == CurveType.SINGLE_CURVE:
            # 0% -> Linear
            # 100% -> Ease In (Slow -> Fast)
            # -100% -> Ease Out (Fast -> Slow)
            
            if abs(tension) < 0.001:
                return v_start + delta * t
            
            exponent = 1.0
            if tension > 0:
                # Ease In: t^alpha, alpha > 1
                # Map 0..1 to 1..6?
                exponent = 1.0 + 5.0 * tension
                t_mapped = math.pow(t, exponent)
            else:
                # Ease Out: t^alpha, alpha < 1
                # Map -1..0 to 0.2..1
                # alpha = 1 / (1 + 5*|T|)
                exponent = 1.0 / (1.0 + 5.0 * abs(tension))
                t_mapped = math.pow(t, exponent)
                
            return v_start + delta * t_mapped
            
        elif ctype == CurveType.STAIRS:
            # 0% -> Linear
            # 100% -> 100 steps
            if abs(tension) < 0.01:
                return v_start + delta * t
                
            steps = max(1, round(abs(tension) * 100))
            t_mapped = math.floor(t * steps) / steps
            return v_start + delta * t_mapped
            
        elif ctype == CurveType.SMOOTH_STAIRS:
            if abs(tension) < 0.01:
                return v_start + delta * t
                
            steps = max(1, round(abs(tension) * 100))
            t_scaled = t * steps
            step_idx = math.floor(t_scaled)
            step_t = t_scaled - step_idx
            
            # Apply smoothstep to the fractional part
            step_t_smooth = step_t * step_t * (3 - 2 * step_t)
            
            t_mapped = (step_idx + step_t_smooth) / steps
            return v_start + delta * t_mapped
            
        elif ctype == CurveType.PULSE:
            # 0% -> Linear
            # 100% -> 100 waves starting from prev
            # -100% -> 100 waves starting from next
            if abs(tension) < 0.01:
                return v_start + delta * t
                
            count = max(1, round(abs(tension) * 100))
            cycle = t * count
            phase = cycle - math.floor(cycle)
            
            # Sine approximation for soft square wave
            raw_wave = math.sin(phase * 2 * math.pi)
            k = 10.0 # Steepness
            w = raw_wave * k
            w = max(-1.0, min(1.0, w)) # -1 to 1
            w = (w + 1.0) / 2.0 # 0 to 1
            
            if tension < 0:
                w = 1.0 - w
                
            t_mapped = w
            return v_start + delta * t_mapped
            
        elif ctype == CurveType.WAVE:
            # 0% -> Linear
            # 100% -> 100 Triangle waves
            # -100% -> 100 Sine waves
            if abs(tension) < 0.01:
                return v_start + delta * t
                
            count = max(1, round(abs(tension) * 100))
            cycle = t * count
            phase = cycle - math.floor(cycle)
            
            t_mapped = 0.0
            
            if tension > 0:
                # Triangle
                t_mapped = 1.0 - 2.0 * abs(phase - 0.5)
            else:
                # Sine
                t_mapped = (1.0 - math.cos(phase * 2 * math.pi)) / 2.0
                
            return v_start + delta * t_mapped
            
        # Default Linear
        return v_start + delta * t

    def get_value_at(self, beat: float) -> float:
        if not self.keyframes:
            return 0.0
            
        # 1. Check bounds
        if beat <= self.keyframes[0].time:
            return self.keyframes[0].value
        if beat >= self.keyframes[-1].time:
            return self.keyframes[-1].value
            
        # 2. Find segment
        for i in range(len(self.keyframes) - 1):
            k1 = self.keyframes[i]
            k2 = self.keyframes[i+1]
            
            if k1.time <= beat <= k2.time:
                duration = k2.time - k1.time
                if duration <= 0: return k1.value
                
                t = (beat - k1.time) / duration
                return self.calculate_value(k1, k2, t)
                    
        return 0.0

@dataclass
class LaserSource:
    name: str
    type: int # 0=Beam, 1=Fan, 2=Pattern, 3=Particle, 4=SolidFan
    # Standardized params array to map to GLSL struct
    # 0-2: Pos (vec3)
    # 3-5: Dir (vec3)
    # 6-8: Color (vec3)
    # 9: Brightness (float)
    # 10: Thickness (float)
    # 11: Divergence (float)
    # 12: Attenuation (float)
    # 13-16: Params (vec4)
    # 17-19: LocalUp (vec3)
    params: List[float] = field(default_factory=lambda: [
        1316.0, 50.0, 1600.0,   # Pos (Visible in front of camera)
        0.0, 1.0, 0.0,   # Dir (Up)
        1.0, 1.0, 1.0,   # Color
        2.0,             # Brightness
        2.0,             # Thickness (Thicker for visibility)
        0.0,             # Divergence
        0.1,             # Attenuation
        0.0, 0.0, 0.0, 0.0, # Params
        0.0, 0.0, 1.0    # LocalUp (Z+)
    ])
    
    # Master/Slave System
    is_master: bool = False
    master_id: str = "" # Name of the master laser
    subordinate_ids: List[str] = field(default_factory=list) # Names of subordinates in order
    
    # Offsets for subordinates (same structure as params)
    offset_params: List[float] = field(default_factory=lambda: [0.0] * 20)
    
    # Offset Mode for subordinates (0 = Sub + Offset, 1 = Master + Offset)
    # Same structure as params/offset_params
    offset_mode_params: List[float] = field(default_factory=lambda: [0.0] * 20)

import json
from dataclasses import asdict

# ... existing imports ...

@dataclass
class Project:
    bpm: float = 120.0
    time_signature: str = "4/4"
    beats_per_bar: int = 4
    total_measures: int = 120
    tracks: List[Track] = field(default_factory=list)
    lasers: List[LaserSource] = field(default_factory=list)

    def to_dict(self):
        # Helper to serialize Enum
        def convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            if hasattr(obj, "__dict__"):
                return {k: convert(v) for k, v in obj.__dict__.items()}
            return obj
        return convert(self)

    @staticmethod
    def from_dict(data):
        p = Project()
        p.bpm = data.get("bpm", 120.0)
        p.time_signature = data.get("time_signature", "4/4")
        
        # Prefer calculating beats_per_bar from time_signature to ensure consistency
        try:
            numerator = int(p.time_signature.split('/')[0])
            p.beats_per_bar = numerator
        except:
            p.beats_per_bar = data.get("beats_per_bar", 4)
            
        p.total_measures = data.get("total_measures", 120)
        
        # Load Lasers
        lasers_data = data.get("lasers", [])
        for l_data in lasers_data:
            l = LaserSource(name=l_data["name"], type=l_data["type"], params=l_data["params"])
            l.is_master = l_data.get("is_master", False)
            l.master_id = l_data.get("master_id", "")
            l.subordinate_ids = l_data.get("subordinate_ids", [])
            l.offset_params = l_data.get("offset_params", [0.0] * 20)
            l.offset_mode_params = l_data.get("offset_mode_params", [0.0] * 20)
            p.lasers.append(l)
            
        # Load Tracks
        tracks_data = data.get("tracks", [])
        for t_data in tracks_data:
            t = Track(
                name=t_data["name"], 
                track_type=t_data["track_type"],
                target_laser=t_data.get("target_laser", ""),
                target_param=t_data.get("target_param", ""),
                color=t_data.get("color", "#FF0000"),
                min_val=t_data.get("min_val", 0.0),
                max_val=t_data.get("max_val", 1.0),
                height=t_data.get("height", 60),
                enabled=t_data.get("enabled", True)
            )
            
            # Sequences (Audio)
            seqs_data = t_data.get("sequences", [])
            for s_data in seqs_data:
                s = Sequence(
                    start_time=s_data["start_time"],
                    duration=s_data["duration"],
                    audio_file=s_data.get("audio_file", ""),
                    audio_offset=s_data.get("audio_offset", 0.0)
                )
                # Keyframes for sequence (if any, though audio usually doesn't have kfs in this design)
                # But if we did:
                # s.keyframes = ...
                t.sequences.append(s)
                
            # Keyframes (Param)
            kfs_data = t_data.get("keyframes", [])
            for k_data in kfs_data:
                k = Keyframe(
                    time=k_data["time"],
                    value=k_data["value"],
                    curve_type=CurveType(k_data.get("curve_type", "smooth")),
                    tension=k_data.get("tension", 0.0)
                )
                t.keyframes.append(k)
                
            p.tracks.append(t)
            
        return p
