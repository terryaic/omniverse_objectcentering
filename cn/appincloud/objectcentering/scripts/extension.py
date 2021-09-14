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

MAX_ANGULAR_VELOCITY = 500
MIN_LINEAR_VELOCITY = -2000
WINDOW_NAME = "Object Centering"
EXTENSION_NAME = "Object Centering"

class ExtWindow:
    def _create_window(self):
        if not standalone_renderer_present:
            carb.log_warn("Only supported in standalone mode!")
            return
        new_window = self._appwindow_factory.create_window_ptr()
        new_window.startup_with_desc(
            "%d: test" % (len(self.added_windows)),
            1200,
            900,
            omni.appwindow.POSITION_UNSET,
            omni.appwindow.POSITION_UNSET,
            True,
            True,
            False,
            True,
        )
        self._imgui_renderer.attach_app_window(new_window)
        self.added_windows.append(new_window)
        new_dock_space = omni.ui.DockSpace(self._window_manager.get_window_set_by_app_window(new_window))
        self.added_dock_spaces.append(new_dock_space)

    def _move_cb_window_active(self):
        if self._active_os_window is None:
            carb.log_error("Please select OS window")
            return
        if self._active_cb_window is None:
            carb.log_error("Please select UI window")
            return

        self._window_manager.move_callback_to_app_window(self._active_cb_window, self._active_os_window)

        ui_window = omni.ui.Workspace.get_window_from_callback(self._active_cb_window)
        if ui_window is not None:
            ui_window.notify_app_window_change(self._active_os_window)

        self._refresh()

    def _update_control_frame(self):
        with self._control_frame:
            with omni.ui.HStack():
                if self._active_cb_window is not None and self._active_os_window is not None:
                    omni.ui.Label(
                        "UI-cb window '%s', OS Window '%s'"
                        % (self._active_cb_window.get_title(), self._active_os_window.get_title())
                    )
                    btn = omni.ui.Button("Move", width=64, height=16)
                    btn.set_clicked_fn(self._move_cb_window_active)
                else:
                    omni.ui.Label("Please select both UI and OS active windows")

    def _set_active_os_window(self, os_window):
        self._active_os_window = os_window
        self._update_control_frame()

    def _set_active_cb_window(self, cb_window):
        self._active_cb_window = cb_window
        self._update_control_frame()

    def _output_all_os_windows(self):
        self._os_wnd_btns = []
        with self._os_wnd_frame:
            with omni.ui.VStack():
                os_windows = self._appwindow_factory.get_windows()
                for os_window in os_windows:
                    btn = omni.ui.Button(os_window.get_title(), height=16)
                    btn.set_clicked_fn(lambda wnd=os_window: self._set_active_os_window(wnd))
                    self._os_wnd_btns.append(btn)

    def _output_all_cb_windows(self):
        self._cb_wnd_btns = []
        with self._cb_wnd_frame:
            with omni.ui.VStack():
                window_set_count = self._window_manager.get_window_set_count()
                for wnd_set_i in range(window_set_count):
                    window_set = self._window_manager.get_window_set_at(wnd_set_i)
                    window_set_callbacks_count = self._window_manager.get_window_set_callback_count(window_set)
                    omni.ui.Label("%d: %d wnds" % (wnd_set_i, window_set_callbacks_count), height=16)
                    for callback_i in range(window_set_callbacks_count):
                        cb_window = self._window_manager.get_window_set_callback_at(window_set, callback_i)
                        btn = omni.ui.Button(cb_window.get_title(), height=16)
                        btn.set_clicked_fn(lambda wnd=cb_window: self._set_active_cb_window(wnd))
                        self._cb_wnd_btns.append(btn)

    def _refresh(self):
        self._output_all_os_windows()
        self._output_all_cb_windows()

    def _exit(self):
        omni.kit.app.get_app().post_quit()

    def startup(self):
        if standalone_renderer_present:
            self._imgui_renderer = omni.kit.imgui_renderer.acquire_imgui_renderer_interface()
        self._settings = carb.settings.get_settings()
        self._window = omni.ui.Window(WINDOW_NAME, width=600, height=340)
        self._appwindow_factory = omni.appwindow.acquire_app_window_factory_interface()
        self._window_manager = omni.kit.ui_windowmanager.acquire_window_callback_manager_interface()
        self.added_windows = []
        self.added_dock_spaces = []
        self._active_os_window = None
        self._active_cb_window = None
        with self._window.frame:
            with omni.ui.VStack():
                with omni.ui.HStack(height=16):
                    self._btn_create_window = omni.ui.Button("Create 'test' Window", width=100, height=16)
                    self._btn_create_window.set_clicked_fn(self._create_window)
                    self._btn_refresh = omni.ui.Button("Refresh", width=100, height=16)
                    self._btn_refresh.set_clicked_fn(self._refresh)
                    self._btn_exit = omni.ui.Button("Exit", width=100, height=16)
                    self._btn_exit.set_clicked_fn(self._exit)
                self._control_frame = omni.ui.Frame(height=32)
                with omni.ui.HStack():
                    self._cb_wnd_frame = omni.ui.Frame(width=omni.ui.Percent(30))
                    self._os_wnd_frame = omni.ui.Frame(width=omni.ui.Percent(30))

        self._output_all_os_windows()
        self._output_all_cb_windows()
        self._update_control_frame()

    def shutdown(self):
        self._btn_refresh_rgb = None
        self._btn_create_window = None
        self._btn_refresh = None
        self._btn_exit = None
        self._ui_wnd_btns = None
        self._os_wnd_btns = None
        self._cb_wnd_btns = None
        self._active_os_window = None
        self._active_cb_window = None
        self.added_dock_spaces = None
        self.added_windows = None
        self._window = None


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

    async def doCenter(self):
        stage = omni.usd.get_context().get_stage()
        selected_paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
        carb.log_info(f"{selected_paths}")
        for selected_path in selected_paths:
            selected = stage.GetPrimAtPath(selected_path)
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

        scale = [1,1,1]
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
            newtranslate[0] = (translate[0] + psmean[0])*scale[0]
            newtranslate[1] = (translate[1] + psmean[1])*scale[1]
            newtranslate[2] = (translate[2] + psmean[2])*scale[2]
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
                        start_button_label = (
                            "Do center"
                        )
                        start_button = omni.ui.Button(start_button_label, height=5, style={"padding": 12, "font_size": 20})

                        start_button.set_clicked_fn(lambda: asyncio.ensure_future(self.doCenter()))