import os
import math
import asyncio

import carb
import carb.settings

import omni.kit.app
import omni.ext
import omni.ui
import omni.kit.ui_windowmanager
import omni.appwindow
import numpy as np

from pxr import UsdGeom, UsdShade, Vt, Gf, Sdf, Usd

try:
    import omni.kit.renderer
    import omni.kit.imgui_renderer

    standalone_renderer_present = True
except:
    standalone_renderer_present = False


WINDOW_NAME = "Object Centering"
EXTENSION_NAME = "Object Centering"


class Extension(omni.ext.IExt):
    def __init__(self):
        self.enabled = True
        self._window = omni.ui.Window(EXTENSION_NAME, width=600, height=800, menu_path=f"{EXTENSION_NAME}")
        self._scroll_frame = omni.ui.ScrollingFrame()
        self._ui_rebuild()
        self._window.frame.set_build_fn(self._ui_rebuild)
        self.loads()

    def loads(self):
        self.x = 0
        self.y = 0
        self.z = 6

    def get_name(self):
        return EXTENSION_NAME

    def on_startup(self, ext_id):
        stage = omni.usd.get_context().get_stage()

        self._context = omni.usd.get_context()
        self.event_sub = self._context.get_stage_event_stream().create_subscription_to_pop(self._on_event)
        self._timeline_iface = omni.timeline.get_timeline_interface()
        self._timeline_events = self._timeline_iface.get_timeline_event_stream().create_subscription_to_pop(
            self._on_timeline_event
        )
        self.update_events = (
            omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(self._on_update)
        )

    def on_shutdown(self):
        pass

    def _on_event(self, e):
        if e.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            pass
        elif e.type == int(omni.usd.StageEventType.OPENED) or e.type == int(omni.usd.StageEventType.ASSETS_LOADED):
            self.loads()

    def _on_timeline_event(self, e):
        stage = omni.usd.get_context().get_stage()
        if e.type == int(omni.timeline.TimelineEventType.PLAY):
            # Disable visualization dropdown
            # Change button to Stop
            pass
        elif e.type == int(omni.timeline.TimelineEventType.STOP):
            # Enable visualization dropdown
            # Change button to Drive
            carb.log_info("stoped")
        elif e.type == int(omni.timeline.TimelineEventType.PAUSE):
            # Change button to Drive
            pass

    def _on_update(self, dt):
        pass

    async def test(self):
        stage = omni.usd.get_context().get_stage()
        carb.log_info(f"stage:{help(stage)}")
        selected_paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        for selected_path in selected_paths:
            selected = stage.GetPrimAtPath(selected_path)
            carb.log_info(f"stage:{help(selected)}")
            carb.log_info(f"{selected}")
            carb.log_info(f"typename:{selected.GetTypeName()} name:{selected.GetName()}")
            points = selected.GetAttribute("points").Get()
            if points:
                normals = selected.GetAttribute("normals").Get()
                faceVertexCounts = selected.GetAttribute("faceVertexCounts").Get()
                faceVertexIndices = selected.GetAttribute("faceVertexIndices").Get()
                carb.log_info(f"points len:{len(points)}")
                carb.log_info(f"normals len:{len(normals)}")
                carb.log_info(f"faceVertexCounts len:{len(faceVertexCounts)}")
                carb.log_info(f"faceVertexIndices len:{len(faceVertexIndices)}")
                self.doSplit(selected)

    #split the subset, not working yet.
    def doSplit(self, selected):
        stage = omni.usd.get_context().get_stage()
        if selected.GetTypeName() != 'Mesh':
            return
        name = selected.GetName()
        points = selected.GetAttribute("points").Get()
        faceVertexIndices = selected.GetAttribute("faceVertexIndices").Get()
        carb.log_info(f"faceVertexIndices:{faceVertexIndices}")
        faceVertexIndices = np.array(faceVertexIndices).reshape(int(len(faceVertexIndices)/4),4)
        normals = selected.GetAttribute("normals").Get()
        carb.log_info(f"normals:{normals}")
        for child in selected.GetAllChildren():
            subsetName = child.GetName()
            indices = child.GetAttribute("indices").Get()
            points1 = points
            #payload1 = Usd.Stage.CreateNew("payload1.usd")
            payload1 = stage.DefinePrim("/payload1", "Xform")
            mesh = stage.DefinePrim(f"/payload1/{name}_{subsetName}", "Mesh")
            path = f"/payload1/{name}_{subsetName}"
            mesh = UsdGeom.Mesh.Get(stage, path)
            mesh.CreatePointsAttr().Set(points1)
            newVertexIndices = []
            newNormals = []
            count = 0
            for index in faceVertexIndices:
                toAdd = 4
                for i in index:
                    if i not in indices:
                        #carb.log_info(f"{i} not in index")
                        toAdd -= 1
                if toAdd > 0:
                    newVertexIndices.append(index)
                    newNormals.append(normals[count*4])
                    newNormals.append(normals[count*4+1])
                    newNormals.append(normals[count*4+2])
                    newNormals.append(normals[count*4+3])
                count += 1
            faceCounts = [4]*len(newVertexIndices)
            newVertexIndices = np.array(newVertexIndices).reshape(len(newVertexIndices)*4)
            carb.log_info(f"newVertexIndices:{len(newVertexIndices)}")
            mesh.CreateFaceVertexCountsAttr().Set(faceCounts)
            mesh.CreateFaceVertexIndicesAttr().Set(newVertexIndices)
            mesh.CreateNormalsAttr().Set(newNormals)

    #center the selected object
    async def doCenter(self):
        stage = omni.usd.get_context().get_stage()
        selected_paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        carb.log_info(f"{selected_paths}")
        for selected_path in selected_paths:
            selected = stage.GetPrimAtPath(selected_path)
            carb.log_info(f"selected:{help(selected)}")
            if selected.GetTypeName() == 'Xform':
                carb.log_info(f"children:{selected.GetAllChildren()}")
                for child in selected.GetAllChildren():
                    self.doCenterPrim(child)
            else:
                self.doCenterPrim(selected)

    async def doCenterAll(self):
        stage = omni.usd.get_context().get_stage()
        selecteds = stage.Traverse()#omni.usd.get_context().get_selection().get_selected_prim_paths()
        carb.log_info(f"{selecteds}")
        for selected in selecteds:
            if selected.GetTypeName() == 'Xform':
                continue
            else:
                self.doCenterPrim(selected)

    def doCenterPrim(self, selected):
        points = selected.GetAttribute("points").Get()
        carb.log_info(f"points:{points}")
        if points is None:
            return
        ps = np.array(points)
        psmean = ps.mean(axis=0)
        carb.log_info(f"mean:{psmean}")
        ps[:] -= psmean
        selected.GetAttribute("points").Set(ps)

        scale = [1,1,1]#actually, scale is not used!
        if selected.HasAttribute("xformOp:translate"):
            attr_position = selected.GetAttribute("xformOp:translate")
            if selected.HasAttribute("xformOp:scale"):
                scale = selected.GetAttribute("xformOp:scale").Get()
        else:
            attr_position = selected.GetParent().GetAttribute("xformOp:translate")
            if selected.GetParent().GetAttribute("xformOp:scale").Get() is not None:
                scale = selected.GetParent().GetAttribute("xformOp:scale").Get()
        carb.log_info(f"attr_position:{attr_position} attr_scale:{scale}")
        translate = attr_position.Get()
        if translate is not None:
            carb.log_info(f"get translate:{translate}")
            #attr_position = selected.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, False)
            newtranslate = Gf.Vec3d(0,0,0)
            newtranslate[0] = translate[0] + psmean[0]
            newtranslate[1] = translate[1] + psmean[1]
            newtranslate[2] = translate[2] + psmean[2]
            attr_position.Set(newtranslate)
            carb.log_info(f"set translate:{newtranslate}")
        else:
            attr_position = selected.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, False)
            carb.log_info(f"create translate:{attr_position}")
            translate = Gf.Vec3d(0,0,0)
            translate[0] += psmean[0]
            translate[1] += psmean[1]
            translate[2] += psmean[2]
            attr_position = selected.GetAttribute("xformOp:translate")
            attr_position.Set(translate)

        self._window.frame.rebuild()

    def _ui_rebuild(self):
        self._scroll_frame = omni.ui.ScrollingFrame()
        with self._window.frame:
            with self._scroll_frame:
                with omni.ui.VStack(spacing=5):
                    # intro
                    with omni.ui.CollapsableFrame(title="Description", height=10):
                        with omni.ui.VStack(style={"margin": 5}):
                            omni.ui.Label(
                                "This extension will center the selected object",
                                word_wrap=True,
                            )

                    # Test Drive/Reset Button
                    with omni.ui.HStack():
                        button_label = (
                            "Do center"
                        )
                        button = omni.ui.Button(button_label, height=5, style={"padding": 12, "font_size": 20})
                        button.set_clicked_fn(lambda: asyncio.ensure_future(self.doCenter()))

                        button_label2 = (
                            "Do center all"
                        )
                        button2 = omni.ui.Button(button_label2, height=5, style={"padding": 12, "font_size": 20})
                        button2.set_clicked_fn(lambda: asyncio.ensure_future(self.doCenterAll()))
                        """
                        button_label3 = (
                            "test"
                        )
                        button3 = omni.ui.Button(button_label3, height=5, style={"padding": 12, "font_size": 20})
                        button3.set_clicked_fn(lambda: asyncio.ensure_future(self.test()))
                        """