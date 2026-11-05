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
        dbus: 'performance',
        tuned: 'throughput-performance',
    },
    'balanced': {
        name: 'Balanced',
        iconName: 'power-profile-balanced-symbolic',
        raw: 'balanced',
        dbus: 'balanced',
        tuned: 'balanced',
    },
    'quiet': {
        name: 'Whisper / Quiet',
        iconName: 'power-profile-power-saver-symbolic',
        raw: 'quiet',
        dbus: 'power-saver',
        tuned: 'powersave',
    },
};

function applyProfileAsync(targetKey) {
    const info = PROFILE_CONFIGS[targetKey] ?? PROFILE_CONFIGS['balanced'];
    const rawTarget = info.raw;
    const dbusTarget = info.dbus;

    // 1. Asynchronous non-blocking write to ACPI sysfs
    try {
        const acpiFile = Gio.File.new_for_path(ACPI_PROFILE_PATH);
        const bytes = new GLib.Bytes(new TextEncoder().encode(rawTarget + '\n'));
        acpiFile.replace_contents_bytes_async(
            bytes,
            null,
            false,
            Gio.FileCreateFlags.NONE,
            null,
            (file, res) => {
                try {
                    file.replace_contents_finish(res);
                } catch (err) {
                    try {
                        GLib.spawn_command_line_async(`sh -c "echo '${rawTarget}' > ${ACPI_PROFILE_PATH}"`);
                    } catch (e2) {}
                }
            }
        );
    } catch (e) {}

    // 2. Asynchronous non-blocking update of /etc/nitrosense/config.json
    try {
        const cfgFile = Gio.File.new_for_path(CONFIG_FILE_PATH);
        cfgFile.load_contents_async(null, (file, res) => {
            let cfg = { profile: targetKey, fan_mode: 'auto', fan_speed: 60 };
            try {
                const [, contents] = file.load_contents_finish(res);
                cfg = JSON.parse(new TextDecoder('utf-8').decode(contents));
                cfg.profile = targetKey;
            } catch (err) {
                cfg.profile = targetKey;
            }
            try {
                const cfgBytes = new GLib.Bytes(new TextEncoder().encode(JSON.stringify(cfg, null, 2) + '\n'));
                file.replace_contents_bytes_async(
                    cfgBytes,
                    null,
                    false,
                    Gio.FileCreateFlags.NONE,
                    null,
                    (f2, res2) => {
                        try { f2.replace_contents_finish(res2); } catch (e) {}
                    }
                );
            } catch (e) {}
        });
    } catch (e) {}

    // 3. Instant asynchronous D-Bus call to tuned-ppd / power-profiles-daemon (<40ms)
    try {
        Gio.DBus.system.call(
            'net.hadess.PowerProfiles',
            '/net/hadess/PowerProfiles',
            'org.freedesktop.DBus.Properties',
            'Set',
            new GLib.Variant('(ssv)', [
                'net.hadess.PowerProfiles',
                'ActiveProfile',
                new GLib.Variant('s', dbusTarget)
            ]),
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (err) {
                    try {
                        GLib.spawn_command_line_async(`tuned-adm profile ${info.tuned}`);
                    } catch (e2) {}
                }
            }
        );
    } catch (e) {
        try {
            GLib.spawn_command_line_async(`tuned-adm profile ${info.tuned}`);
        } catch (e2) {}
    }
}

const NitroSenseToggle = GObject.registerClass(
class NitroSenseToggle extends QuickMenuToggle {
    _init(indicator) {
        super._init({
            title: 'NitroSense',
            menuButtonAccessibleName: 'NitroSense Profile Menu',
        });

        this._indicator = indicator;
        this._profileItems = new Map();

        this.menu.setHeader('power-profile-balanced-symbolic', 'NitroSense Profile', null);

        this._profileSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._profileSection);

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

        this.connect('clicked', () => {
            const current = this._indicator.activeProfile;
            const next = (current === 'balanced')
                ? (this._indicator.lastNonBalancedProfile || 'performance')
                : 'balanced';
            this._indicator.changeProfile(next);
        });
    }

    updateUI(activeProfile) {
        const info = PROFILE_CONFIGS[activeProfile] ?? PROFILE_CONFIGS['balanced'];

        if (this.subtitle !== info.name || this.iconName !== info.iconName) {
            this.set({
                subtitle: info.name,
                iconName: info.iconName,
            });
        }

        const isChecked = (activeProfile !== 'balanced');
        if (this.checked !== isChecked) {
            this.checked = isChecked;
        }

        for (const [key, item] of this._profileItems) {
            const desiredOrnament = (key === activeProfile)
                ? PopupMenu.Ornament.CHECK
                : PopupMenu.Ornament.NONE;
            if (item._ornament !== desiredOrnament) {
                item.setOrnament(desiredOrnament);
            }
        }
    }
});

