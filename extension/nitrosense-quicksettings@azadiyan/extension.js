import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {QuickMenuToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const ACPI_PROFILE_PATH = '/sys/firmware/acpi/platform_profile';
const CONFIG_FILE_PATH = '/etc/nitrosense/config.json';

const PROFILE_CONFIGS = {
    'performance': {
        name: 'Performance',
        iconName: 'power-profile-performance-symbolic',
        raw: 'balanced-performance',
    },
    'balanced': {
        name: 'Balanced',
        iconName: 'power-profile-balanced-symbolic',
        raw: 'balanced',
    },
    'quiet': {
        name: 'Whisper / Quiet',
        iconName: 'power-profile-power-saver-symbolic',
        raw: 'quiet',
    },
};

function readHardwareProfile() {
    try {
        const file = Gio.File.new_for_path(ACPI_PROFILE_PATH);
        const [, contents] = file.load_contents(null);
        const raw = new TextDecoder('utf-8').decode(contents).trim();
        if (raw === 'balanced-performance' || raw === 'performance')
            return 'performance';
        if (raw === 'quiet' || raw === 'whisper')
            return 'quiet';
        if (raw === 'low-power' || raw === 'eco')
            return 'quiet'; // Map low-power to whisper for the 3 user choices
        return 'balanced';
    } catch (e) {
        return 'balanced';
    }
}

function writeHardwareAndConfig(targetKey) {
    const rawTarget = PROFILE_CONFIGS[targetKey]?.raw ?? 'balanced';
    try {
        const file = Gio.File.new_for_path(ACPI_PROFILE_PATH);
        file.replace_contents(rawTarget, null, false, Gio.FileCreateFlags.NONE, null);
    } catch (e) {
        console.warn(`[NitroSense] Failed to write directly to ${ACPI_PROFILE_PATH}:`, e);
    }

    try {
        let cfg = { profile: targetKey, fan_mode: 'auto', fan_speed: 60 };
        const cfgFile = Gio.File.new_for_path(CONFIG_FILE_PATH);
        if (cfgFile.query_exists(null)) {
            try {
                const [, contents] = cfgFile.load_contents(null);
                cfg = JSON.parse(new TextDecoder('utf-8').decode(contents));
                cfg.profile = targetKey;
            } catch (err) {}
        }
        cfgFile.replace_contents(JSON.stringify(cfg, null, 2), null, false, Gio.FileCreateFlags.NONE, null);
    } catch (e) {
        console.warn(`[NitroSense] Failed to write config:`, e);
    }

    // Call CLI asynchronously to ensure daemon and tuned sync
    const cliCmd = targetKey === 'quiet' ? 'whisper' : (targetKey === 'performance' ? 'perf' : 'balanced');
    try {
        GLib.spawn_command_line_async(`/usr/local/bin/nitrosense ${cliCmd}`);
    } catch (e) {}
}

const NitroSenseToggle = GObject.registerClass(
class NitroSenseToggle extends QuickMenuToggle {
    _init(indicator) {
        super._init({
            title: 'NitroSense',
            menuButtonAccessibleName: 'NitroSense profile menu',
        });

        this._indicator = indicator;
        this._profileItems = new Map();

        // Menu header
        this.menu.setHeader('power-profile-balanced-symbolic', 'NitroSense Profile', null);

        this._profileSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._profileSection);

        // 3 Modes as requested: Performance, Balanced, Whisper Mode
        const modeOrder = ['performance', 'balanced', 'quiet'];
        for (const key of modeOrder) {
            const {name, iconName} = PROFILE_CONFIGS[key];
            const item = new PopupMenu.PopupImageMenuItem(name, iconName);
            item.connect('activate', () => {
                this._indicator.changeProfile(key);
            });
            this._profileItems.set(key, item);
            this._profileSection.addMenuItem(item);
        }

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addAction('Open NitroSense App', () => {
            Main.panel.closeQuickSettings();
            try {
                GLib.spawn_command_line_async('/usr/local/bin/nitrosense gui');
            } catch (e) {}
        });

        // Click on the toggle button itself: toggle between balanced and last active profile
        this.connect('clicked', () => {
            const current = this._indicator.activeProfile;
            const next = current === 'balanced'
                ? (this._indicator.lastNonBalancedProfile || 'performance')
                : 'balanced';
            this._indicator.changeProfile(next);
        });
    }

    updateUI(activeProfile) {
        const info = PROFILE_CONFIGS[activeProfile] ?? PROFILE_CONFIGS['balanced'];
        this.set({
            subtitle: info.name,
            iconName: info.iconName,
        });

        this.checked = (activeProfile !== 'balanced');

        for (const [key, item] of this._profileItems) {
            item.setOrnament(key === activeProfile ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }
    }
});

const NitroSenseIndicator = GObject.registerClass(
class NitroSenseIndicator extends SystemIndicator {
    _init() {
        super._init();

        this.activeProfile = 'balanced';
        this.lastNonBalancedProfile = 'performance';

        // Top bar icon
        this._topBarIcon = this._addIndicator();

        // Quick Settings item
        this._toggle = new NitroSenseToggle(this);
        this.quickSettingsItems.push(this._toggle);

        this._setupFileWatchers();
        this.sync();
    }

    sync() {
        const current = readHardwareProfile();
        this.activeProfile = current;
        if (current !== 'balanced') {
            this.lastNonBalancedProfile = current;
        }

        // 1. Update Quick Settings toggle
        this._toggle.updateUI(current);

        // 2. Update Top Bar Indicator icon
        // - Performance: tachometer gauge icon (power-profile-performance-symbolic)
        // - Balanced: hidden (show nothing)
        // - Whisper / Quiet: leaf icon (power-profile-power-saver-symbolic)
        if (current === 'performance') {
            this._topBarIcon.icon_name = 'power-profile-performance-symbolic';
            this._topBarIcon.visible = true;
        } else if (current === 'quiet') {
            this._topBarIcon.icon_name = 'power-profile-power-saver-symbolic';
            this._topBarIcon.visible = true;
        } else {
            // Balanced mode: show nothing in the top bar!
            this._topBarIcon.visible = false;
        }
    }

    changeProfile(key) {
        writeHardwareAndConfig(key);
        this.sync();
    }

    _setupFileWatchers() {
        // Monitor sysfs ACPI platform_profile
        try {
            const acpiFile = Gio.File.new_for_path(ACPI_PROFILE_PATH);
            this._acpiMonitor = acpiFile.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._acpiMonitorId = this._acpiMonitor.connect('changed', () => {
                GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                    this.sync();
                    return GLib.SOURCE_REMOVE;
                });
            });
        } catch (e) {
            console.warn('[NitroSense] ACPI monitor error:', e);
        }

        // Monitor config json
        try {
            const cfgFile = Gio.File.new_for_path(CONFIG_FILE_PATH);
            this._cfgMonitor = cfgFile.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._cfgMonitorId = this._cfgMonitor.connect('changed', () => {
                GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
                    this.sync();
                    return GLib.SOURCE_REMOVE;
                });
            });
        } catch (e) {}

        // Fallback polling timer every 2 seconds
        this._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this.sync();
            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        if (this._timerId) {
            GLib.source_remove(this._timerId);
            this._timerId = null;
        }
        if (this._acpiMonitor && this._acpiMonitorId) {
            this._acpiMonitor.disconnect(this._acpiMonitorId);
            this._acpiMonitor = null;
        }
        if (this._cfgMonitor && this._cfgMonitorId) {
            this._cfgMonitor.disconnect(this._cfgMonitorId);
            this._cfgMonitor = null;
        }

        this.quickSettingsItems.forEach(item => item.destroy());
        super.destroy();
    }
});

