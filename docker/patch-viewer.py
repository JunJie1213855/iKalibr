#!/usr/bin/env python3
"""Add screen-space borders and titles without changing the viewer ABI."""
from pathlib import Path

path = Path('/opt/ikalibr_ws/src/ikalibr/thirdparty/ctraj/thirdparty/tiny-viewer/src/src/core/multi_viewer.cpp')
text = path.read_text()
font_include = '#include "pangolin/gl/glfont.h"\n'
if font_include not in text:
    text = text.replace('#include "pangolin/gl/gldraw.h"\n', '#include "pangolin/gl/gldraw.h"\n' + font_include)
marker = '// iKalibr screen-space panel labels'
if marker not in text:
    anchor = '        // Swap frames and Process Events\n'
    assert text.count(anchor) == 1, 'Inspect changed viewer render loop before patching'
    overlay = r'''        // iKalibr screen-space panel labels (independent of the 3D camera).
        const std::map<std::string, std::string> panelTitles = {
            {"VIEW_SENSORS", "Sensors / extrinsics"},
            {"VIEW_SPLINE", "Continuous-time trajectory"},
            {"VIEW_MAP", "Map"},
            {"VIEW_ASSOCIATION", "Data association"}};
        for (const auto &name : _configor.subWinNames) {
            const auto title = panelTitles.find(name);
            auto &panel = d_cam.at(name);
            if (title == panelTitles.end() || !panel.IsShown() ||
                panel.v.w < 2 || panel.v.h < 2) continue;
            glPushAttrib(GL_ALL_ATTRIB_BITS);
            glMatrixMode(GL_PROJECTION);
            glPushMatrix();
            glMatrixMode(GL_MODELVIEW);
            glPushMatrix();
            panel.ActivatePixelOrthographic();
            glDisable(GL_DEPTH_TEST);
            glDisable(GL_LIGHTING);
            glDisable(GL_LINE_SMOOTH);
            glDisable(GL_LINE_STIPPLE);
            glDisable(GL_TEXTURE_2D);
            glEnable(GL_BLEND);
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
            glLineWidth(1.0f);
            glColor4f(0, 0, 0, 1);
            glBegin(GL_LINE_LOOP);
            glVertex2f(0.5f, 0.5f);
            glVertex2f(panel.v.w - 0.5f, 0.5f);
            glVertex2f(panel.v.w - 0.5f, panel.v.h - 0.5f);
            glVertex2f(0.5f, panel.v.h - 0.5f);
            glEnd();
            auto label = panelFont.Text(title->second);
            glColor4f(1, 1, 1, 0.85f);
            glBegin(GL_QUADS);
            glVertex2f(5, panel.v.h - 30);
            glVertex2f(20 + label.Width(), panel.v.h - 30);
            glVertex2f(20 + label.Width(), panel.v.h - 5);
            glVertex2f(5, panel.v.h - 5);
            glEnd();
            glColor4f(0, 0, 0, 1);
            label.Draw(10, panel.v.h - 23);
            glMatrixMode(GL_MODELVIEW);
            glPopMatrix();
            glMatrixMode(GL_PROJECTION);
            glPopMatrix();
            glPopAttrib();
        }

'''
    text = text.replace(anchor, overlay + anchor)
text = text.replace('pangolin::GlFont::I().Text(title->second)', 'panelFont.Text(title->second)')
if 'pangolin::GlFont panelFont(18);' not in text:
    text = text.replace('    while (!pangolin::ShouldQuit()) {',
                        '    pangolin::GlFont panelFont(18);\n\n    while (!pangolin::ShouldQuit()) {')
path.write_text(text)
