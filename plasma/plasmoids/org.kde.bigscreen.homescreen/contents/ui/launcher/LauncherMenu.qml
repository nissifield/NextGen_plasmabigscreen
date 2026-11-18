/*
    SPDX-FileCopyrightText: 2019 Aditya Mehra <aix.m@outlook.com>
    SPDX-FileCopyrightText: 2015 Marco Martin <mart@kde.org>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window

import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kquickcontrolsaddons
import org.kde.bigscreen as Launcher
import org.kde.private.biglauncher
import org.kde.kirigami as Kirigami

FocusScope {
    id: root

    property real startY
    property real leftMargin
    property real rightMargin
    property string activeCategory: "all"

    readonly property int reservedSpaceForLabel: metrics.height

    // Whether the view has scrolled down at least one row
    readonly property bool scrolledDown: launcherHome.scrolledDown
    readonly property var focusedApp: launcherHome.focusedApp

    property var currentOptionsApp: null
    property int currentFavIndex: -1
    property int totalFavCount: 0

    function selectCategory(cat) {
        launcherHome.selectCategory(cat);
    }

    function showOptions(app, mover) {
        if (!app || !app.storageId) {
            return;
        }
        root.currentOptionsApp = app;
        root.currentFavIndex = launcherHome.findFavIndex(app.storageId);
        root.totalFavCount = Plasmoid.favsListModel.count ?? 0;
        optionsOverlay.visible = true;
        btnOpenApp.forceActiveFocus();
        Launcher.NavigationSoundEffects.playClickedSound();
        Launcher.NavigationRumble.playConfirmRumble();
    }

    function closeOptions() {
        optionsOverlay.visible = false;
        launcherHome.activateAppView();
    }

    readonly property bool contextMenuOpen: optionsOverlay.visible

    function closeContextMenuIfOpen() {
        if (optionsOverlay.visible) {
            closeOptions();
            return true;
        }
        return false;
    }

    onActiveFocusChanged: {
        if (activeFocus && !launcherHome.activeFocus && !optionsOverlay.visible) {
            launcherHome.activateAppView();
        }
    }

    Controls.Label {
        id: metrics
        text: "M\nM"
        visible: false
    }

    LauncherHome {
        id: launcherHome
        anchors {
            fill: parent
            leftMargin: root.leftMargin
            rightMargin: root.rightMargin
        }

        activeCategory: root.activeCategory
        navigationUp: root.KeyNavigation.up
        startY: root.startY
        onOptionsRequested: (app, mover) => root.showOptions(app, mover)
    }

    component ContextActionButton: Controls.AbstractButton {
        id: actionBtn
        property string iconSource: "application-x-executable"
        property bool destructive: false
        Layout.fillWidth: true
        implicitHeight: Kirigami.Units.gridUnit * 2.8
        hoverEnabled: true

        onClicked: {
            Launcher.NavigationSoundEffects.playClickedSound();
            Launcher.NavigationRumble.playConfirmRumble();
        }

        Keys.onReturnPressed: (event) => {
            event.accepted = true;
            actionBtn.clicked();
        }
        Keys.onEnterPressed: (event) => {
            event.accepted = true;
            actionBtn.clicked();
        }
        Keys.onSelectPressed: (event) => {
            event.accepted = true;
            actionBtn.clicked();
        }
        Keys.onSpacePressed: (event) => {
            event.accepted = true;
            actionBtn.clicked();
        }

        Keys.onEscapePressed: (event) => {
            event.accepted = true;
            root.closeOptions();
        }

        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
                Launcher.NavigationSoundEffects.playMovingSound();
                Launcher.NavigationRumble.playNavigationRumble();
            } else if (event.key === Qt.Key_Back || event.key === Qt.Key_Backspace) {
                event.accepted = true;
                root.closeOptions();
            }
        }

        background: Rectangle {
            radius: Kirigami.Units.cornerRadius * 1.5
            color: {
                if (actionBtn.activeFocus) {
                    return actionBtn.destructive ? "#c0392b" : "white";
                }
                if (actionBtn.hovered) {
                    return Qt.rgba(1, 1, 1, 0.14);
                }
                return Qt.rgba(1, 1, 1, 0.06);
            }
            border.width: actionBtn.activeFocus ? 2 : 1
            border.color: actionBtn.activeFocus ? Kirigami.Theme.highlightColor : Qt.rgba(1, 1, 1, 0.12)
            Behavior on color { ColorAnimation { duration: 120 } }
        }

        contentItem: RowLayout {
            spacing: Kirigami.Units.largeSpacing
            anchors {
                fill: parent
                leftMargin: Kirigami.Units.gridUnit * 1.2
                rightMargin: Kirigami.Units.gridUnit * 1.2
            }

            Kirigami.Icon {
                source: actionBtn.iconSource
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
                color: actionBtn.activeFocus
                    ? (actionBtn.destructive ? "white" : "#111318")
                    : (actionBtn.destructive ? "#ff6b6b" : "white")
            }

            Controls.Label {
                Layout.fillWidth: true
                text: actionBtn.text
                font.pixelSize: 18
                font.weight: actionBtn.activeFocus ? Font.DemiBold : Font.Normal
                color: actionBtn.activeFocus
                    ? (actionBtn.destructive ? "white" : "#111318")
                    : (actionBtn.destructive ? "#ff6b6b" : "white")
                elide: Text.ElideRight
            }
        }
    }

    // Android TV Long-Press Context Menu Modal Overlay
    FocusScope {
        id: optionsOverlay
        anchors.fill: parent
        visible: false
        z: 100

        Launcher.BackHandler.enabled: optionsOverlay.visible
        Launcher.BackHandler.onActivated: {
            Launcher.NavigationRumble.playNavigationRumble();
            root.closeOptions();
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.72)

            MouseArea {
                anchors.fill: parent
                onClicked: root.closeOptions()
            }
        }

        Rectangle {
            id: modalCard
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.42, Kirigami.Units.gridUnit * 28)
            implicitHeight: modalColumn.implicitHeight + Kirigami.Units.gridUnit * 3
            radius: Kirigami.Units.cornerRadius * 3
            color: "#181b22"
            border.width: 2
            border.color: Qt.rgba(1, 1, 1, 0.22)

            ColumnLayout {
                id: modalColumn
                anchors {
                    fill: parent
                    margins: Kirigami.Units.gridUnit * 1.5
                }
                spacing: Kirigami.Units.largeSpacing

                // App Header in Modal
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing

                    Kirigami.Icon {
                        source: root.currentOptionsApp ? (root.currentOptionsApp.iconName || "applications-multimedia") : "applications-multimedia"
                        implicitWidth: Kirigami.Units.iconSizes.large
                        implicitHeight: Kirigami.Units.iconSizes.large
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Controls.Label {
                            Layout.fillWidth: true
                            text: root.currentOptionsApp ? (root.currentOptionsApp.name || "") : ""
                            font.pixelSize: 24
                            font.weight: Font.Bold
                            color: "white"
                            elide: Text.ElideRight
                        }

                        Controls.Label {
                            Layout.fillWidth: true
                            text: (root.currentOptionsApp && root.currentOptionsApp.running)
                                ? i18n("● Currently Running")
                                : (root.currentOptionsApp ? (root.currentOptionsApp.description || i18n("TV Application Options")) : "")
                            font.pixelSize: 14
                            color: (root.currentOptionsApp && root.currentOptionsApp.running) ? "#4cd137" : Qt.rgba(1, 1, 1, 0.68)
                            elide: Text.ElideRight
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Qt.rgba(1, 1, 1, 0.14)
                }

                ContextActionButton {
                    id: btnOpenApp
                    iconSource: (root.currentOptionsApp && root.currentOptionsApp.running) ? "window-restore-symbolic" : "media-playback-start-symbolic"
                    text: (root.currentOptionsApp && root.currentOptionsApp.running) ? i18n("Resume Application") : i18n("Open Application")
                    KeyNavigation.down: btnToggleFav
                    onClicked: {
                        const app = root.currentOptionsApp;
                        root.closeOptions();
                        if (app && app.storageId) {
                            if (app.storageId === "return-to-desktop.desktop") {
                                Plasmoid.applicationListModel.runApplication(app.storageId);
                            } else if (app.storageId === "steam-bigpicture.desktop") {
                                Plasmoid.showAppLaunchScreen(app.name, app.iconName);
                                Plasmoid.applicationListModel.runApplication(app.storageId);
                            } else if (Plasmoid.applicationListModel.isApplicationRunning(app.storageId)) {
                                Plasmoid.applicationListModel.maximizeApplication(app.storageId);
                            } else {
                                Plasmoid.showAppLaunchScreen(app.name, app.iconName);
                                Plasmoid.applicationListModel.runApplication(app.storageId);
                            }
                        }
                    }
                }

                ContextActionButton {
                    id: btnToggleFav
                    iconSource: root.currentFavIndex >= 0 ? "list-remove-symbolic" : "bookmark-new-symbolic"
                    text: root.currentFavIndex >= 0 ? i18n("Remove from Favorites") : i18n("Pin to Favorites")
                    KeyNavigation.up: btnOpenApp
                    KeyNavigation.down: {
                        if (btnMoveLeft.visible) return btnMoveLeft;
                        if (btnMoveRight.visible) return btnMoveRight;
                        if (btnForceStop.visible) return btnForceStop;
                        return btnCancel;
                    }
                    onClicked: {
                        const app = root.currentOptionsApp;
                        if (app && app.storageId) {
                            if (root.currentFavIndex >= 0) {
                                FavsManager.removeFav(Plasmoid.favsListModel.itemMap(root.currentFavIndex));
                            } else {
                                const m = launcherHome.findAppItemMap(app.storageId);
                                if (m) {
                                    FavsManager.addFav(m);
                                }
                            }
                        }
                        root.closeOptions();
                    }
                }

                ContextActionButton {
                    id: btnMoveLeft
                    visible: root.currentFavIndex > 0
                    iconSource: "go-previous-symbolic"
                    text: i18n("Move Left in Favorites")
                    KeyNavigation.up: btnToggleFav
                    KeyNavigation.down: {
                        if (btnMoveRight.visible) return btnMoveRight;
                        if (btnForceStop.visible) return btnForceStop;
                        return btnCancel;
                    }
                    onClicked: {
                        if (root.currentFavIndex > 0) {
                            FavsManager.moveFav(Plasmoid.favsListModel.itemMap(root.currentFavIndex), root.currentFavIndex - 1);
                        }
                        root.closeOptions();
                    }
                }

                ContextActionButton {
                    id: btnMoveRight
                    visible: root.currentFavIndex >= 0 && root.currentFavIndex < (root.totalFavCount - 1)
                    iconSource: "go-next-symbolic"
                    text: i18n("Move Right in Favorites")
                    KeyNavigation.up: btnMoveLeft.visible ? btnMoveLeft : btnToggleFav
                    KeyNavigation.down: btnForceStop.visible ? btnForceStop : btnCancel
                    onClicked: {
                        if (root.currentFavIndex >= 0 && root.currentFavIndex < (root.totalFavCount - 1)) {
                            FavsManager.moveFav(Plasmoid.favsListModel.itemMap(root.currentFavIndex), root.currentFavIndex + 1);
                        }
                        root.closeOptions();
                    }
                }

                ContextActionButton {
                    id: btnForceStop
                    visible: Boolean(root.currentOptionsApp && root.currentOptionsApp.running)
                    destructive: true
                    iconSource: "process-stop-symbolic"
                    text: i18n("Force Stop (Quit App)")
                    KeyNavigation.up: {
                        if (btnMoveRight.visible) return btnMoveRight;
                        if (btnMoveLeft.visible) return btnMoveLeft;
                        return btnToggleFav;
                    }
                    KeyNavigation.down: btnCancel
                    onClicked: {
                        if (root.currentOptionsApp && root.currentOptionsApp.storageId) {
                            launcherHome.forceStopApp(root.currentOptionsApp.storageId);
                        }
                        root.closeOptions();
                    }
                }

                ContextActionButton {
                    id: btnCancel
                    iconSource: "dialog-close-symbolic"
                    text: i18n("Cancel")
                    KeyNavigation.up: {
                        if (btnForceStop.visible) return btnForceStop;
                        if (btnMoveRight.visible) return btnMoveRight;
                        if (btnMoveLeft.visible) return btnMoveLeft;
                        return btnToggleFav;
                    }
                    onClicked: root.closeOptions()
                }
            }
        }
    }
}
