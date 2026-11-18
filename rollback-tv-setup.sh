#!/usr/bin/env bash
set -e

echo "=== Rolling Back NextGen Plasma Bigscreen TV Setup ==="

# 1. Reset default boot session to Desktop
echo "--> Restoring default login session to Desktop..."
steamosctl set-default-login-mode desktop 2>/dev/null || true

# 2. Remove TV display-mode daemon, KWin script, Movie Mode toggle, and shell helpers
echo "--> Removing tv-display-mode daemon, Movie Mode toggle, KWin script, and Stremio shim..."
systemctl --user disable --now tv-display-mode.service 2>/dev/null || true
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript tv-display-mode 2>/dev/null || true
rm -f ~/.local/bin/tv-display-mode \
      ~/.local/bin/tv-movie-mode-toggle \
      ~/tv-display-mode.sh \
      ~/.bashrc.d/tv-display-mode.sh \
      ~/.config/systemd/user/tv-display-mode.service \
      ~/.config/mpv/scripts/tv-display-mode.lua \
      ~/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so
rm -rf ~/.local/share/tv-display-mode ~/.config/tv-display-mode ~/.local/state/tv-display-mode

# 3. Remove desktop launchers
echo "--> Removing TV desktop launchers..."
rm -f ~/Desktop/YouTube-TV.desktop ~/Desktop/Stremio.desktop ~/Desktop/Jellyfin.desktop ~/Desktop/Steam-Big-Picture.desktop ~/Desktop/Plasma-Bigscreen.desktop \
      ~/.local/share/applications/tv-movie-mode.desktop ~/.local/share/applications/plasma-bigscreen-swap.desktop ~/.local/share/applications/return-to-desktop.desktop \
      ~/.local/share/applications/rocks.shy.VacuumTube.desktop ~/.local/share/applications/com.stremio.Stremio.desktop \
      ~/.local/share/applications/org.jellyfin.JellyfinDesktop.desktop ~/.local/share/applications/steam-bigpicture.desktop
if [ -f ~/.tv-setup-backups/Return.desktop ]; then
    cp -p ~/.tv-setup-backups/Return.desktop ~/Desktop/Return.desktop
    chmod +x ~/Desktop/Return.desktop
fi

# 4. Remove user-space Plasma Bigscreen Android TV overrides, session switcher, inputhandler service, and configs
echo "--> Restoring standard KDE Plasma Desktop shell and removing Plasma Bigscreen user-space configs..."
if [ -x ~/.local/bin/tv-session-switch.sh ]; then
    ~/.local/bin/tv-session-switch.sh desktop 2>/dev/null || true
fi
systemctl --user disable --now plasma-bigscreen-inputhandler.service 2>/dev/null || true
rm -rf ~/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen ~/.config/plasma-bigscreen ~/.cache/plasma-bigscreen
rm -f ~/.config/bigscreen-favs ~/.config/applications-blacklistrc ~/.config/plasma-bigscreen-inputhandlerrc \
      ~/.config/autostart/plasma-bigscreen-autostart.desktop ~/.config/systemd/user/plasma-bigscreen-inputhandler.service \
      ~/.local/bin/tv-session-switch.sh

# 5. Remove VA-API hardware acceleration overrides and Flatpak user overrides
echo "--> Removing VA-API environment config and Flatpak overrides..."
rm -f ~/.config/environment.d/90-intel-vaapi.conf \
      ~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt \
      ~/.var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/mpv.conf
if [ -f ~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/config.json.bak ]; then
    mv -f ~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/config.json.bak \
          ~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/config.json
fi
for app in rocks.shy.VacuumTube org.jellyfin.JellyfinDesktop com.stremio.Stremio org.kde.haruna org.mozilla.firefox; do
    flatpak override --user --reset "$app" 2>/dev/null || true
done

# 6. Remove defense-in-depth Gamescope overrides
echo "--> Removing defense-in-depth Gamescope session overrides..."
rm -f ~/.config/gamescope-session-plus/sessions.d/ogui-steam ~/.config/gamescope/modes.cfg

# 7. Remove TV remote user-space keymap service and restore PowerDevil/shortcut defaults
echo "--> Removing TV remote keymap service and restoring PowerDevil/KGlobalAccel defaults..."
systemctl --user disable --now tv-remote-keymap.service 2>/dev/null || true
if [ -x ~/.local/bin/tv-remote-keymap.py ]; then
    ~/.local/bin/tv-remote-keymap.py --reset 2>/dev/null || true
fi
rm -f ~/.local/bin/tv-remote-keymap.py ~/.config/systemd/user/tv-remote-keymap.service
systemctl --user daemon-reload 2>/dev/null || true
if [ -f ~/.tv-setup-backups/powerdevilrc ]; then
    cp -p ~/.tv-setup-backups/powerdevilrc ~/.config/powerdevilrc
else
    kwriteconfig6 --file powerdevilrc --group AC --group SuspendAndShutdown --key PowerButtonAction 8 2>/dev/null || true
    kwriteconfig6 --file powerdevilrc --group AC --group SuspendAndShutdown --key PowerDownAction --delete 2>/dev/null || true
    kwriteconfig6 --file powerdevilrc --group Battery --group SuspendAndShutdown --key PowerButtonAction 1 2>/dev/null || true
    kwriteconfig6 --file powerdevilrc --group Battery --group SuspendAndShutdown --key PowerDownAction --delete 2>/dev/null || true
    kwriteconfig6 --file powerdevilrc --group LowBattery --group SuspendAndShutdown --key PowerButtonAction 1 2>/dev/null || true
    kwriteconfig6 --file powerdevilrc --group LowBattery --group SuspendAndShutdown --key PowerDownAction --delete 2>/dev/null || true
fi
kwriteconfig6 --file kglobalshortcutsrc --group org_kde_powerdevil --key Sleep "Sleep,Sleep,Suspend" 2>/dev/null || true
kwriteconfig6 --file kglobalshortcutsrc --group org_kde_powerdevil --key "Turn Off Screen" "none,none,Turn Off Screen" 2>/dev/null || true
systemctl --user restart plasma-powerdevil.service 2>/dev/null || true

# 8. Remove streaming launcher scripts and Plasma 6 steamos-add-to-steam override
echo "--> Removing streaming scripts and user-space steamos-add-to-steam fix..."
rm -rf ~/Applications/streaming_scripts
rm -f ~/.local/bin/steamos-add-to-steam

# 9. Restore WirePlumber audio priority
echo "--> Restoring WirePlumber audio rules..."
rm -f ~/.config/wireplumber/wireplumber.conf.d/90-tv-hdmi-audio.conf
systemctl --user restart wireplumber 2>/dev/null || true

# 10. Disable lingering if desired
loginctl disable-linger "$USER" 2>/dev/null || true

echo "=== Rollback Complete ==="
echo "Your user-space environment has been returned to stock defaults."