export default class NitroSenseExtension extends Extension {
    enable() {
        const quickSettings = Main.panel.statusArea.quickSettings;

        // 1. Hide the default battery power-profile indicator from the top bar
        // ("میخوام اون بالا باتری نشون نده ولی به جاش این برای سیپییو رو نشون بده")
        this._hideDefaultPowerProfileIndicator();

        // 2. Create NitroSense indicator & quick toggle
        this._nitroIndicator = new NitroSenseIndicator();

        // 3. Add to QuickSettings Menu (adds toggle to menu grid and indicator to top bar)
        quickSettings.addExternalIndicator(this._nitroIndicator, 1);

        // 4. Reposition our indicator right before the battery icon in the top panel
        this._positionIndicatorNearBattery();
    }

    disable() {
        // Restore default power profiles indicator
        this._restoreDefaultPowerProfileIndicator();

        if (this._nitroIndicator) {
            this._nitroIndicator.destroy();
            this._nitroIndicator = null;
        }
    }

    _hideDefaultPowerProfileIndicator() {
        const quickSettings = Main.panel.statusArea.quickSettings;
        const pp = quickSettings._powerProfiles;
        if (pp) {
            if (pp._indicator) {
                pp._indicator.visible = false;
                this._ppIndSig = pp._indicator.connect('notify::visible', () => {
                    if (pp._indicator && pp._indicator.visible)
                        pp._indicator.visible = false;
                });
            }
            pp.visible = false;
            this._ppBoxSig = pp.connect('notify::visible', () => {
                if (pp.visible)
                    pp.visible = false;
            });
        }
    }

    _restoreDefaultPowerProfileIndicator() {
        const quickSettings = Main.panel.statusArea.quickSettings;
        const pp = quickSettings?._powerProfiles;
        if (pp) {
            if (this._ppIndSig && pp._indicator) {
                pp._indicator.disconnect(this._ppIndSig);
                this._ppIndSig = null;
            }
            if (this._ppBoxSig) {
                pp.disconnect(this._ppBoxSig);
                this._ppBoxSig = null;
            }
            pp.visible = pp.get_children().some(c => c.visible);
        }
    }

    _positionIndicatorNearBattery() {
        const quickSettings = Main.panel.statusArea.quickSettings;
        const indicators = quickSettings._indicators;
        const system = quickSettings._system;
        if (indicators && system && this._nitroIndicator) {
            try {
                indicators.set_child_below_sibling(this._nitroIndicator, system);
            } catch (e) {
                try {
                    indicators.remove_child(this._nitroIndicator);
                    indicators.insert_child_below(this._nitroIndicator, system);
                } catch (e2) {}
            }
        }
    }
}
