"""
NitroSense Hardware Backend for Acer Nitro V 15 (ANV15-51)
"""
import glob
import os
import json
import subprocess
import time

CONFIG_DIR = "/etc/nitrosense"
CONFIG_FILE = "/etc/nitrosense/config.json"

DEFAULT_CONFIG = {
    "profile": "performance",
    "fan_mode": "auto",
    "fan_speed": 60,
}

PROFILE_MAP = {
    "quiet": "quiet",
    "whisper": "quiet",
    "balanced": "balanced",
    "performance": "balanced-performance",
    "perf": "balanced-performance",
    "eco": "low-power",
    "low-power": "low-power",
}

REV_PROFILE_MAP = {
    "quiet": "Whisper / Quiet",
    "balanced": "Balanced",
    "balanced-performance": "Performance",
    "performance": "Performance",
    "low-power": "Eco",
}

NORM_MAP = {
    "quiet": "quiet",
    "whisper": "quiet",
    "balanced": "balanced",
    "balanced-performance": "performance",
    "performance": "performance",
    "perf": "performance",
    "low-power": "eco",
    "eco": "eco",
}

class NitroBackend:
    def __init__(self):
        self._last_total = None
        self._last_idle = None
        self.acer_hwmon = self._locate_acer_hwmon()

    def _locate_acer_hwmon(self):
        for p in glob.glob("/sys/class/hwmon/hwmon*"):
            name_file = os.path.join(p, "name")
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r") as f:
                        if f.read().strip() == "acer":
                            return p
                except Exception:
                    pass
        return None

    def read_file(self, path, default="0"):
        if not path or not os.path.exists(path):
            return default
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return default

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    cfg = dict(DEFAULT_CONFIG)
                    cfg.update(data)
                    return cfg
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)

    def save_config(self, **kwargs):
        cfg = self.load_config()
        changed = False
        for k, v in kwargs.items():
            if cfg.get(k) != v:
                cfg[k] = v
                changed = True
        if not changed and os.path.exists(CONFIG_FILE):
            return True
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
            os.chmod(CONFIG_FILE, 0o666)
            return True
        except Exception:
            try:
                content = json.dumps(cfg, indent=2)
                cmd = ["sudo", "sh", "-c", f"cat << 'INNEREOF' > {CONFIG_FILE}\n{content}\nINNEREOF\nchmod 666 {CONFIG_FILE}"]
                res = subprocess.run(cmd, capture_output=True)
                return res.returncode == 0
            except Exception:
                return False

    def get_cpu_utilization(self):
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
            fields = [float(x) for x in line.strip().split()[1:]]
            idle = fields[3] + fields[4]
            total = sum(fields)
            if self._last_total is not None and self._last_idle is not None:
                d_total = total - self._last_total
                d_idle = idle - self._last_idle
                util = 100.0 * (1.0 - d_idle / d_total) if d_total > 0 else 0.0
            else:
                util = 0.0
            self._last_total = total
            self._last_idle = idle
            return max(0.0, min(100.0, util))
        except Exception:
            return 0.0

    def get_mem_utilization(self):
        try:
            mem_total = 0
            mem_avail = 0
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail = int(line.split()[1])
            if mem_total > 0:
                used = mem_total - mem_avail
                return (used / mem_total) * 100.0, used // 1024, mem_total // 1024
        except Exception:
            pass
        return 0.0, 0, 0

    def get_nvidia_stats(self):
        stats = {
            "available": False,
            "name": "NVIDIA RTX 3050",
            "utilization": 0,
            "mem_used": 0,
            "mem_total": 6144,
            "temp": 0,
            "power": 0.0,
        }
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 6:
                    stats["available"] = True
                    stats["name"] = parts[0]
                    stats["utilization"] = int(float(parts[1]))
                    stats["mem_used"] = int(float(parts[2]))
                    stats["mem_total"] = int(float(parts[3]))
                    stats["temp"] = int(float(parts[4]))
                    stats["power"] = float(parts[5])
        except Exception:
            pass
        return stats

    def get_battery_stats(self):
        bat = {"present": False, "capacity": 0, "status": "Unknown"}
        bat_dir = "/sys/class/power_supply/BAT1"
        if os.path.exists(bat_dir):
            bat["present"] = True
            bat["capacity"] = int(self.read_file(f"{bat_dir}/capacity", "0"))
            bat["status"] = self.read_file(f"{bat_dir}/status", "Unknown")
        return bat

    def get_platform_profile(self):
        raw = self.read_file("/sys/firmware/acpi/platform_profile", "balanced")
        return {
            "raw": raw,
            "display": REV_PROFILE_MAP.get(raw, raw.capitalize()),
            "normalized": NORM_MAP.get(raw, "balanced"),
            "choices": ["quiet", "balanced", "balanced-performance", "low-power"]
        }

    def set_platform_profile(self, target):
        mapped = PROFILE_MAP.get(target.lower(), target)
        norm = NORM_MAP.get(target.lower(), target)
        path = "/sys/firmware/acpi/platform_profile"
        success = False
        try:
            with open(path, "w") as f:
                f.write(mapped)
            success = True
        except Exception:
            cmd = ["sudo", "sh", "-c", f"echo {mapped} > {path}"]
            res = subprocess.run(cmd, capture_output=True)
            success = (res.returncode == 0)

        if success:
            self.save_config(profile=norm)
            self._sync_tuned(norm)
            return True, mapped
        return False, mapped

    def _sync_tuned(self, norm):
        tuned_map = {
            "performance": "throughput-performance",
            "balanced": "balanced",
            "quiet": "powersave",
            "eco": "powersave",
        }
        target_tuned = tuned_map.get(norm)
        if target_tuned:
            try:
                subprocess.Popen(["tuned-adm", "profile", target_tuned],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def get_fan_mode(self):
        if not self.acer_hwmon or not os.path.exists(self.acer_hwmon):
            self.acer_hwmon = self._locate_acer_hwmon()
        if not self.acer_hwmon:
            return "auto", 50, 50

        # pwm1_enable: 0 = Turbo/Max, 1 = Custom, 2 = Auto
        raw_mode = self.read_file(f"{self.acer_hwmon}/pwm1_enable", "2")
        mode = "auto"
        if raw_mode == "0":
            mode = "max"
        elif raw_mode == "1":
            mode = "custom"
        elif raw_mode == "2":
            mode = "auto"

        raw_pwm1 = int(self.read_file(f"{self.acer_hwmon}/pwm1", "128"))
        raw_pwm2 = int(self.read_file(f"{self.acer_hwmon}/pwm2", "128"))
        pct1 = int(round((raw_pwm1 / 255.0) * 100))
        pct2 = int(round((raw_pwm2 / 255.0) * 100))
        return mode, pct1, pct2

    def set_fan_mode(self, mode):
        # mode: auto, max, custom
        if not self.acer_hwmon or not os.path.exists(self.acer_hwmon):
            self.acer_hwmon = self._locate_acer_hwmon()
        if not self.acer_hwmon:
            return False, "Acer hwmon not found"

        mode_val = {"max": 0, "custom": 1, "auto": 2}.get(mode.lower(), 2)
        try:
            with open(f"{self.acer_hwmon}/pwm1_enable", "w") as f1, open(f"{self.acer_hwmon}/pwm2_enable", "w") as f2:
                f1.write(str(mode_val))
                f2.write(str(mode_val))
            res_ok = True
        except Exception:
            cmd = [
                "sudo", "sh", "-c",
                f"echo {mode_val} > {self.acer_hwmon}/pwm1_enable && echo {mode_val} > {self.acer_hwmon}/pwm2_enable"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            res_ok = (res.returncode == 0)

        if res_ok:
            self.save_config(fan_mode=mode.lower())
            return True, mode
        return False, "Failed to write fan mode"

    def set_fan_speed(self, cpu_pct, gpu_pct=None):
        if not self.acer_hwmon or not os.path.exists(self.acer_hwmon):
            self.acer_hwmon = self._locate_acer_hwmon()
        if not self.acer_hwmon:
            return False, "Acer hwmon not found"

        if gpu_pct is None:
            gpu_pct = cpu_pct

        cpu_pwm = max(20, min(255, int(cpu_pct * 2.55)))
        gpu_pwm = max(20, min(255, int(gpu_pct * 2.55)))

        try:
            with open(f"{self.acer_hwmon}/pwm1_enable", "w") as f1, open(f"{self.acer_hwmon}/pwm2_enable", "w") as f2:
                f1.write("1")
                f2.write("1")
            with open(f"{self.acer_hwmon}/pwm1", "w") as p1, open(f"{self.acer_hwmon}/pwm2", "w") as p2:
                p1.write(str(cpu_pwm))
                p2.write(str(gpu_pwm))
            res_ok = True
        except Exception:
            cmd = [
                "sudo", "sh", "-c",
                f"echo 1 > {self.acer_hwmon}/pwm1_enable && "
                f"echo 1 > {self.acer_hwmon}/pwm2_enable && "
                f"echo {cpu_pwm} > {self.acer_hwmon}/pwm1 && "
                f"echo {gpu_pwm} > {self.acer_hwmon}/pwm2"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            res_ok = (res.returncode == 0)

        if res_ok:
            self.save_config(fan_mode="custom", fan_speed=int(cpu_pct))
            return True, (cpu_pct, gpu_pct)
        return False, "Failed to set custom fan speed"

    def apply_saved_config(self):
        cfg = self.load_config()
        prof = cfg.get("profile", "performance")
        self.set_platform_profile(prof)
        fan_mode = cfg.get("fan_mode", "auto")
        if fan_mode == "custom":
            speed = cfg.get("fan_speed", 60)
            self.set_fan_speed(speed)
        else:
            self.set_fan_mode(fan_mode)
        return True

    def get_all_metrics(self):
        if not self.acer_hwmon or not os.path.exists(self.acer_hwmon):
            self.acer_hwmon = self._locate_acer_hwmon()

        cpu_fan = 0
        gpu_fan = 0
        cpu_temp = 0.0
        gpu_temp = 0.0

        if self.acer_hwmon:
            cpu_fan = int(self.read_file(f"{self.acer_hwmon}/fan1_input", "0"))
            gpu_fan = int(self.read_file(f"{self.acer_hwmon}/fan2_input", "0"))
            cpu_temp_raw = int(self.read_file(f"{self.acer_hwmon}/temp1_input", "0"))
            gpu_temp_raw = int(self.read_file(f"{self.acer_hwmon}/temp3_input", "0"))
            cpu_temp = cpu_temp_raw / 1000.0 if cpu_temp_raw > 0 else 0.0
            gpu_temp = gpu_temp_raw / 1000.0 if gpu_temp_raw > 0 else 0.0

        mem_pct, mem_used, mem_total = self.get_mem_utilization()
        cpu_pct = self.get_cpu_utilization()
        nv_stats = self.get_nvidia_stats()
        profile = self.get_platform_profile()
        battery = self.get_battery_stats()
        fan_mode, cpu_pwm_pct, gpu_pwm_pct = self.get_fan_mode()

        if gpu_temp == 0.0 and nv_stats.get("temp", 0) > 0:
            gpu_temp = float(nv_stats["temp"])

        return {
            "cpu_fan_rpm": cpu_fan,
            "gpu_fan_rpm": gpu_fan,
            "cpu_temp": round(cpu_temp, 1),
            "gpu_temp": round(gpu_temp, 1),
            "cpu_util": round(cpu_pct, 1),
            "mem_util": round(mem_pct, 1),
            "mem_used_mb": mem_used,
            "mem_total_mb": mem_total,
            "nvidia": nv_stats,
            "profile": profile,
            "battery": battery,
            "fan_mode": fan_mode,
            "cpu_pwm_pct": cpu_pwm_pct,
            "gpu_pwm_pct": gpu_pwm_pct,
        }
