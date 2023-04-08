﻿import assembly
import random
import geometry
import geometry.simple
import OpenGL.GL as gl
import numpy as np
import transforms
import math
import fbo

from datetime import datetime

class newyear(assembly.assembly):
    freq = 250

    class Stars(geometry.base):
        primitive = gl.GL_QUADS
        srcblend = gl.GL_SRC_ALPHA
        dstblend = gl.GL_ONE

        instanceAttributes = { 'texcoor' : 2 }
        attributes = { 'position' : 2 }

        vertex_code = """
            uniform mat4 modelview;
            uniform mat4 projection;
            uniform mat4 aspect;
            uniform mat4 rotation;
            uniform vec4 objcolor;
            uniform float time;
            uniform float lifetime;

            uniform sampler2D positionTex;
            uniform sampler2D colorTex;
            uniform sampler2D velocityTex;
            uniform sampler2D depthTex;

            in highp vec2 position;
            in highp vec2 texcoor;
            out highp vec4 v_color;
            out highp vec2 v_texcoor;
            void main()
            {
                highp vec4 postex = texelFetch(positionTex, ivec2(texcoor), 0);
                highp vec3 center = postex.xyz;
                highp vec4 color = vec4(texelFetch(colorTex, ivec2(texcoor), 0).rgb, 1.0);
                highp vec4 velocity = texelFetch(velocityTex, ivec2(texcoor), 0);

                highp vec4 projectedCenter = projection * aspect * modelview * vec4(center, 1.0);
                highp vec4 prevProjectedCenter = projection * aspect * modelview * rotation * vec4(center, 1.0);
                highp vec4 projectedRotationVelocity = projectedCenter - prevProjectedCenter;
                highp float rmbscale = 100.0;  // Increase to make it more pronounced.

                highp float scale = abs((projectedCenter.z - 5.5) * 1.0);
                scale = max(scale, 0.04);
                scale = min(scale, 8.0);

                highp vec4 projectedObjectVelocity = aspect * projection * modelview * vec4(velocity.xyz, 1.0);
                highp vec4 projectedVelocity = projectedObjectVelocity + projectedRotationVelocity * rmbscale;
                highp vec2 velocity_2d = projectedVelocity.xy / length(projectedVelocity.xy);
                highp vec2 velocity_2d_ortho = vec2(-velocity_2d.y, velocity_2d.x);
                highp float mbscale = clamp(length(projectedVelocity.xy) / 100.0, 1.0, 10.0);

                highp vec2 transformed_position = (position.x * velocity_2d_ortho) + (position.y * velocity_2d * mbscale);
                gl_Position = (vec4(transformed_position, 0.0, 1.0) * scale * aspect + projectedCenter);
                highp float brightness = 1.0/pow(scale, 2.0);
                brightness *= 0.1 / projectedCenter.z;
                highp float sparkle = (1.0 + sin((time - postex.w) * 10.0)) / 2.0;
                highp float fade = clamp(1.0 - ((time - postex.w) / lifetime), 0.0, 1.0);

                highp float near = 1.0;
                highp float far = 1000.0;
                highp float depthSample = texture(depthTex, (0.5 * gl_Position.xy / gl_Position.w) + vec2(0.5)).x;
                depthSample = 2.0 * depthSample - 1.0;
                highp float zLinear = 2.0 * near * far / (far + near - depthSample * (far - near));
                if (zLinear < gl_Position.z) {
                    v_color = vec4(0.0, 0.0, 0.0, 1.0);
                } else {
                    v_color =  objcolor * color * vec4(vec3(brightness * sparkle * fade), 1.0);
                }
                v_texcoor = position;
            } 
        """

        fragment_code = """
            in highp vec4 v_color;
            in highp vec2 v_texcoor;
            out highp vec4 f_color;

            void main()
            {
                f_color = vec4(v_color.rgb * v_color.a * clamp(pow((1.0 - length(v_texcoor)),0.5), 0.0, 1.0), 1.0);
            } """

        def __init__(self, positionTex, colorTex, velocityTex, depthTex, texcoors, lifetime, aspect, rotationSpeed):
            self.starcolor = (1,1,1,1)
            self.positionTex = positionTex
            self.velocityTex = velocityTex
            self.colorTex = colorTex
            self.depthTex = depthTex
            self.texcoor = texcoors
            self.time = 0
            self.lifetime = lifetime
            self.aspect = aspect
            self.rotationTransform = self.rotationSpeedToTransform(rotationSpeed)

            super(newyear.Stars, self).__init__()
        
        @staticmethod
        def rotationSpeedToTransform(rotationSpeed):
            rotationTransform = np.eye(4, dtype=np.float32)
            fps = 60.0
            transforms.yrotate(rotationTransform, -rotationSpeed / fps)
            return rotationTransform
    
        def getVertices(self):
            verts = [(-1, -1), (+1, -1), (+1, +1), (-1, +1)]
            colors = [self.starcolor, self.starcolor, self.starcolor, self.starcolor]

            return { 'position' : verts, 'color' : colors }

        def getTextures(self):
            return {
                'colorTex': self.colorTex, 
                'positionTex': self.positionTex,
                'velocityTex': self.velocityTex,
                'depthTex': self.depthTex
            }

        def getInstances(self):
            return { 'texcoor' : self.texcoor }

        def getUniforms(self):
            return { 
                'time' : (self.time,), 
                'lifetime' : (self.lifetime,), 
                'aspect': self.aspect,
                'rotation': self.rotationTransform,
            }

    class VelocityShader(geometry.simple.texquad):
        fragment_code = """
            uniform sampler2D velocityTex;
            uniform sampler2D positionTex;
            uniform highp float dt;
            out highp vec4 f_color;
            in highp vec2 v_texcoor;

            void main()
            {
                highp float drag = 0.001;
                highp float gravity = 0.0;

                highp vec4 currentSpeed = vec4(textureLod(velocityTex, v_texcoor, 0.0).xyz, 1.0);
                highp vec4 currentPos = vec4(textureLod(positionTex, v_texcoor, 0.0).xyz, 1.0);
                f_color = currentSpeed * (1.0 - (drag * dt * length(currentSpeed))) - normalize(currentPos) * pow(length(currentPos), -2.0) * dt * gravity;
            }
        """

        def __init__(self):
            self.dt = 0
            self.velocityTex = None
            self.positionTex = None

            super().__init__()

        def getUniforms(self):
            return { 'dt' : (self.dt,) }

        def getTextures(self):
            return { 'velocityTex' : self.velocityTex, 'positionTex': self.positionTex }

    def __init__(self, depthTex, rotationSpeed):
        self.depthTex = depthTex
        self.rotationSpeed = rotationSpeed
        self.last = 0
        self.lastx = self.lasty = self.lastz = 0
        self.aspect = np.eye(4, dtype=np.float32)

        self.tsize = 128
        self.lifetime = self.tsize * self.tsize / self.freq
        self.nextPixel = 0

        self.positions = fbo.FBO(self.tsize, self.tsize)
        self.velocities = fbo.FBO(self.tsize, self.tsize)
        self.velocitiesDest = fbo.FBO(self.tsize, self.tsize)
        self.colors = fbo.FBO(self.tsize, self.tsize)

        for fb in [self.positions, self.velocities, self.velocitiesDest, self.colors]:
            with fb:
                gl.glClearColor(0,0,0,0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)

        self.velocityApplier = geometry.simple.texquad()
        self.velocityChanger = newyear.VelocityShader()

        texcoors = [(x,y) for x in range(0, self.tsize) for y in range(0, self.tsize)]

        self.geometry = newyear.Stars(
            self.positions.getTexture(), 
            self.colors.getTexture(), 
            self.velocities.getTexture(),
            self.depthTex,
            texcoors, 
            self.lifetime, 
            self.aspect,
            rotationSpeed,
        )

    def addstar(self, t, x, y, z, dx, dy, dz, r, g, b):
        shift = random.uniform(0, 1)

