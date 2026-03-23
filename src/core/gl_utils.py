import numpy as np
import math
from OpenGL.GL import *
import ctypes

def create_shader(vertex_src, fragment_src):
    program = glCreateProgram()
    
    vs = glCreateShader(GL_VERTEX_SHADER)
    glShaderSource(vs, vertex_src)
    glCompileShader(vs)
    if not glGetShaderiv(vs, GL_COMPILE_STATUS):
        log = glGetShaderInfoLog(vs).decode()
        print(f"Vertex Shader Error: {log}")
        raise RuntimeError(f"Vertex Shader Compilation Error: {log}")
    
    fs = glCreateShader(GL_FRAGMENT_SHADER)
    glShaderSource(fs, fragment_src)
    glCompileShader(fs)
    if not glGetShaderiv(fs, GL_COMPILE_STATUS):
        log = glGetShaderInfoLog(fs).decode()
        print(f"Fragment Shader Error: {log}")
        raise RuntimeError(f"Fragment Shader Compilation Error: {log}")
        
    glAttachShader(program, vs)
    glAttachShader(program, fs)
    glLinkProgram(program)
    if not glGetProgramiv(program, GL_LINK_STATUS):
        log = glGetProgramInfoLog(program).decode()
        print(f"Link Error: {log}")
        raise RuntimeError(f"Program Linking Error: {log}")
        
    glDeleteShader(vs)
    glDeleteShader(fs)
    return program

def create_box(width, height, depth):
    w, h, d = width/2, height/2, depth/2
    vertices = np.array([
        -w, -h,  d,   w, -h,  d,   w,  h,  d,  -w,  h,  d, # Front
        -w, -h, -d,   w, -h, -d,   w,  h, -d,  -w,  h, -d  # Back
    ], dtype=np.float32)
    
    indices = np.array([
        0, 1, 2, 2, 3, 0, # Front
        1, 5, 6, 6, 2, 1, # Right
        5, 4, 7, 7, 6, 5, # Back
        4, 0, 3, 3, 7, 4, # Left
        3, 2, 6, 6, 7, 3, # Top
        4, 5, 1, 1, 0, 4  # Bottom
    ], dtype=np.uint32)
    
    return vertices, indices

def create_cylinder(radius, height, segments=32):
    vertices = []
    indices = []
    
    vertices.append([0, height/2, 0]) 
    vertices.append([0, -height/2, 0]) 
    
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        vertices.append([x, height/2, z]) 
        vertices.append([x, -height/2, z]) 
        
    vertices = np.array(vertices, dtype=np.float32)
    
    for i in range(segments):
        top_curr = 2 + i * 2
        bot_curr = 3 + i * 2
        top_next = 2 + ((i + 1) % segments) * 2
        bot_next = 3 + ((i + 1) % segments) * 2
        
        indices.extend([bot_curr, top_next, top_curr])
        indices.extend([bot_curr, bot_next, top_next])
        indices.extend([0, top_curr, top_next])
        indices.extend([1, bot_next, bot_curr])
        
    return vertices, np.array(indices, dtype=np.uint32)

class Mesh:
    def __init__(self, vertices, indices):
        self.vertices = vertices
        self.indices = indices
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.count = len(indices)

    def setup(self):
        if self.vao: return
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL_STATIC_DRAW)
        
        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices.nbytes, self.indices, GL_STATIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))
        
        glBindVertexArray(0)
        
    def draw(self):
        if not self.vao: self.setup()
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        
    def cleanup(self):
        if self.vao: glDeleteVertexArrays(1, [self.vao])
        if self.vbo: glDeleteBuffers(1, [self.vbo])
        if self.ebo: glDeleteBuffers(1, [self.ebo])

# Math Helpers
def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0: return v
    return v / norm

def cross(a, b):
    return np.cross(a, b)

def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m

def look_at(eye, center, up):
    f = normalize(center - eye)
    s = normalize(cross(f, up))
    u = cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[:3, 3] = -np.dot(m[:3, :3], eye) # Translation
    return m # Row-Major View Matrix

def translation_matrix(x, y, z):
    m = np.eye(4, dtype=np.float32)
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m

def rotation_matrix_x(angle):
    c = math.cos(angle)
    s = math.sin(angle)
    m = np.eye(4, dtype=np.float32)
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m
