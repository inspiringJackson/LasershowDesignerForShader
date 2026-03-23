from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QUrl
from PySide6.QtGui import QMouseEvent, QWheelEvent, QKeyEvent, QPainter, QColor, QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from OpenGL.GL import *
import numpy as np
import time
import os
import math
from core.gl_utils import create_shader, create_box, create_cylinder, Mesh, perspective, look_at, translation_matrix, normalize, cross
from core.exporter import GLSLExporter

class SimulatorWidget(QOpenGLWidget):
    time_updated = Signal(float) # Emits current time in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # State
        self.camera_pos = np.array([1316.0, 50.0, 1515.0], dtype=np.float32)
        self.camera_lon = 0.0
        self.camera_lat = 0.0
        self.camera_fov = 70.0
        self.u_time = 0.0
        self.MAX_LASERS = 100
        
        # Playback State
        self.is_playing = False
        self.current_time = 0.0 # Timeline time in seconds
        self.is_dirty = True # Data changed
        self.baked_mode = False
        self.baked_program = None
        self.realtime_program = None
        
        # Audio
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.has_audio = False
        
        self.keys_pressed = set()
        self.last_mouse_pos = QPoint()
        self.mouse_pressed = False
        
        # Resources
        self.props_program = None
        self.laser_program = None
        self.meshes = {}
        
        # Data
        self.project = None
        self.render_params = []
        
        # Animation Loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(16) # ~60 FPS
        self.last_time = time.time()
        
        # FPS
        self.fps = 0.0
        self.frame_count = 0
        self.last_fps_time = time.time()

        # Paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.shader_root = os.path.dirname(self.base_dir) 
        
    def set_project(self, project):
        self.project = project
        
        # Reset Playback State
        self.is_playing = False
        self.current_time = 0.0
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.has_audio = False
        self.is_dirty = True
        
        if self.isVisible():
            self.reload_laser_shader()

    def on_data_changed(self):
        """Called when project data changes"""
        self.is_dirty = True
        if self.is_playing:
            self.pause()

    def on_seek_requested(self):
        """Called when user seeks via other widgets"""
        if self.is_playing:
            self.pause()

    def pause(self):
        self.is_playing = False
        if self.has_audio:
            self.media_player.pause()
        # Switch back to realtime program for editing
        self.baked_mode = False
        self.update()

    def play_baked(self):
        # Generate baked shader if needed
        if self.is_dirty or not self.baked_program:
            exporter = GLSLExporter(self.project)
            code = exporter.export()
            
            # Compile baked shader
            success = self.compile_baked_shader(code)
            if success:
                self.is_dirty = False
            else:
                print("Failed to compile baked shader, falling back to realtime")
                # Fallback?
        
        if self.baked_program:
            self.baked_mode = True
            
        self.is_playing = True
        if self.has_audio:
            # Sync
            self.media_player.setPosition(int(self.current_time * 1000))
            self.media_player.play()
        self.last_time = time.time()
        self.update()

    def toggle_playback(self):
        if self.is_playing:
            self.pause()
        else:
            self.play_baked()

    def initializeGL(self):
        glClearColor(0.06, 0.06, 0.08, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        
        # Initialize Meshes
        box_v, box_i = create_box(4000, 1000, 4000)
        self.meshes['box'] = Mesh(box_v, box_i)
        
        c1_v, c1_i = create_cylinder(10, 222)
        self.meshes['c1'] = Mesh(c1_v, c1_i)
        
        c2_v, c2_i = create_cylinder(2, 71)
        self.meshes['c2'] = Mesh(c2_v, c2_i)
        
        c3_v, c3_i = create_cylinder(10, 205)
        self.meshes['c3'] = Mesh(c3_v, c3_i)
        
        c4_v, c4_i = create_cylinder(14, 262)
        self.meshes['c4'] = Mesh(c4_v, c4_i)
        
        # Upload data
        for m in self.meshes.values():
            m.setup()
            
        # Shaders
        self.init_shaders()
        
    def init_shaders(self):
        # Props Shader
        vs = """
        #version 330 core
        layout (location = 0) in vec3 position;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        void main() {
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
        """
        fs = """
        #version 330 core
        uniform vec3 color;
        out vec4 FragColor;
        void main() {
            FragColor = vec4(color, 1.0);
        }
        """
        try:
            self.props_program = create_shader(vs, fs)
        except RuntimeError as e:
            print(e)

        # Laser Shader - Load Default
        self.reload_laser_shader()

    def get_shader_content(self, filename):
        if filename == 'laser_lib.glsl':
            return """
#ifndef LASER_LIB_GLSL
#define LASER_LIB_GLSL

#define eps 1e-6
#define pi 3.14159265359
#define tau 6.28318530718
#define sqr(x) ((x)*(x))
float laser_length_sq(vec3 v) { return dot(v, v); }

struct Laser {
    vec3 pos;
    vec3 dir;
    vec3 localUp; // Used for orientation (Fan plane, Pattern up)
    
    vec3 color;
    float brightness;
    float thickness; // Beam radius (Type 0/1) or Pattern Scale (Type 2)
    
    float divergence; // 0.0 = Parallel, >0.0 = Spotlight/Projector
    
    float transparency;
    float attenuation;
    float maxDist;
    
    int type; 
    // 0: SINGLE_BEAM
    // 1: FAN (Discrete Beams)
    // 2: PATTERN (SDF Projector)
    // 3: PARTICLE (Noise/Hash based)
    // 4：SOLID_FAN (Continuous Sheet)
    
    vec4 params; 
    // Type 1 (Fan): x=Count (int), y=SpreadAngle (deg), z=Phase/Offset (deg), w=EffectID
    // Type 2 (Pattern): x=ShapeID (int), y=Rotation (deg), z=Fill/Param, w=EffectID
    // Type 3 (Particle): x=Seed, y=Spread, z=Speed, w=EffectID
};

// --- Math Helpers ---

vec3 hueToRgb(float h) {
    vec3 rgb = clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return rgb;
}

vec3 rotateVector(vec3 v, vec3 axis, float angle) {
    return mix(dot(axis, v) * axis, v, cos(angle)) + cross(axis, v) * sin(angle);
}

float hash12(vec2 p) {
    vec3 p3  = fract(vec3(p.xyx) * .1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// --- Noise Functions ---
float noise3D(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float n = i.x + i.y * 57.0 + i.z * 113.0;
    return mix(mix(mix(fract(sin(n + 0.0) * 43758.5453),
                       fract(sin(n + 1.0) * 43758.5453), f.x),
                   mix(fract(sin(n + 57.0) * 43758.5453),
                       fract(sin(n + 58.0) * 43758.5453), f.x), f.y),
               mix(mix(fract(sin(n + 113.0) * 43758.5453),
                       fract(sin(n + 114.0) * 43758.5453), f.x),
                   mix(fract(sin(n + 170.0) * 43758.5453),
                       fract(sin(n + 171.0) * 43758.5453), f.x), f.y), f.z);
}

// --- SDF Functions (2D) ---
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

float sdBox(vec2 p, vec2 b) {
    vec2 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

float sdTriangle(vec2 p, float r) {
    const float k = sqrt(3.0);
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if(p.x + k*p.y > 0.0) p = vec2(p.x - k*p.y, -k*p.x - p.y) / 2.0;
    p.x -= clamp(p.x, -2.0*r, 0.0);
    return -length(p) * sign(p.y);
}

float sdStar5(vec2 p, float r, float rf) {
    const vec2 k1 = vec2(0.809016994375, -0.587785252292);
    const vec2 k2 = vec2(-k1.x, k1.y);
    p.x = abs(p.x);
    p -= 2.0 * max(dot(k1, p), 0.0) * k1;
    p -= 2.0 * max(dot(k2, p), 0.0) * k2;
    p.x = abs(p.x);
    p.y -= r;
    vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0, 1);
    float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
    return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}

float sdHexagon(vec2 p, float r) {
    const vec3 k = vec3(-0.866025404, 0.5, 0.577350269);
    p = abs(p);
    p -= 2.0 * min(dot(k.xy, p), 0.0) * k.xy;
    p -= vec2(clamp(p.x, -k.z*r, k.z*r), r);
    return length(p) * sign(p.y);
}

float sdCrossFractal(vec2 p, float scale) {
    // 简化版本，使用迭代缩放
    float d = 1e6;
    float s = 1.0;
    
    for (int i = 0; i < 3; i++) {
        // 在每次迭代中创建自相似图案
        p = abs(p) - scale;
        p *= 1.5;
        
        // 简单的十字SDF
        float crossSize = scale * pow(0.7, float(i));
        vec2 q = p;
        q = abs(q) - crossSize;
        float crossDist = min(max(q.x, q.y), 0.0) + length(max(q, 0.0));
        
        d = min(d, crossDist * 0.5);
    }
    
    return d;
}

float sdSierpinski(vec2 p, float scale) {
    float r = scale;
    const vec2 va = vec2(0.0, 1.0);
    const vec2 vb = vec2(0.866, -0.5);
    const vec2 vc = vec2(-0.866, -0.5);
    
    float d = sdTriangle(p, r);
    
    // 3 Iterations
    for(int i=0; i<3; i++) {
        p.x = abs(p.x);
        p.y = -p.y; // flip
        // Fold
        if (p.x - 1.732*p.y > 0.0) p = vec2(p.x - 1.732*p.y, -1.732*p.x - p.y) * 0.5;
        p.x -= r;
        p.y += r; // shift
        r *= 0.5;
    }
    return length(p) - r;
}

// Get SDF distance for shape ID
float getShapeDist(int id, vec2 p, float scale) {
    float d = 1000.0;
    if (id == 0) d = sdCircle(p, scale);
    else if (id == 1) d = sdBox(p, vec2(scale));
    else if (id == 2) d = sdTriangle(p, scale);
    else if (id == 3) d = sdStar5(p, scale, scale * 0.5);
    else if (id == 4) d = sdHexagon(p, scale);
    else if (id == 5) d = sdBox(p, vec2(scale * 0.1, scale)); // Line
    else if (id == 6) { // Fractal - 使用简单的Sierpinski三角
        float tempScale = scale;
        p /= tempScale;
        
        // 简单的Sierpinski三角SDF
        float s = 1.0;
        for (int i = 0; i < 3; i++) {
            p = abs(p) - 0.5;
            p *= 2.0;
            s *= 2.0;
        }
        d = length(p) / s * tempScale;
    }
    return d;
}

// --- Color Effect Logic ---
vec3 applyColorEffect(vec3 baseColor, float t, float time, int effectID, float brightness) {
    vec3 color = baseColor;
    
    if (effectID == 1) { // Rainbow
        float phase = t * 0.05 - time * 2.0;
        color = hueToRgb(fract(phase)) * brightness;
    } 
    else if (effectID == 2) { // Gradient (Cyan-Purple)
        float phase = t * 0.02 - time;
        vec3 c1 = vec3(0.0, 1.0, 1.0);
        vec3 c2 = vec3(1.0, 0.0, 1.0);
        color = mix(c1, c2, sin(phase)*0.5+0.5) * brightness;
    }
    else if (effectID == 3) { // Strobe
        float strobe = step(0.5, sin(time * 30.0));
        color *= strobe;
    }
    else if (effectID == 4) { // Pulse
        float pulse = sin(time * 5.0) * 0.5 + 0.5;
        color *= (0.5 + 0.5 * pulse);
    }
    else if (effectID == 5) { // Color Cycle
        float phase = time * 0.5; // Slow cycle
        color = hueToRgb(fract(phase)) * brightness;
    }
    
    return color;
}

// --- Core Laser Logic ---

// Helper: Single Beam Contribution
vec3 getSingleBeamContribution(vec3 origin, vec3 dir, float maxDist, float thickness, float attenuation, 
                               vec3 camPos, vec3 viewDir, float maxViewDist, int effectType, float time, vec3 baseColor, float brightness) {
    vec3 p1 = camPos;
    vec3 d1 = viewDir;
    vec3 p2 = origin;
    vec3 d2 = dir;

    vec3 p12 = p2 - p1;
    float d1d2 = dot(d1, d2);
    float d1p12 = dot(d1, p12);
    float d2p12 = dot(d2, p12);

    float denom = 1.0 - d1d2 * d1d2;
    
    if (abs(denom) < eps) return vec3(0.0);

    float s = (d1p12 - d1d2 * d2p12) / denom;
    float t = (d2p12 - d1d2 * d1p12) / -denom;

    t = clamp(t, 0.0, maxDist);
    if (s < 0.0 || s > maxViewDist) return vec3(0.0);

    vec3 closestPointOnViewRay = p1 + s * d1;
    vec3 closestPointOnLaserRay = p2 + t * d2;
    float distSq = laser_length_sq(closestPointOnViewRay - closestPointOnLaserRay);

    float intensity = exp(-distSq / sqr(thickness));
    float atten = exp(-t * attenuation);
    
    vec3 finalColor = applyColorEffect(baseColor, t, time, effectType, brightness);
    
    return finalColor * intensity * atten;
}

vec3 getLaserContribution(Laser laser, vec3 cameraPos, vec3 viewDir, float maxViewDist, float time) {
    vec3 totalContribution = vec3(0.0);
    
    // Clamp brightness and color to be non-negative
    float brightness = max(laser.brightness, 0.0);
    vec3 color = max(laser.color, vec3(0.0));
    
    vec3 baseColor = color * brightness * laser.transparency;
    int effectType = int(laser.params.w);
    
    if (laser.type == 0) { // Single Beam
        totalContribution += getSingleBeamContribution(laser.pos, laser.dir, laser.maxDist, laser.thickness, laser.attenuation, cameraPos, viewDir, maxViewDist, effectType, time, baseColor, brightness * laser.transparency);
    } 
    else if (laser.type == 1) { // Fan
        int count = int(laser.params.x);
        float spread = radians(laser.params.y);
        float offset = radians(laser.params.z);
        vec3 axis = normalize(laser.localUp);
        
        float startAngle = -spread * 0.5 + offset;
        float stepAngle = (count > 1) ? spread / float(count - 1) : 0.0;
        
        for (int i = 0; i < 32; i++) { // Increased max loop
            if (i >= count) break;
            float angle = startAngle + float(i) * stepAngle;
            vec3 beamDir = rotateVector(laser.dir, axis, angle);
            totalContribution += getSingleBeamContribution(laser.pos, beamDir, laser.maxDist, laser.thickness, laser.attenuation, cameraPos, viewDir, maxViewDist, effectType, time, baseColor, brightness * laser.transparency);
        }
    }
    else if (laser.type == 2) { // Pattern (SDF)
        vec3 p1 = cameraPos;
        vec3 d1 = viewDir;
        vec3 p2 = laser.pos;
        vec3 d2 = laser.dir;
        
        // Closest point t on laser ray
        vec3 p12 = p2 - p1;
        float d1d2 = dot(d1, d2);
        float d1p12 = dot(d1, p12);
        float d2p12 = dot(d2, p12);
        float denom = 1.0 - d1d2 * d1d2;
        
        if (abs(denom) > eps) {
             float s_closest = (d1p12 - d1d2 * d2p12) / denom;
             if (s_closest < 0.0 || s_closest > maxViewDist) {
                 return totalContribution;
             }
             float marchStart = s_closest - 5.0;
             float marchEnd = s_closest + 5.0;
             if (marchStart < 0.0) marchStart = 0.0;
             if (marchEnd > maxViewDist) marchEnd = maxViewDist;
             
             vec3 forward = normalize(d2);
             vec3 up = normalize(laser.localUp);
             vec3 right = cross(forward, up);
             
             int steps = 16;
             float stepSize = (marchEnd - marchStart) / float(steps);
             float totalDensity = 0.0;
             
             for (int i = 0; i < 16; i++) {
                 float s = marchStart + float(i) * stepSize;
                 if (s < 0.0 || s > maxViewDist) continue;
                 vec3 pos = p1 + s * d1;
                 vec3 localPos = pos - laser.pos;
                 float z = dot(localPos, forward);
                 
                 if (z > 0.0 && z < laser.maxDist) {
                     float x = dot(localPos, right);
                     float y = dot(localPos, up);
                     vec2 uv = vec2(x, y);
                     
                     float rot = laser.params.y;
                     float cr = cos(rot); float sr = sin(rot);
                     uv = vec2(uv.x * cr - uv.y * sr, uv.x * sr + uv.y * cr);

                     float scale = laser.thickness;
                     if (laser.divergence > 0.001) scale = z * tan(laser.divergence * 0.5);
                     
                     int shapeID = int(laser.params.x);
                     float d = getShapeDist(shapeID, uv, scale);
                     
                     float fill = laser.params.z;
                     float edge = laser.thickness * 0.1; 
                     
                     float density = 0.0;
                     if (fill > 0.5) density = 1.0 - smoothstep(0.0, edge, d);
                     else density = 1.0 - smoothstep(0.0, edge, abs(d));
                     
                     density *= exp(-z * laser.attenuation);
                     totalDensity += density;
                 }
             }
             totalDensity *= stepSize * 0.1;
             
             // Apply color effect to pattern
             vec3 finalColor = applyColorEffect(baseColor, s_closest, time, effectType, brightness); // Approx t with s_closest
             totalContribution += totalDensity * finalColor;
        }
    }
    else if (laser.type == 3) { // Particle / Impractical FX
        // Use hash noise to simulate particles along the beam
        // Treat as a volumetric cylinder with noise density
        vec3 p1 = cameraPos;
        vec3 d1 = viewDir;
        vec3 p2 = laser.pos;
        vec3 d2 = laser.dir;
        
        vec3 p12 = p2 - p1;
        float d1d2 = dot(d1, d2);
        float d1p12 = dot(d1, p12);
        float d2p12 = dot(d2, p12);
        float denom = 1.0 - d1d2 * d1d2;
        
        if (abs(denom) > eps) {
            float s = (d1p12 - d1d2 * d2p12) / denom;
            float t = (d2p12 - d1d2 * d1p12) / -denom;
            
            if (s > 0.0 && s < maxViewDist && t > 0.0 && t < laser.maxDist) {
                 vec3 closestPointOnViewRay = p1 + s * d1;
                 vec3 closestPointOnLaserRay = p2 + t * d2;
                 float distSq = laser_length_sq(closestPointOnViewRay - closestPointOnLaserRay);
                 
                 // Cylinder check
                 if (distSq < sqr(laser.thickness * 4.0)) { // 4x thickness for particles
                     float seed = laser.params.x;
                     float speed = laser.params.z;
                     
                     // Sample multiple points along view ray near intersection
                     float density = 0.0;
                     for(int i=-2; i<=2; i++) {
                         vec3 samplePos = closestPointOnViewRay + d1 * float(i) * 0.5;
                         float h = hash12(samplePos.xz * 0.1 + vec2(time * speed, seed));
                         if (h > 0.95) density += 1.0;
                     }
                     
                     totalContribution += density * baseColor * exp(-t * laser.attenuation);
                 }
            }
        }
    }
    else if (laser.type == 4) { // SOLID_FAN (Continuous Sheet)
        // Params:
        // x: unused
        // y: Spread (Angle)
        // z: Offset (Rotation)
        // w: EffectID
        
        vec3 lDir = normalize(laser.dir);
        vec3 lUp = normalize(laser.localUp);
        
        vec3 right = cross(lDir, lUp);
        if (length(right) < 0.001) right = vec3(1.0, 0.0, 0.0);
        right = normalize(right);
        
        vec3 n = normalize(cross(right, lDir));
        
        vec3 p0 = laser.pos;
        vec3 ro = cameraPos;
        vec3 rd = viewDir;
        
        float denom = dot(n, rd);
        if (abs(denom) > 1e-4) { // Not parallel
            float t = dot(p0 - ro, n) / denom;
            if (t > 0.0 && t < maxViewDist) {
                 vec3 p = ro + rd * t; // Intersection point on plane
                 vec3 v = p - p0;      // Vector from origin to intersection
                 float dist = length(v);
                 
                 if (dist < laser.maxDist) {
                     // vec3 dir = normalize(laser.dir);
                     
                     // Calculate Angle relative to dir
                     // We need a basis on the plane: dir and right
                     // vec3 right = cross(dir, n);
                     vec3 v_norm = v / dist; // Normalized direction to intersection
                     
                     float cosAngle = dot(v_norm, lDir);
                     float sinAngle = dot(v_norm, right);
                     float ang = atan(sinAngle, cosAngle);
                     
                     float spread = radians(laser.params.y);
                     float offset = radians(laser.params.z);
                     
                     // Fan range: [offset - spread/2, offset + spread/2]
                     float halfSpread = spread * 0.5;
                     float lower = offset - halfSpread;
                     float upper = offset + halfSpread;
                     
                     // Smooth edges
                     float edge = 0.02; // Softness
                     float alpha = smoothstep(lower - edge, lower, ang) * (1.0 - smoothstep(upper, upper + edge, ang));
                     
                     if (alpha > 0.0) {
                         // Intensity depends on intersection depth (path length through sheet)
                         // Thickness T. Path = T / |dot(rd, n)|
                         float pathLen = laser.thickness / abs(denom);
                         pathLen = min(pathLen, 50.0); // Clamp max brightness at grazing angles
                         
                         vec3 col = applyColorEffect(baseColor, dist, time, effectType, brightness);
                         totalContribution += col * alpha * pathLen * exp(-dist * laser.attenuation);
                     }
                 }
            }
        }
    }
    
    return totalContribution;
}

// --- Motion Functions ---

vec3 getLinearMotion(vec3 start, vec3 end, float t) {
    return mix(start, end, t);
}

vec3 getCircularMotion(vec3 center, float radius, float speed, float time, vec3 axis) {
    // Arbitrary axis rotation
    vec3 base = vec3(radius, 0.0, 0.0);
    // Need a perpendicular vector to axis.
    vec3 up = vec3(0.0, 1.0, 0.0);
    if (abs(dot(axis, up)) > 0.9) up = vec3(1.0, 0.0, 0.0);
    vec3 u = normalize(cross(axis, up));
    vec3 v = cross(axis, u);
    
    float angle = time * speed;
    return center + u * cos(angle) * radius + v * sin(angle) * radius;
}

vec3 getLissajousMotion(vec3 center, vec2 amp, vec2 freq, float time, float phase) {
    float x = sin(time * freq.x + phase) * amp.x;
    float y = cos(time * freq.y) * amp.y;
    return center + vec3(x, y, 0.0); // Assume XY plane
}

vec3 getSpiralMotion(vec3 center, float radius, float speed, float climbSpeed, float time) {
    float angle = time * speed;
    float h = time * climbSpeed;
    return center + vec3(cos(angle)*radius, h, sin(angle)*radius);
}

vec3 getFigure8Motion(vec3 center, float size, float speed, float time) {
    float t = time * speed;
    return center + vec3(sin(t) * size, sin(t * 2.0) * size * 0.5, 0.0);
}

vec3 getRandomWalkMotion(vec3 start, float speed, float time, float scale) {
    // Use 3D noise to generate smooth random offsets
    float x = noise3D(vec3(time * speed, 0.0, 0.0));
    float y = noise3D(vec3(0.0, time * speed, 0.0));
    float z = noise3D(vec3(0.0, 0.0, time * speed));
    // noise3D returns 0..1, map to -1..1
    vec3 offset = (vec3(x, y, z) - 0.5) * 2.0;
    return start + offset * scale;
}

vec3 getSineWaveMotion(vec3 start, vec3 dir, float amp, float freq, float time) {
    // Move along dir, oscillate perpendicular
    // Create an arbitrary perpendicular vector
    vec3 up = vec3(0.0, 1.0, 0.0);
    if (abs(dot(normalize(dir), up)) > 0.9) up = vec3(1.0, 0.0, 0.0);
    vec3 right = normalize(cross(dir, up));
    
    float offset = sin(time * freq) * amp;
    return start + right * offset;
}

vec3 getKeyframeMotion(vec3 p0, vec3 p1, vec3 p2, vec3 p3, float time) {
    // Simple linear interpolation between 4 points based on time
    // time is expected to be 0..3 (or looped)
    float t = mod(time, 4.0);
    
    if (t < 1.0) return mix(p0, p1, smoothstep(0.0, 1.0, t));
    else if (t < 2.0) return mix(p1, p2, smoothstep(0.0, 1.0, t - 1.0));
    else if (t < 3.0) return mix(p2, p3, smoothstep(0.0, 1.0, t - 2.0));
    else return mix(p3, p0, smoothstep(0.0, 1.0, t - 3.0));
}

// --- Helper for Animations ---
float oscillate(float minVal, float maxVal, float frequency, float time, float phase) {
    float s = sin(time * tau * frequency + phase) * 0.5 + 0.5;
    return mix(minVal, maxVal, s);
}

#endif // LASER_LIB_GLSL
            """
        
        # Check potential paths
        paths = [
            os.path.join(self.shader_root, filename),
            os.path.join(self.base_dir, "shader", "include", "misc", filename)
        ]
        
        for path in paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        return "// Shader not found"

    def generate_laser_code(self):
        # Use Uniforms for real-time control
        return f"""
        #define MAX_LASERS {self.MAX_LASERS}
        
        struct LaserData {{
            vec3 pos;
            vec3 dir;
            vec3 color;
            float brightness;
            float thickness;
            float divergence;
            float attenuation;
            int type;
            vec4 params;
            vec3 localUp;
        }};
        
        uniform LaserData uLasers[MAX_LASERS];
        uniform int uLaserCount;
        
        vec3 drawLaserShow(vec3 cameraPos, vec3 viewDir, float maxDist, float time, vec3 bg) {{
            vec3 totalColor = bg;
            
            for(int i=0; i<uLaserCount; i++) {{
                Laser l;
                l.pos = uLasers[i].pos;
                l.dir = normalize(uLasers[i].dir);
                l.color = uLasers[i].color;
                l.brightness = uLasers[i].brightness;
                l.thickness = uLasers[i].thickness;
                l.divergence = uLasers[i].divergence;
                l.attenuation = uLasers[i].attenuation;
                l.type = uLasers[i].type;
                l.params = uLasers[i].params;
                l.localUp = uLasers[i].localUp;
                
                // Defaults
                l.maxDist = 2000.0;
                l.transparency = 1.0;
                
                totalColor += getLaserContribution(l, cameraPos, viewDir, maxDist, time);
            }}
            return totalColor;
        }}
        """

    def update_laser_uniforms(self):
        if not self.project or not self.realtime_program:
            return
            
        glUseProgram(self.realtime_program)
        
        # Count
        count = min(len(self.project.lasers), self.MAX_LASERS)
        loc = glGetUniformLocation(self.realtime_program, "uLaserCount")
        glUniform1i(loc, count)
        
        for i in range(count):
            laser = self.project.lasers[i]
            # Use render_params if available and valid, else raw params
            p = laser.params
            if i < len(self.render_params):
                p = self.render_params[i]
            
            # Helper to set uniform
            def set_u(name, val, is_int=False):
                l = glGetUniformLocation(self.realtime_program, f"uLasers[{i}].{name}")
                if l != -1:
                    if is_int: glUniform1i(l, int(val))
                    elif isinstance(val, (list, tuple)) and len(val) == 3: glUniform3f(l, *val)
                    elif isinstance(val, (list, tuple)) and len(val) == 4: glUniform4f(l, *val)
                    else: glUniform1f(l, float(val))

            set_u("pos", p[0:3])
            set_u("dir", p[3:6])
            set_u("color", p[6:9])
            set_u("brightness", p[9])
            set_u("thickness", p[10])
            set_u("divergence", p[11])
            set_u("attenuation", p[12])
            set_u("type", laser.type, is_int=True)
            set_u("params", p[13:17])
            set_u("localUp", p[17:20])

    def compile_baked_shader(self, custom_show_code):
        self.makeCurrent()
        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 position;
        
        uniform mat4 modelMatrix;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        
        out vec3 vWorldPosition;
        
        void main() {
            vec4 worldPosition = modelMatrix * vec4(position, 1.0);
            vWorldPosition = worldPosition.xyz;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
        """
        
        laser_lib = self.get_shader_content('laser_lib.glsl')
        
        fragment_src = f"""
        #version 330 core
        uniform float uTime;
        uniform vec3 cameraPosition;
        
        in vec3 vWorldPosition;
        out vec4 FragColor;
        
        {laser_lib}
        
        {custom_show_code}
        
        void main() {{
            vec3 viewDir = normalize(vWorldPosition - cameraPosition);
            // Pass uTime directly (seconds)
            vec3 color = drawLaserShow(cameraPosition, viewDir, 4000.0, uTime, vec3(0.0));
            FragColor = vec4(color, 1.0);
        }}
        """
        
        try:
            new_prog = create_shader(vertex_src, fragment_src)
            if self.baked_program:
                glDeleteProgram(self.baked_program)
            self.baked_program = new_prog
            print("Baked shader compiled successfully")
            self.doneCurrent()
            return True
        except RuntimeError as e:
            print(f"Baked shader failed: {e}")
            self.doneCurrent()
            return False

    def reload_laser_shader(self, custom_show_code=None):
        self.makeCurrent()
        vertex_src = """
        #version 330 core
        layout (location = 0) in vec3 position;
        
        uniform mat4 modelMatrix;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        
        out vec3 vWorldPosition;
        
        void main() {
            vec4 worldPosition = modelMatrix * vec4(position, 1.0);
            vWorldPosition = worldPosition.xyz;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
        """
        
        laser_lib = self.get_shader_content('laser_lib.glsl')
        
        if custom_show_code:
            laser_show = custom_show_code
        else:
            # Generate code from project
            laser_show = self.generate_laser_code()
        
        fragment_src = f"""
        #version 330 core
        uniform float uTime;
        uniform vec3 cameraPosition;
        
        in vec3 vWorldPosition;
        out vec4 FragColor;
        
        {laser_lib}
        
        {laser_show}
        
        void main() {{
            vec3 viewDir = normalize(vWorldPosition - cameraPosition);
            vec3 color = drawLaserShow(cameraPosition, viewDir, 4000.0, uTime / 24000.0, vec3(0.0));
            FragColor = vec4(color, 1.0);
        }}
        """
        
        try:
            new_prog = create_shader(vertex_src, fragment_src)
            if self.realtime_program:
                glDeleteProgram(self.realtime_program)
            self.realtime_program = new_prog
            print("激光着色器(Realtime)已重载")
            self.doneCurrent()
            self.update() # Force redraw
            return True
        except RuntimeError as e:
            print(f"激光着色器失败: {e}")
            self.doneCurrent()
            return False

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Decide which program to use
        program = self.realtime_program
        if self.baked_mode and self.baked_program:
            program = self.baked_program
            
        if not self.props_program or not program:
            return

        aspect = self.width() / self.height() if self.height() > 0 else 1.0
        proj_mat = perspective(self.camera_fov, aspect, 0.1, 5000.0)
        
        # Camera Vectors
        phi = math.radians(90 - self.camera_lat)
        theta = math.radians(self.camera_lon)
        dir_x = math.sin(phi) * math.sin(theta)
        dir_y = math.cos(phi)
        dir_z = math.sin(phi) * math.cos(theta)
        forward = np.array([dir_x, dir_y, dir_z], dtype=np.float32)
        
        view_mat = look_at(self.camera_pos, self.camera_pos + forward, np.array([0, 1, 0], dtype=np.float32))
        
        # 1. Draw Props
        glUseProgram(self.props_program)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glUniformMatrix4fv(glGetUniformLocation(self.props_program, "projectionMatrix"), 1, GL_TRUE, proj_mat)
        
        def draw_prop(name, x, y, z, r, g, b):
            if name not in self.meshes: return
            model = translation_matrix(x, y, z)
            mv = np.dot(view_mat, model) # Row Major: V * M
            glUniformMatrix4fv(glGetUniformLocation(self.props_program, "modelViewMatrix"), 1, GL_TRUE, mv)
            glUniform3f(glGetUniformLocation(self.props_program, "color"), r, g, b)
            self.meshes[name].draw()

        draw_prop('c1', 1317, 142, 2052, 1, 1, 1)
        draw_prop('c2', 1317, 288.5, 2052, 1, 1, 1) # 253 + 71/2
        draw_prop('c3', 1253, 133.5, 1420, 0, 0, 1)
        draw_prop('c4', 1391, 162, 1420, 1, 1, 1)
        
        # 2. Draw Laser
        if program:
            if program == self.realtime_program:
                self.update_laser_uniforms()
                
            glUseProgram(program)
            glBlendFunc(GL_ONE, GL_ONE) # Additive
            glDepthMask(GL_FALSE)
            
            box_model = translation_matrix(1317, 300, 1700)
            glUniformMatrix4fv(glGetUniformLocation(program, "modelMatrix"), 1, GL_TRUE, box_model)
            glUniformMatrix4fv(glGetUniformLocation(program, "modelViewMatrix"), 1, GL_TRUE, np.dot(view_mat, box_model))
            glUniformMatrix4fv(glGetUniformLocation(program, "projectionMatrix"), 1, GL_TRUE, proj_mat)
            
            glUniform1f(glGetUniformLocation(program, "uTime"), self.u_time)
            glUniform3fv(glGetUniformLocation(program, "cameraPosition"), 1, self.camera_pos)
            
            self.meshes['box'].draw()
            glDepthMask(GL_TRUE)
            
        # 3. Draw 2D Overlay (FPS)
        glUseProgram(0)
        
        # FPS Calculation
        self.frame_count += 1
        curr_time = time.time()
        if curr_time - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (curr_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = curr_time
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(10, self.height() - 10, f"FPS: {self.fps:.1f}")
        painter.end()

    def load_audio(self, file_path):
        if not file_path or not os.path.exists(file_path):
            self.has_audio = False
            self.media_player.setSource(QUrl())
            return
            
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.has_audio = True
        self.audio_output.setVolume(1.0) # Ensure volume is up
        
    def update_loop(self):
        curr_time = time.time()
        dt = curr_time - self.last_time
        self.last_time = curr_time
        
        # Determine current beat from timeline time
        bpm = 120.0
        if self.project and self.project.bpm > 0:
            bpm = self.project.bpm
        
        if self.is_playing:
            # Advance time
            # self.current_time += dt # Old logic
            
            # Handle Audio Sync logic
            if self.project:
                # Find active audio sequence
                current_beat = (self.current_time * bpm) / 60.0
                active_seq = None
                
                for track in self.project.tracks:
                    if track.track_type == "audio" and track.enabled:
                        for seq in track.sequences:
                            # Check overlap
                            if seq.start_time <= current_beat < (seq.start_time + seq.duration):
                                active_seq = seq
                                break
                        if active_seq: break
                
                if active_seq:
                    # We should be playing audio
                    # Check if player is playing right file
                    if not self.has_audio or self.media_player.source().toLocalFile() != active_seq.audio_file:
                        self.load_audio(active_seq.audio_file)
                        # Seek to correct start position
                        offset_in_beats = (current_beat - active_seq.start_time) + active_seq.audio_offset
                        offset_in_sec = (offset_in_beats * 60.0) / bpm
                        self.media_player.setPosition(int(offset_in_sec * 1000))
                        self.media_player.play()
                    
                    if self.media_player.playbackState() != QMediaPlayer.PlayingState:
                         # Start playing if not playing
                         offset_in_beats = (current_beat - active_seq.start_time) + active_seq.audio_offset
                         offset_in_sec = (offset_in_beats * 60.0) / bpm
                         self.media_player.setPosition(int(offset_in_sec * 1000))
                         self.media_player.play()
                         # Still increment by dt for this frame until audio starts
                         self.current_time += dt
                    else:
                        # Audio IS playing, use it as master clock
                        player_pos = self.media_player.position() / 1000.0
                        
                        # Convert player_pos back to timeline time
                        # Timeline Time = Sequence Start Time (sec) + (Player Pos - Audio Offset (sec))
                        # Note: Audio Offset is in beats in model, converted to sec
                        
                        seq_start_sec = (active_seq.start_time * 60.0) / bpm
                        audio_offset_sec = (active_seq.audio_offset * 60.0) / bpm
                        
                        # Correct logic:
                        # Player Pos corresponds to position WITHIN audio file.
                        # Audio starts playing at timeline time: seq_start_sec
                        # Audio file starts at offset: audio_offset_sec (meaning we skip first X sec of audio file)
                        # So Player Pos 0 = Timeline Time seq_start_sec (if offset=0)
                        
                        # Actually:
                        # If audio_offset is 0:
                        # Timeline: S .......
                        # Audio:    0 .......
                        # So Timeline = S + PlayerPos
                        
                        # If audio_offset is O (skip O sec of audio):
                        # Timeline: S .......
                        # Audio:    O .......
                        # PlayerPos will be O + elapsed.
                        # So Timeline = S + (PlayerPos - O)
                        
                        new_time = seq_start_sec + (player_pos - audio_offset_sec)
                        
                        # Smooth update? If jitter is high.
                        # For now, trust audio clock.
                        # Check if new_time is reasonable (not jumping backwards too much or forwards)
                        if abs(new_time - self.current_time) < 0.5:
                            self.current_time = new_time
                        else:
                            # Too big jump, maybe loop or seek? Trust audio.
                            self.current_time = new_time
                            
                else:
                    # No active audio, pause player if playing
                    if self.media_player.playbackState() == QMediaPlayer.PlayingState:
                        self.media_player.pause()
                    
                    # Use system clock
                    self.current_time += dt

            self.time_updated.emit(self.current_time)
            
        self.u_time = self.current_time # Sync u_time to timeline
        
        if self.project:
            bpm = self.project.bpm
            if bpm <= 0: bpm = 120.0
            current_beat = (self.current_time * bpm) / 60.0
            
            for track in self.project.tracks:
                if track.track_type == "audio" or not track.target_laser:
                    continue
                
                # Resolve Laser Object from Name
                laser = None
                for l in self.project.lasers:
                    if l.name == track.target_laser:
                        laser = l
                        break
                if not laser: continue

                val = track.get_value_at(current_beat)
                
                # Apply value based on param_type
                pt = track.target_param
                
                if pt == "is_master":
                    laser.is_master = (val > 0.5)
                    continue

                # Determine target array (params or offset_params)
                target_arr = laser.params
                real_pt = pt
                
                if pt.startswith("offset_mode_"):
                    target_arr = laser.offset_mode_params
                    real_pt = pt[12:]
                elif pt.startswith("offset_"):
                    target_arr = laser.offset_params
                    real_pt = pt[7:]
                
                # Helper to set value with conversion
                def set_v(idx, v, needs_rad=False, needs_col=False):
                    if needs_col: target_arr[idx] = v / 255.0
                    elif needs_rad: target_arr[idx] = math.radians(v)
                    else: target_arr[idx] = v

                if real_pt == "pos.x": set_v(0, val)
                elif real_pt == "pos.y": set_v(1, val)
                elif real_pt == "pos.z": set_v(2, val)
                elif real_pt == "dir.x": set_v(3, val)
                elif real_pt == "dir.y": set_v(4, val)
                elif real_pt == "dir.z": set_v(5, val)
                elif real_pt == "color.r": set_v(6, val, needs_col=True)
                elif real_pt == "color.g": set_v(7, val, needs_col=True)
                elif real_pt == "color.b": set_v(8, val, needs_col=True)
                elif real_pt == "brightness": set_v(9, val)
                elif real_pt == "thickness": set_v(10, val)
                elif real_pt == "divergence": set_v(11, val, needs_rad=True)
                elif real_pt == "attenuation": set_v(12, val)
                elif real_pt == "params.x": set_v(13, val)
                elif real_pt == "params.y": set_v(14, val)
                elif real_pt == "params.z": set_v(15, val)
                elif real_pt == "params.w": set_v(16, val)
                elif real_pt == "localUp.x": set_v(17, val)
                elif real_pt == "localUp.y": set_v(18, val)
                elif real_pt == "localUp.z": set_v(19, val)
                elif real_pt == "type": laser.type = int(val)
        
        # Prepare Render Params (Copy base params)
        self.render_params = [list(l.params) for l in self.project.lasers]
        
        # Apply Master/Slave Logic to Render Params
        laser_map_idx = {l.name: i for i, l in enumerate(self.project.lasers)}
        
        for i, l in enumerate(self.project.lasers):
            if l.is_master:
                for sub_order_idx, sub_name in enumerate(l.subordinate_ids):
                    if sub_name not in laser_map_idx: continue
                    sub_idx = laser_map_idx[sub_name]
                    
                    # We modify self.render_params[sub_idx]
                    for k in range(20):
                        mode = l.offset_mode_params[k] if k < len(l.offset_mode_params) else 0.0
                        offset = l.offset_params[k] * (sub_order_idx + 1)
                        
                        if mode > 0.5: # Switch ON: Master + Offset
                            # Use Master's RENDER param (so if master is animated, sub follows)
                            # Master is at index i
                            self.render_params[sub_idx][k] = self.render_params[i][k] + offset
                        else: # Switch OFF: Sub + Offset
                            # Use Sub's RENDER param (which is currently Base)
                            self.render_params[sub_idx][k] = self.render_params[sub_idx][k] + offset

        # Camera Move
        speed = 100.0 * dt
        if Qt.Key.Key_Control in self.keys_pressed: speed *= 3.0
        
        phi = math.radians(90 - self.camera_lat)
        theta = math.radians(self.camera_lon)
        forward = np.array([
            math.sin(phi) * math.sin(theta),
            math.cos(phi),
            math.sin(phi) * math.cos(theta)
        ], dtype=np.float32)
        right = normalize(cross(forward, np.array([0, 1, 0], dtype=np.float32)))
        
        if Qt.Key.Key_W in self.keys_pressed: self.camera_pos += forward * speed
        if Qt.Key.Key_S in self.keys_pressed: self.camera_pos -= forward * speed
        if Qt.Key.Key_A in self.keys_pressed: self.camera_pos -= right * speed
        if Qt.Key.Key_D in self.keys_pressed: self.camera_pos += right * speed
        if Qt.Key.Key_Space in self.keys_pressed: self.camera_pos[1] += speed
        if Qt.Key.Key_Shift in self.keys_pressed: self.camera_pos[1] -= speed
        
        self.update() # Trigger paintGL

    def toggle_playback(self):
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            if self.has_audio:
                # Seek to current time before playing to ensure sync
                # But QMediaPlayer.play() might resume from last pos.
                # If current_time was changed by seek, we need to update player.
                self.media_player.setPosition(int(self.current_time * 1000))
                self.media_player.play()
        else:
            if self.has_audio:
                self.media_player.pause()
        
    def set_time(self, time_sec):
        # Pause if playing (user seek)
        if self.is_playing:
            self.pause()
            
        self.current_time = max(0.0, time_sec)
        self.u_time = self.current_time
        
        if self.has_audio:
             # If dragging scrubber while playing, this might stutter. 
             # Usually we seek but don't pause if playing.
             self.media_player.setPosition(int(self.current_time * 1000))
             
        self.time_updated.emit(self.current_time)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_playback()
            return
            
        self.keys_pressed.add(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = True
            self.last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouse_pressed:
            dx = event.pos().x() - self.last_mouse_pos.x()
            dy = event.pos().y() - self.last_mouse_pos.y()
            
            self.camera_lon += dx * 0.1
            self.camera_lat += dy * 0.1
            self.camera_lat = max(-89.9, min(89.9, self.camera_lat))
            
            self.last_mouse_pos = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.camera_fov -= delta * 0.05
        self.camera_fov = max(10, min(120, self.camera_fov))
        self.update()