#        color = random.choice([(8.0,6.4,1.6), (6.8,6.2,7.8)])
#        color = random.choice([(8.0,0.4,0.6), (6.8,4.2,4.8), (0.8,9.2,0.8)])
        color = [r, g, b]

        gl.glBlendFunc(gl.GL_ONE, gl.GL_ZERO)
        gl.glUseProgram(0)
        with self.positions:
            gl.glWindowPos2i(*self.rasterPos(self.nextPixel))
            gl.glDrawPixels(1, 1, gl.GL_RGBA, gl.GL_FLOAT, (x,y,z, t + shift)) # Store xyz + starttime

        with self.colors:
            gl.glWindowPos2i(*self.rasterPos(self.nextPixel))
            gl.glDrawPixels(1, 1, gl.GL_RGB, gl.GL_FLOAT, color)

        with self.velocities:
            gl.glWindowPos2i(*self.rasterPos(self.nextPixel))
            gl.glDrawPixels(1, 1, gl.GL_RGBA, gl.GL_FLOAT, (dx,dy,dz,1))

        self.nextPixel = (self.nextPixel + 1) % (self.tsize*self.tsize)

    def rasterPos(self, n):
        return ( n % self.tsize, int (n / self.tsize) )

    def step(self, t):
        dt = t - self.last

        with self.positions:
            self.velocityApplier.setTexture(self.velocities.getTexture())
            self.velocityApplier.dstblend = gl.GL_ONE
            self.velocityApplier.srcblend = gl.GL_SRC_ALPHA
            self.velocityApplier.color = (1,1,1,dt) # apply delta's with 'dt' weight, as an alpha value
            self.velocityApplier.render()

        # Update velocities to 'slow down'. Since we cannot render to the texture that we're reading
        # from, we have to render to another FBO, and swap it around
        with self.velocitiesDest:
            self.velocityChanger.dt = dt
            self.velocityChanger.velocityTex = self.velocities.getTexture()
            self.velocityChanger.positionTex = self.positions.getTexture()
            self.velocityChanger.dstblend = gl.GL_ZERO
            self.velocityChanger.srcblend = gl.GL_ONE
            self.velocityChanger.color = (1,1,1,1 - dt * 0.5)
            self.velocityChanger.render()

        # Swap around velocity FBOs
        self.velocities, self.velocityDest = (self.velocitiesDest, self.velocities)
        self.last = t

    def render(self, t):
        self.geometry.time = t
        self.geometry.velocityTex = self.velocities.getTexture()
        self.geometry.render()

    def setProjection(self, M):
        self.geometry.setProjection(M)

    def setModelView(self, M):
        self.geometry.setModelView(M)

    def setAspect(self, M):
        self.geometry.aspect = M

    def changeModelview(self, t):
        modelview = np.eye(4, dtype=np.float32)
        transforms.yrotate(modelview, t * self.rotationSpeed)
        #transforms.translate(modelview, 0, -.03, -.5)
        transforms.translate(modelview, 0, 0, -100)
        effect.setModelView(modelview)
