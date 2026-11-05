#!/usr/bin/env python3
"""
NitroSense GUI - Modern Libadwaita Interface for Acer Nitro V 15
Designed for Acer Nitro Gaming Laptops (ANV15-51)
"""
import sys
import os
import glob
import subprocess

sys.path.insert(0, "/usr/local/share/nitrosense")
from backend import NitroBackend

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

CSS = """
window.nitrosense-window {
    background-color: #0b0c10;
    color: #e2e8f0;
}

.nitro-card {
    background-color: #12151d;
    border: 1px solid #1f2433;
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
}

.nitro-card:hover {
    border-color: #2e354b;
}

.section-title {
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 1.2px;
    color: #94a3b8;
}

.card-title {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
}

.stat-subtext {
    font-size: 12px;
    color: #64748b;
}

.fan-label {
    font-size: 26px;
    font-weight: 800;
    font-family: monospace;
    color: #00d2ff;
}

.fan-label-gpu {
    font-size: 26px;
    font-weight: 800;
    font-family: monospace;
    color: #10b981;
}

.temp-badge-cool {
    font-size: 20px;
    font-weight: 800;
    font-family: monospace;
    color: #10b981;
}

.temp-badge-warm {
    font-size: 20px;
    font-weight: 800;
    font-family: monospace;
    color: #f59e0b;
}

.temp-badge-hot {
    font-size: 20px;
    font-weight: 800;
    font-family: monospace;
    color: #ef4444;
}

/* Profile Selector Cards */
.profile-btn {
    background-color: #161a24;
    border: 2px solid #242a3b;
    border-radius: 12px;
    padding: 12px 10px;
    transition: all 180ms ease-in-out;
}

.profile-btn:hover {
    background-color: #1c2230;
    border-color: #3b4560;
}

.profile-btn-title {
    font-size: 14px;
    font-weight: 700;
    color: #f1f5f9;
}

.profile-btn-desc {
    font-size: 11px;
    color: #94a3b8;
}

.profile-btn-active {
    background: linear-gradient(135deg, #991b1b, #dc2626);
    border: 2px solid #f87171;
    color: #ffffff;
    box-shadow: 0 0 18px rgba(239, 68, 68, 0.45);
}

.profile-btn-active .profile-btn-title,
.profile-btn-active .profile-btn-desc {
    color: #ffffff;
}

/* Fan Mode Buttons */
.fan-mode-btn {
    background-color: #161a24;
    border: 2px solid #242a3b;
    border-radius: 10px;
    padding: 12px 8px;
    font-weight: 700;
    color: #cbd5e1;
}

.fan-mode-btn:hover {
    background-color: #1c2230;
    border-color: #3b4560;
}

.fan-mode-auto-active {
    background: linear-gradient(135deg, #0284c7, #0ea5e9);
    border: 2px solid #38bdf8;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(14, 165, 233, 0.4);
}

.fan-mode-max-active {
    background: linear-gradient(135deg, #b91c1c, #ef4444);
    border: 2px solid #f87171;
    color: #ffffff;
    box-shadow: 0 0 18px rgba(239, 68, 68, 0.55);
}

.fan-mode-custom-active {
    background: linear-gradient(135deg, #7c3aed, #a855f7);
    border: 2px solid #c084fc;
    color: #ffffff;
    box-shadow: 0 0 16px rgba(168, 85, 247, 0.4);
}

/* Progress Bars */
progressbar.nitro-cpu-bar trough {
    background-color: #1a202c;
    border-radius: 6px;
    min-height: 8px;
}
progressbar.nitro-cpu-bar progress {
    background: linear-gradient(90deg, #0284c7, #00d2ff);
    border-radius: 6px;
}

progressbar.nitro-gpu-bar trough {
    background-color: #1a202c;
    border-radius: 6px;
    min-height: 8px;
}
progressbar.nitro-gpu-bar progress {
    background: linear-gradient(90deg, #059669, #10b981);
    border-radius: 6px;
}

scale.nitro-slider trough {
    background-color: #1a202c;
    border-radius: 6px;
    min-height: 8px;
}
scale.nitro-slider highlight {
    background: linear-gradient(90deg, #7c3aed, #c084fc);
    border-radius: 6px;
}
scale.nitro-slider slider {
    background-color: #ffffff;
    border: 2px solid #a855f7;
    border-radius: 50%;
    min-width: 18px;
    min-height: 18px;
}

.status-pill {
    background-color: #064e3b;
    border: 1px solid #059669;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    color: #34d399;
}
"""

class NitroSenseWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("NitroSense")
        self.set_default_size(860, 800)
        self.add_css_class("nitrosense-window")

        self.backend = NitroBackend()
        self._is_user_dragging = False

        self._load_css()
        self._build_ui()

        self.update_stats()
        GLib.timeout_add(1500, self.update_stats)

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

        # Header Bar
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_valign(Gtk.Align.CENTER)
        
        main_title = Gtk.Label(label="NitroSense", xalign=0.5)
        main_title.set_css_classes(["card-title"])
        
        sub_title = Gtk.Label(label="Acer Nitro V 15 (ANV15-51)", xalign=0.5)
        sub_title.set_css_classes(["stat-subtext"])
        
        title_box.append(main_title)
        title_box.append(sub_title)
        header.set_title_widget(title_box)

        # Right status pill in header
        self.status_pill = Gtk.Label(label="DAEMON ACTIVE")
        self.status_pill.add_css_class("status-pill")
        header.pack_end(self.status_pill)
        main_box.append(header)

        # Scrollable content
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        main_box.append(scroller)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(16)
        content.set_margin_bottom(24)
        content.set_margin_start(20)
        content.set_margin_end(20)
        scroller.set_child(content)

        # 1. Thermal & Cooling Grid (CPU & GPU)
        cards_grid = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True)
        content.append(cards_grid)

        self.cpu_card = self._create_cooling_card(
            title="CPU Thermal & Fan",
            icon_name="processor-symbolic",
            is_cpu=True
        )
        cards_grid.attach(self.cpu_card, 0, 0, 1, 1)

        self.gpu_card = self._create_cooling_card(
            title="GPU Thermal & Fan",
            icon_name="video-display-symbolic",
            is_cpu=False
        )
        cards_grid.attach(self.gpu_card, 1, 0, 1, 1)

        # 2. Operating Thermal Profiles (Whisper, Balanced, Performance, Eco)
        profile_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        profile_card.add_css_class("nitro-card")
        content.append(profile_card)

        prof_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        prof_icon = Gtk.Image.new_from_icon_name("power-profile-balanced-symbolic")
        prof_title = Gtk.Label(label="Operating Thermal Profile", xalign=0)
        prof_title.add_css_class("card-title")
        prof_header_box.append(prof_icon)
        prof_header_box.append(prof_title)
        profile_card.append(prof_header_box)

        prof_desc = Gtk.Label(
            label="Hardware TDP targets, thermal ceiling, and dynamic cooling response curve.",
            xalign=0
        )
        prof_desc.add_css_class("stat-subtext")
        profile_card.append(prof_desc)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, homogeneous=True)
        btn_box.set_margin_top(6)
        profile_card.append(btn_box)

        self.btn_quiet = self._create_profile_btn("Whisper", "🍃", "Silent fan profile", "quiet")
        self.btn_balanced = self._create_profile_btn("Balanced", "⚡", "Dynamic auto curve", "balanced")
        self.btn_perf = self._create_profile_btn("Performance", "🔥", "Maximum boost & power", "performance")
        self.btn_eco = self._create_profile_btn("Eco Saver", "🔋", "Battery priority", "eco")

        btn_box.append(self.btn_quiet)
        btn_box.append(self.btn_balanced)
        btn_box.append(self.btn_perf)
        btn_box.append(self.btn_eco)

        self.profile_status_lbl = Gtk.Label(label="Active Profile: Balanced", xalign=0)
        self.profile_status_lbl.add_css_class("stat-subtext")
        profile_card.append(self.profile_status_lbl)

        # 3. Fan Speed Control Section (Auto / Max / Custom + Slider)
        fan_control_card = self._create_fan_control_card()
        content.append(fan_control_card)

        # 4. Dedicated GPU Card (NVIDIA RTX 3050)
        self.nv_card = self._create_nvidia_card()
        content.append(self.nv_card)

        # 5. System & Battery Overview Card
        sys_card = self._create_system_card()
        content.append(sys_card)

    def _create_cooling_card(self, title, icon_name, is_cpu):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class("nitro-card")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name(icon_name)
        title_lbl = Gtk.Label(label=title, xalign=0)
        title_lbl.add_css_class("card-title")
        h_box.append(img)
        h_box.append(title_lbl)
        box.append(h_box)

        fan_header = Gtk.Label(label="FAN ROTATIONAL SPEED", xalign=0)
        fan_header.add_css_class("stat-subtext")
        box.append(fan_header)

        fan_val_lbl = Gtk.Label(label="-- RPM", xalign=0)
        fan_val_lbl.add_css_class("fan-label" if is_cpu else "fan-label-gpu")
        box.append(fan_val_lbl)

        bar = Gtk.ProgressBar()
        bar.add_css_class("nitro-cpu-bar" if is_cpu else "nitro-gpu-bar")
        bar.set_fraction(0.0)
        box.append(bar)

        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16, homogeneous=True)
        stats_box.set_margin_top(4)
        box.append(stats_box)

        temp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        temp_title = Gtk.Label(label="TEMPERATURE", xalign=0)
        temp_title.add_css_class("stat-subtext")
        temp_val = Gtk.Label(label="-- °C", xalign=0)
        temp_val.add_css_class("temp-badge-cool")
        temp_box.append(temp_title)
        temp_box.append(temp_val)
        stats_box.append(temp_box)

        load_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        load_title = Gtk.Label(label="UTILIZATION", xalign=0)
        load_title.add_css_class("stat-subtext")
        load_val = Gtk.Label(label="-- %", xalign=0)
        load_val.add_css_class("card-title")
        load_box.append(load_title)
        load_box.append(load_val)
        stats_box.append(load_box)

        if is_cpu:
            self.cpu_fan_lbl = fan_val_lbl
            self.cpu_fan_bar = bar
            self.cpu_temp_lbl = temp_val
            self.cpu_load_lbl = load_val
        else:
            self.gpu_fan_lbl = fan_val_lbl
            self.gpu_fan_bar = bar
            self.gpu_temp_lbl = temp_val
            self.gpu_load_lbl = load_val

        return box

    def _create_fan_control_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("nitro-card")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name("weather-windy-symbolic")
        title_lbl = Gtk.Label(label="Fan Speed Control Mode", xalign=0)
        title_lbl.add_css_class("card-title")
        h_box.append(img)
        h_box.append(title_lbl)
        box.append(h_box)

        sub_desc = Gtk.Label(
            label="Choose dynamic firmware cooling (Auto), full throttle 100% cooling (Max), or manual slider control (Custom).",
            xalign=0
        )
        sub_desc.add_css_class("stat-subtext")
        box.append(sub_desc)

        modes_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        box.append(modes_row)

        self.btn_fan_auto = Gtk.Button(label="🔄 Auto Dynamic")
        self.btn_fan_auto.add_css_class("fan-mode-btn")
        self.btn_fan_auto.connect("clicked", lambda b: self._on_fan_mode_clicked("auto"))
        modes_row.append(self.btn_fan_auto)

        self.btn_fan_max = Gtk.Button(label="🚀 Max Full (100%)")
        self.btn_fan_max.add_css_class("fan-mode-btn")
        self.btn_fan_max.connect("clicked", lambda b: self._on_fan_mode_clicked("max"))
        modes_row.append(self.btn_fan_max)

        self.btn_fan_custom = Gtk.Button(label="🎛️ Custom Manual")
        self.btn_fan_custom.add_css_class("fan-mode-btn")
        self.btn_fan_custom.connect("clicked", lambda b: self._on_fan_mode_clicked("custom"))
        modes_row.append(self.btn_fan_custom)

        self.slider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.slider_box.set_margin_top(6)
        box.append(self.slider_box)

        slider_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        slider_title = Gtk.Label(label="Manual Target Speed:", xalign=0)
        slider_title.add_css_class("card-title")
        self.slider_val_lbl = Gtk.Label(label="60% (~4800 RPM)", xalign=1)
        self.slider_val_lbl.set_hexpand(True)
        self.slider_val_lbl.add_css_class("stat-subtext")
        slider_header.append(slider_title)
        slider_header.append(self.slider_val_lbl)
        self.slider_box.append(slider_header)

        self.fan_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 25, 100, 5)
        self.fan_slider.add_css_class("nitro-slider")
        self.fan_slider.set_value(60)
        self.fan_slider.set_hexpand(True)
        self.fan_slider.connect("value-changed", self._on_slider_value_changed)
        self.slider_box.append(self.fan_slider)

        presets_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        presets_row.set_margin_top(4)
        for pct in [30, 50, 75, 100]:
            p_btn = Gtk.Button(label=f"{pct}%")
            p_btn.connect("clicked", lambda b, p=pct: self._on_preset_clicked(p))
            presets_row.append(p_btn)
        self.slider_box.append(presets_row)

        return box

    def _on_fan_mode_clicked(self, mode):
        ok, res = self.backend.set_fan_mode(mode)
        if ok:
            title_map = {"auto": "Auto Dynamic", "max": "Max Full Throttle", "custom": "Custom Manual"}
            toast = Adw.Toast.new(f"Fan Mode: {title_map.get(mode, mode)}")
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)
            if mode == "custom":
                val = int(self.fan_slider.get_value())
                self.backend.set_fan_speed(val)
            self.update_stats()

    def _on_slider_value_changed(self, scale):
        pct = int(scale.get_value())
        rpm_est = int(round(1800 + (pct / 100.0) * (7800 - 1800)))
        self.slider_val_lbl.set_label(f"{pct}% (~{rpm_est} RPM)")
        self.backend.set_fan_speed(pct)

    def _on_preset_clicked(self, pct):
        self.fan_slider.set_value(pct)
        self.backend.set_fan_speed(pct)

    def _create_profile_btn(self, title, emoji, subtitle, key):
        btn = Gtk.Button()
        btn.add_css_class("profile-btn")
        
        b_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        b_box.set_margin_top(6)
        b_box.set_margin_bottom(6)
        b_box.set_margin_start(4)
        b_box.set_margin_end(4)

        icon_lbl = Gtk.Label(label=emoji)
        name_lbl = Gtk.Label(label=title)
        name_lbl.add_css_class("profile-btn-title")
        sub_lbl = Gtk.Label(label=subtitle)
        sub_lbl.add_css_class("profile-btn-desc")

        b_box.append(icon_lbl)
        b_box.append(name_lbl)
        b_box.append(sub_lbl)
        btn.set_child(b_box)

        btn.connect("clicked", lambda b: self._on_profile_clicked(key, title))
        return btn

    def _on_profile_clicked(self, key, title):
        ok, res = self.backend.set_platform_profile(key)
        if ok:
            toast = Adw.Toast.new(f"Switched to {title} Mode")
            toast.set_timeout(2)
            self.toast_overlay.add_toast(toast)
            self.update_stats()
        else:
            toast = Adw.Toast.new(f"Error: {res}")
            self.toast_overlay.add_toast(toast)

    def _create_nvidia_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("nitro-card")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name("video-display-symbolic")
        title_lbl = Gtk.Label(label="NVIDIA Dedicated GPU Telemetry", xalign=0)
        title_lbl.add_css_class("card-title")
        h_box.append(img)
        h_box.append(title_lbl)
        box.append(h_box)

        stats_grid = Gtk.Grid(column_spacing=16, row_spacing=6, column_homogeneous=True)
        box.append(stats_grid)

        vram_title = Gtk.Label(label="VRAM Allocation", xalign=0)
        vram_title.add_css_class("stat-subtext")
        stats_grid.attach(vram_title, 0, 0, 1, 1)

        self.nv_vram_lbl = Gtk.Label(label="-- / 6144 MB", xalign=1)
        self.nv_vram_lbl.add_css_class("stat-subtext")
        stats_grid.attach(self.nv_vram_lbl, 1, 0, 1, 1)

        self.nv_vram_bar = Gtk.ProgressBar()
        self.nv_vram_bar.add_css_class("nitro-gpu-bar")
        stats_grid.attach(self.nv_vram_bar, 0, 1, 2, 1)

        pwr_title = Gtk.Label(label="Power Consumption", xalign=0)
        pwr_title.add_css_class("stat-subtext")
        stats_grid.attach(pwr_title, 0, 2, 1, 1)

        self.nv_pwr_lbl = Gtk.Label(label="-- W", xalign=1)
        self.nv_pwr_lbl.add_css_class("card-title")
        stats_grid.attach(self.nv_pwr_lbl, 1, 2, 1, 1)

        self.nv_clock_lbl = Gtk.Label(label="Clocks: -- MHz Core / -- MHz Mem", xalign=0)
        self.nv_clock_lbl.add_css_class("stat-subtext")
        stats_grid.attach(self.nv_clock_lbl, 0, 3, 2, 1)

        return box

    def _create_system_card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("nitro-card")

        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name("battery-level-80-charging-symbolic")
        title_lbl = Gtk.Label(label="System & Battery Telemetry", xalign=0)
        title_lbl.add_css_class("card-title")
        h_box.append(img)
        h_box.append(title_lbl)
        box.append(h_box)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20, homogeneous=True)
        box.append(row)

        mem_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        mem_h = Gtk.Label(label="RAM USAGE", xalign=0)
        mem_h.add_css_class("stat-subtext")
        self.ram_lbl = Gtk.Label(label="-- %", xalign=0)
        self.ram_lbl.add_css_class("card-title")
        mem_box.append(mem_h)
        mem_box.append(self.ram_lbl)
        row.append(mem_box)

        bat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        bat_h = Gtk.Label(label="BATTERY STATUS", xalign=0)
        bat_h.add_css_class("stat-subtext")
        self.bat_lbl = Gtk.Label(label="-- %", xalign=0)
        self.bat_lbl.add_css_class("card-title")
        bat_box.append(bat_h)
        bat_box.append(self.bat_lbl)
        row.append(bat_box)

        drv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        drv_h = Gtk.Label(label="INTERFACE DRIVER", xalign=0)
        drv_h.add_css_class("stat-subtext")
        self.drv_lbl = Gtk.Label(label="acer_wmi (Predator v4 + PWM)", xalign=0)
        self.drv_lbl.add_css_class("card-title")
        drv_box.append(drv_h)
        drv_box.append(self.drv_lbl)
        row.append(drv_box)

        return box

    def _set_temp_class(self, label, temp):
        label.remove_css_class("temp-badge-cool")
        label.remove_css_class("temp-badge-warm")
        label.remove_css_class("temp-badge-hot")
        if temp < 55:
            label.add_css_class("temp-badge-cool")
        elif temp < 75:
            label.add_css_class("temp-badge-warm")
        else:
            label.add_css_class("temp-badge-hot")

    def update_stats(self):
        try:
            m = self.backend.get_all_metrics()

            # CPU
            cfan = m.get("cpu_fan_rpm", 0)
            self.cpu_fan_lbl.set_label(f"{cfan} RPM")
            self.cpu_fan_bar.set_fraction(min(1.0, cfan / 8000.0) if cfan > 0 else 0.0)
            ctemp = m.get("cpu_temp", 0.0)
            self.cpu_temp_lbl.set_label(f"{ctemp:.1f} °C")
            self._set_temp_class(self.cpu_temp_lbl, ctemp)
            cutil = m.get("cpu_util", 0.0)
            self.cpu_load_lbl.set_label(f"{cutil:.1f} %")

            # GPU
            gfan = m.get("gpu_fan_rpm", 0)
            self.gpu_fan_lbl.set_label(f"{gfan} RPM")
            self.gpu_fan_bar.set_fraction(min(1.0, gfan / 8000.0) if gfan > 0 else 0.0)
            gtemp = m.get("gpu_temp", 0.0)
            self.gpu_temp_lbl.set_label(f"{gtemp:.1f} °C")
            self._set_temp_class(self.gpu_temp_lbl, gtemp)
            gutil = m.get("nvidia", {}).get("utilization", 0)
            self.gpu_load_lbl.set_label(f"{gutil} %")

            # Fan Mode Highlighting
            cur_fan_mode = m.get("fan_mode", "auto")
            self.btn_fan_auto.remove_css_class("fan-mode-auto-active")
            self.btn_fan_max.remove_css_class("fan-mode-max-active")
            self.btn_fan_custom.remove_css_class("fan-mode-custom-active")

            if cur_fan_mode == "auto":
                self.btn_fan_auto.add_css_class("fan-mode-auto-active")
                self.slider_box.set_opacity(0.35)
                self.fan_slider.set_sensitive(False)
            elif cur_fan_mode == "max":
                self.btn_fan_max.add_css_class("fan-mode-max-active")
                self.slider_box.set_opacity(0.35)
                self.fan_slider.set_sensitive(False)
            elif cur_fan_mode == "custom":
                self.btn_fan_custom.add_css_class("fan-mode-custom-active")
                self.slider_box.set_opacity(1.0)
                self.fan_slider.set_sensitive(True)

            # NVIDIA
            nv = m.get("nvidia", {})
            if nv.get("available", False):
                used_mb = nv.get("mem_used", 0)
                tot_mb = nv.get("mem_total", 6144)
                self.nv_vram_lbl.set_label(f"{used_mb} MB / {tot_mb} MB")
                self.nv_vram_bar.set_fraction(min(1.0, used_mb / tot_mb) if tot_mb > 0 else 0.0)
                pwr = nv.get("power", 0.0)
                self.nv_pwr_lbl.set_label(f"{pwr:.1f} W")
                cg = nv.get("clock_graphics", 0)
                cm = nv.get("clock_memory", 0)
                self.nv_clock_lbl.set_label(f"Clocks: {cg} MHz Core / {cm} MHz VRAM")

            # System
            m_used = m.get("mem_used_mb", 0)
            m_tot = m.get("mem_total_mb", 0)
            m_pct = m.get("mem_util", 0.0)
            self.ram_lbl.set_label(f"{m_used} MB / {m_tot} MB ({m_pct:.0f}%)")

            bat = m.get("battery", {})
            if bat.get("present", False):
                cap = bat.get("capacity", 0)
                st = bat.get("status", "Unknown")
                hlth = bat.get("health_pct", 100)
                self.bat_lbl.set_label(f"{cap}% ({st}) • {hlth}% Health")

            # Daemon Status
            d_ok = m.get("daemon_active", False)
            if d_ok:
                self.status_pill.set_label("DAEMON ACTIVE")
                self.status_pill.remove_css_class("temp-badge-warm")
                self.status_pill.add_css_class("status-pill")
            else:
                self.status_pill.set_label("STANDALONE")

            # Profile state
            active_prof = m.get("profile", {}).get("raw", "balanced")
            display_prof = m.get("profile", {}).get("display", "Balanced")
            self.profile_status_lbl.set_label(f"Active Profile: {display_prof} ({active_prof})")

            btn_map = [
                (self.btn_quiet, "quiet"),
                (self.btn_balanced, "balanced"),
                (self.btn_perf, "balanced-performance"),
                (self.btn_eco, "low-power")
            ]
            for btn, k in btn_map:
                if active_prof == k:
                    btn.add_css_class("profile-btn-active")
                else:
                    btn.remove_css_class("profile-btn-active")

        except Exception as e:
            print("Error updating stats:", e)

        return GLib.SOURCE_CONTINUE

class NitroSenseApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.acer.nitrosense",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = NitroSenseWindow(application=self)
        win.present()

if __name__ == "__main__":
    app = NitroSenseApp()
    app.run(sys.argv)
