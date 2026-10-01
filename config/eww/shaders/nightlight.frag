#version 300 es
precision mediump float;
in vec2 v_texcoord;
layout(location = 0) out vec4 fragColor;
uniform sampler2D tex;
void main() {
    vec4 pixel = texture(tex, v_texcoord);
    // Approximate 4000 K white point, retaining alpha and the red channel.
    fragColor = vec4(pixel.rgb * vec3(1.0, 0.807, 0.651), pixel.a);
}
