﻿import assembly
import random
import geometry
import geometry.simple
import OpenGL.GL as gl
import numpy as np
import transforms
import math
import fbo
import struct
from io import BytesIO
from PIL import Image

from pygltflib import GLTF2, Scene

class Mesh(geometry.base):
    primitive = gl.GL_TRIANGLES
    srcblend = gl.GL_SRC_ALPHA
    dstblend = gl.GL_ONE_MINUS_SRC_ALPHA

    attributes = { 'position' : 3, 'tex': 2 }

    vertex_code = """
        uniform mat4 modelview;
        uniform mat4 projection;
        uniform vec4 objcolor;
        uniform mat4 aspect;

        in highp vec4 color;
        in highp vec3 position;
        in highp vec2 tex;

        out highp vec4 v_color;
        out highp vec2 v_tex;
        void main()
        {
            gl_Position = aspect * projection * modelview * vec4(position,1.0);
            v_color = vec4(5.0,5.0,5.0,1.0); //objcolor;
            v_tex = tex;
        }
    """

    fragment_code = """
        in highp vec4 v_color;
        in highp vec2 v_tex;
        out highp vec4 f_color;
        uniform sampler2D texture0;

        void main()
        {
            highp vec4 texel = texture(texture0, v_tex);
            f_color = texel * v_color;
        }
    """

    def __init__(self, vertices, indices, texcoors, image):
        self.vertices = vertices
        self.indices = indices
        self.texcoors = texcoors
        self.tex = self.loadImage(image)
        self.aspect = np.eye(4, dtype=np.float32)
        super().__init__()

    def loadImage(self, im):
        imdata = im.tobytes()
        print(len(imdata))
        tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, im.size[0], im.size[1], 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, imdata)
        gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        return tex

    def getVertices(self):
        return { 'position' : self.vertices, 'tex': self.texcoors }

    def getTextures(self):
        return { 'texture0': self.tex }

    def getInstances(self):
        return { }

    def getUniforms(self):
        return { 'aspect': self.aspect }

    def draw(self):
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDrawElements(self.primitive, len(self.indices), gl.GL_UNSIGNED_INT, self.indices)
        gl.glDisable(gl.GL_DEPTH_TEST)

class gltf(assembly.assembly):
    def __init__(self, filename):
        gltf = GLTF2().load(filename)
        mesh = gltf.meshes[gltf.scenes[gltf.scene].nodes[0]]
        primitive = mesh.primitives[0]

        vertices = self.readFromAccessor(gltf, primitive.attributes.POSITION)
        indices = self.readFromAccessor(gltf, primitive.indices)
        texcoors = self.readFromAccessor(gltf, primitive.attributes.TEXCOORD_0)
        images = []

        for image in gltf.images:
            bufferView = gltf.bufferViews[image.bufferView]
            buffer = gltf.buffers[bufferView.buffer]
            data = gltf.get_data_from_buffer_uri(buffer.uri)
            stream = BytesIO(data)
            im = Image.open(stream)
            im.tobytes()
            images.append(im)

        self.geometry = Mesh(vertices, indices, texcoors, images[0])

    def getFormat(self, componentType, type):
        formats = { 5123: "H", 5126: "f" }
        types = { "SCALAR": 1, "VEC2":2, "VEC3": 3 }

        if componentType not in formats:
            raise RuntimeError('Unknown format componentType %d' % componentType)

        if type not in types:
            raise RuntimeError('Unknown format type %s' % type)

        f = formats.get(componentType)
        n = types.get(type)

        return "<" + (f * n)

    def readFromAccessor(self, gltf, accessorId):
        out = []

        # get the binary data for this mesh primitive from the buffer
        accessor = gltf.accessors[accessorId]
        print(accessor)

        format = self.getFormat(accessor.componentType, accessor.type)
        size = struct.calcsize(format)

        bufferView = gltf.bufferViews[accessor.bufferView]
        buffer = gltf.buffers[bufferView.buffer]
        data = gltf.get_data_from_buffer_uri(buffer.uri)

        # pull each vertex from the binary buffer and convert it into a tuple of python floats
        for i in range(accessor.count):
            index = bufferView.byteOffset + accessor.byteOffset + i*size  # the location in the buffer of this vertex
            d = data[index:index+size]  # the vertex data
            v = struct.unpack(format, d)   # convert from base64 to three floats
            out.append(v)

        return out

    def render(self, t):
        self.geometry.time = t
        self.geometry.render()

    def setProjection(self, M):
        self.geometry.setProjection(M)

    def setModelView(self, M):
        self.geometry.setModelView(M)

    def setAspect(self, M):
        self.geometry.aspect = M

