﻿import numpy as np
import OpenGL.GL as gl
import math
import transforms
import ctypes

cache = {}

class base(object):
    """Base class for 2d geometries with modelview and projection transforms"""    
    
    version = """#version 300 es\n"""

    defines = """"""
    
    vertex_code = """
        uniform mat4 modelview;
        uniform mat4 projection;
        uniform vec4 objcolor;

        in highp vec4 color;
        in highp vec2 position;
        out highp vec4 v_color;
        void main()
        {
            gl_Position = projection * modelview * vec4(position,0.0,1.0);
            v_color =  objcolor * color;
        } """

    fragment_code = """
        in highp vec4 v_color;
        out highp vec4 f_color;

        void main()
        {
            f_color = v_color;
        } """

    attributes = { 'color' : 4, 'position' : 2 }
    uniforms = { }
    instanceAttributes = {}
    primitive = gl.GL_TRIANGLES
    srcblend = gl.GL_SRC_ALPHA
    dstblend = gl.GL_ONE_MINUS_SRC_ALPHA

    program = None

    def __init__(self):
        global cache

        # Cache the program based on the class name
        if self.__class__.__name__ in cache:
            self.program = cache[self.__class__.__name__]
        else:
            self.program = self.loadShaderProgram()
            cache[self.__class__.__name__] = self.program

        identity = np.eye(4, dtype=np.float32)
        self.setModelView(identity);
        self.setProjection(identity);
        (self.vertexBuffer, self.vertices, self.offsets, self.stride) = self.loadGeometry()
        (self.instanceBuffer, self.instances, self.instanceOffsets, self.instanceStride) = self.loadInstances()
        self.color = (1,1,1,1)

    def __del__(self):
        gl.glDeleteBuffers(1, [self.vertexBuffer])

    def getVertices(self):
        """Override for useful geometry"""
        return { 'color' : [], 'position' : [] }
        
    def getInstances(self):
        """Override for instancing"""
        return {}

    def getUniforms(self):
        """Override for uniforms"""
        return {}

    def getTextures(self):
        """Override for texture samplers"""
        return {}
        
    def reloadInstanceData(self):
        self.instances = self.loadAttribData(self.instanceBuffer, self.instanceAttributes, self.getInstances())
        
    def loadShaderProgram(self):
        # Request a program and shader slots from GPU
        program  = gl.glCreateProgram()
        vertex   = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        fragment = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)

        # Set shaders source
        gl.glShaderSource(vertex, self.version + self.defines + self.vertex_code)
        gl.glShaderSource(fragment, self.version + self.defines + self.fragment_code)

        # Compile shaders
        gl.glCompileShader(vertex)
        gl.glCompileShader(fragment)
        log = gl.glGetShaderInfoLog(vertex)
        if log:
            print('Vertex shader')
            print(self.vertex_code)
            print(log.decode('ascii'))
            raise RuntimeError('Shader compiliation failed')
        log = gl.glGetShaderInfoLog(fragment)
        if log:
            print('Fragment shader')
            print(self.fragment_code)
            print(log.decode('ascii'))
            raise RuntimeError('Shader compiliation failed')

        # Attach shader objects to the program
        gl.glAttachShader(program, vertex)
        gl.glAttachShader(program, fragment)

        # Build program
        gl.glLinkProgram(program)
        log = gl.glGetProgramInfoLog(program)
        if log:
            print('Shader link')
            print(self.fragment_code)
            print(log.decode('ascii'))
            raise RuntimeError('Shader compiliation failed')

        # Get rid of shaders (no more needed)
        gl.glDetachShader(program, vertex)
        gl.glDetachShader(program, fragment)

        return program
        
    def loadGeometry(self):
        attrData = self.getVertices()
        return self.loadAttribs(self.attributes, attrData)
        
    def loadInstances(self):
        instanceData = self.getInstances()
        return self.loadAttribs(self.instanceAttributes, instanceData)

    def loadAttribData(self, buffer, attrNames, attrData):
        # Make this buffer the default one
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)

        format = []
        for attrib in attrNames:
            format.append( (attrib, np.float32, attrNames[attrib]) )

        size = None
        for attrib, data in attrData.items():
            if size == None:
                size = len(data) 
                continue
            if size != len(data):
                raise RuntimeError('not all attribute arrays have the same length')

        data = np.zeros(size, format)

        for attrib in attrNames:
            if attrib in attrData:
                data[attrib] = attrData[attrib]

        # Upload data
        gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_DRAW)
        
        return size
        
    def loadAttribs(self, attrNames, attrData):
        if not attrNames:
            return (None, 1, 0, 0)
            
        # Request a buffer slot from GPU
        buffer = gl.glGenBuffers(1)

        format = []
        for attrib in attrNames:
            format.append( (attrib, np.float32, attrNames[attrib]) )

        data = np.zeros(1, format)

        offset = 0
        offsets = {}
        for attrib in attrNames:
            offsets[attrib] = ctypes.c_void_p(offset)
            offset += data.dtype[attrib].itemsize

        stride = data.strides[0]

        # Upload data
        if attrNames:
            size = self.loadAttribData(buffer, attrNames, attrData)

        return buffer, size, offsets, stride

    def setModelView(self, M):
        self.modelview = M
    
    def setProjection(self, M):
        self.projection = M
        
    def render(self):
        # Select our shaders
        gl.glUseProgram(self.program)
        
        # Use correct modelview
        loc = gl.glGetUniformLocation(self.program, "modelview")
        gl.glUniformMatrix4fv(loc, 1, False, self.modelview)

        # Use correct projection
        loc = gl.glGetUniformLocation(self.program, "projection")
        gl.glUniformMatrix4fv(loc, 1, False, self.projection)

        # Use correct color
        loc = gl.glGetUniformLocation(self.program, "objcolor")
        gl.glUniform4fv(loc, 1, self.color)

        gl.glBlendFunc(self.srcblend, self.dstblend)

        for uniform, value in self.getUniforms().items():
            loc = gl.glGetUniformLocation(self.program, uniform)
            if len(value) == 1:
                gl.glUniform1fv(loc, 1, value)
            if len(value) == 2:
                gl.glUniform2fv(loc, 1, value)
            if len(value) == 3:
                gl.glUniform3fv(loc, 1, value)
            if len(value) == 4:
                if type(value[0]) == float:
                    gl.glUniform4fv(loc, 1, value)
                else:
                    gl.glUniformMatrix4fv(loc, 1, False, value)

        texunit = 0
        for tex, value in self.getTextures().items():
            loc = gl.glGetUniformLocation(self.program, tex)
            if loc < 0:
                raise RuntimeError('Sampler %s not found in program' % tex)
            gl.glUniform1i(loc, texunit)
            gl.glActiveTexture(gl.GL_TEXTURE0 + texunit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, value)
            gl.glBindSampler(texunit, 0)
            texunit += 1 # Each texture is assigned to another texture unit

        for attrib in self.attributes:
            loc = gl.glGetAttribLocation(self.program, attrib)
            if loc < 0:
                raise RuntimeError('Attribute %s not found in program' % attrib)
            gl.glEnableVertexAttribArray(loc)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vertexBuffer)
            gl.glVertexAttribPointer(loc, self.attributes[attrib], gl.GL_FLOAT, False, self.stride, self.offsets[attrib])
            gl.glVertexAttribDivisor(loc, 0); 
            
        for attrib in self.instanceAttributes:
            loc = gl.glGetAttribLocation(self.program, attrib)
            if loc < 0:
                raise RuntimeError('Instance attribute %s not found in program' % attrib)
            gl.glEnableVertexAttribArray(loc)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.instanceBuffer)
            gl.glVertexAttribPointer(loc, self.instanceAttributes[attrib], gl.GL_FLOAT, False, self.instanceStride, self.instanceOffsets[attrib])
            gl.glVertexAttribDivisor(loc, 1)
            
        self.draw()
        gl.glUseProgram(0)
        
    def draw(self):
        gl.glDrawArraysInstanced(self.primitive, 0, self.vertices, self.instances)
