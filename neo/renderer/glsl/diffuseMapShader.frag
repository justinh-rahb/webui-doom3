#version 100
precision mediump float;
  
uniform sampler2D u_fragmentMap0;
uniform lowp vec4 u_glColor;
  
varying vec4 var_TexCoord;
varying lowp vec4 var_Color;
  
void main(void)
{
  gl_FragColor = texture2D(u_fragmentMap0, var_TexCoord.xy / var_TexCoord.w) * u_glColor * var_Color;
}