const NitroSenseIndicator = GObject.registerClass(
class NitroSenseIndicator extends SystemIndicator {
    _init() {
        super._init();

        this.activeProfile = 'balanced';
        this.lastNonBalancedProfile = 'performance';
        this._isSwitching = false;
        this._cooldownTimerId = null;
        this._dbusSignalId = null;
        this._checkTimerId = null;

        // Top bar icon indicator
        this._topBarIcon = this._addIndicator();

        // Quick Settings item
        this._toggle = new NitroSenseToggle(this);
        this.quickSettingsItems.push(this._toggle);

        // Setup D-Bus listener and background sync
        this._setupListeners();

        // Initial sync
        this.syncInitial();
    }

    _updateTopBarIcon(profile) {
        if (!this._topBarIcon) return;

        let targetIcon = null;
        let shouldBeVisible = false;

        if (profile === 'performance') {
            targetIcon = 'power-profile-performance-symbolic';
            shouldBeVisible = true;
        } else if (profile === 'quiet') {
            targetIcon = 'power-profile-power-saver-symbolic';
            shouldBeVisible = true;
        } else {
            // Balanced: hidden in top bar, matches GNOME native behavior
            shouldBeVisible = false;
        }

        if (targetIcon && this._topBarIcon.icon_name !== targetIcon) {
            this._topBarIcon.icon_name = targetIcon;
        }

        if (this._topBarIcon.visible !== shouldBeVisible) {
            this._topBarIcon.visible = shouldBeVisible;
        }
    }

    changeProfile(key) {
        if (this.activeProfile === key && this._initialized)
            return;

        // 1. Immediately apply to in-memory state
        this.activeProfile = key;
        if (key !== 'balanced') {
            this.lastNonBalancedProfile = key;
        }

        // 2. Zero-latency instant UI update (no dropped frames, no lag)
        this._toggle.updateUI(key);
        this._updateTopBarIcon(key);

        // 3. Set cooldown lock (2500ms) to ignore external signals during write
        this._isSwitching = true;
        if (this._cooldownTimerId) {
            GLib.source_remove(this._cooldownTimerId);
            this._cooldownTimerId = null;
        }
        this._cooldownTimerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 2500, () => {
            this._isSwitching = false;
            this._cooldownTimerId = null;
            return GLib.SOURCE_REMOVE;
        });

        // 4. Asynchronous non-blocking application
        applyProfileAsync(key);
    }

    syncInitial() {
        // Read config and ACPI asynchronously
        try {
            const acpiFile = Gio.File.new_for_path(ACPI_PROFILE_PATH);
            acpiFile.load_contents_async(null, (f, res) => {
                let prof = 'balanced';
                try {
                    const [, contents] = f.load_contents_finish(res);
                    const raw = new TextDecoder('utf-8').decode(contents).trim();
                    if (raw === 'balanced-performance' || raw === 'performance')
                        prof = 'performance';
                    else if (raw === 'quiet' || raw === 'whisper' || raw === 'low-power' || raw === 'eco')
                        prof = 'quiet';
                } catch (e) {}

                this._initialized = true;
                this.activeProfile = prof;
                if (prof !== 'balanced')
                    this.lastNonBalancedProfile = prof;

                this._toggle.updateUI(prof);
                this._updateTopBarIcon(prof);
            });
        } catch (e) {
            this._initialized = true;
            this._toggle.updateUI('balanced');
            this._updateTopBarIcon('balanced');
        }
    }

    _setupListeners() {
        // 1. Listen for D-Bus ActiveProfile property changes
        try {
            this._dbusSignalId = Gio.DBus.system.signal_subscribe(
                'net.hadess.PowerProfiles',
                'org.freedesktop.DBus.Properties',
                'PropertiesChanged',
                '/net/hadess/PowerProfiles',
                null,
                Gio.DBusSignalFlags.NONE,
                (conn, sender, path, iface, signal, params) => {
                    if (this._isSwitching) return;
                    try {
                        const [, changedProps] = params.recursiveUnpack();
                        if (changedProps && changedProps['ActiveProfile']) {
                            const act = changedProps['ActiveProfile'];
                            let prof = 'balanced';
                            if (act === 'performance')
                                prof = 'performance';
                            else if (act === 'power-saver')
                                prof = 'quiet';
                            else
                                prof = 'balanced';

                            if (prof !== this.activeProfile) {
                                this.activeProfile = prof;
                                if (prof !== 'balanced')
                                    this.lastNonBalancedProfile = prof;
                                this._toggle.updateUI(prof);
                                this._updateTopBarIcon(prof);
                            }
                        }
                    } catch (e) {}
                }
            );
        } catch (e) {}

        // 2. Gentle fallback check every 5 seconds (asynchronous, non-blocking)
        this._checkTimerId = GLib.timeout_add_seconds(GLib.PRIORITY_LOW, 5, () => {
            if (this._isSwitching) return GLib.SOURCE_CONTINUE;

            try {
                const acpiFile = Gio.File.new_for_path(ACPI_PROFILE_PATH);
                acpiFile.load_contents_async(null, (f, res) => {
                    if (this._isSwitching) return;
                    try {
                        const [, contents] = f.load_contents_finish(res);
                        const raw = new TextDecoder('utf-8').decode(contents).trim();
                        let prof = 'balanced';
                        if (raw === 'balanced-performance' || raw === 'performance')
                            prof = 'performance';
                        else if (raw === 'quiet' || raw === 'whisper' || raw === 'low-power' || raw === 'eco')
                            prof = 'quiet';

                        if (prof !== this.activeProfile) {
                            this.activeProfile = prof;
                            if (prof !== 'balanced')
                                this.lastNonBalancedProfile = prof;
                            this._toggle.updateUI(prof);
                            this._updateTopBarIcon(prof);
                        }
                    } catch (e) {}
                });
            } catch (e) {}

            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        if (this._cooldownTimerId) {
            GLib.source_remove(this._cooldownTimerId);
            this._cooldownTimerId = null;
        }
        if (this._checkTimerId) {
            GLib.source_remove(this._checkTimerId);
            this._checkTimerId = null;
        }
        if (this._dbusSignalId) {
            Gio.DBus.system.signal_unsubscribe(this._dbusSignalId);
            this._dbusSignalId = null;
        }

        this.quickSettingsItems.forEach(item => item.destroy());
        super.destroy();
    }
});

export default class NitroSenseExtension extends Extension {
    enable() {
        const quickSettings = Main.panel.statusArea.quickSettings;

        this._silenceDefaultPowerProfiles();

        this._nitroIndicator = new NitroSenseIndicator();

        quickSettings.addExternalIndicator(this._nitroIndicator, 1);

        this._positionIndicatorNearBattery();
    }

    disable() {
        this._restoreDefaultPowerProfiles();

        if (this._nitroIndicator) {
            this._nitroIndicator.destroy();
            this._nitroIndicator = null;
        }
    }

    _silenceDefaultPowerProfiles() {
        const quickSettings = Main.panel.statusArea.quickSettings;
        const pp = quickSettings?._powerProfiles;
        if (!pp) return;

        if (!this._origSyncIndicatorsVisible) {
            this._origSyncIndicatorsVisible = pp._syncIndicatorsVisible;
            pp._syncIndicatorsVisible = () => {
                pp.visible = false;
            };
        }

        pp.visible = false;
        if (pp._indicator) {
            pp._indicator.visible = false;
        }

        if (pp._powerProfilesToggle) {
            pp._powerProfilesToggle.visible = false;
        }
    }

    _restoreDefaultPowerProfiles() {
        const quickSettings = Main.panel.statusArea.quickSettings;
        const pp = quickSettings?._powerProfiles;
        if (!pp) return;

        if (this._origSyncIndicatorsVisible) {
            pp._syncIndicatorsVisible = this._origSyncIndicatorsVisible;
            this._origSyncIndicatorsVisible = null;
        }
        if (pp._powerProfilesToggle) {
            pp._powerProfilesToggle.visible = true;
        }
        if (typeof pp._syncIndicatorsVisible === 'function') {
            pp._syncIndicatorsVisible();
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
